"""
Pure Python/NumPy replacement for the _dbdreader C extension.

Reads Slocum glider binary DBD/SBD/MBD/etc. files.  The public API is a
single function ``get()`` whose signature matches the C extension exactly.

Binary format recap
-------------------
After the ASCII header there is a "known cycle" (17 bytes) that the glider
always writes with fixed values so the reader can detect byte order:

    [0]     's'            cycle-tag byte
    [1]     <1-byte int>
    [2:4]   0x1234         two-byte uint  (little-endian if == 4660 decimal)
    [4:8]   123.456        four-byte float
    [8:16]  123456789...   eight-byte double
    [16]    'd'            separator before first real cycle

Every subsequent cycle looks like:

    <n_state_bytes>   2-bit-packed state fields (4 fields/byte, MSB first)
                      each field: UPDATED=2, SAME=1, NOTSET=0
    <data bytes>      concatenated raw values for UPDATED sensors only,
                      in ascending sensor-index order
    'd' (0x64)        separator before the next cycle's state bytes

Performance strategy
--------------------
Two-pass approach to minimise Python overhead:

Pass 1  – cheap Python loop over cycles to locate cycle boundaries.
          Uses a pre-built per-byte-position lookup table so each cycle
          costs only n_state_bytes Python ops (not n_sensors).

Pass 2  – batch numpy operations over ALL cycles at once:
          • extract state bytes for every cycle in one fancy-index read
          • decode fields and compute chunk offsets with vectorised ops
          • read sensor values for wanted sensors with vectorised byte extraction

This replaces the original approach of ~8 numpy array allocations per cycle
inside a Python loop, which dominated runtime for files with many cycles.
"""

import struct
import numpy as np


# ── constants (mirror dbdreader.h) ───────────────────────────────────────────
FILLVALUE = 1e9
UPDATED   = 2
SAME      = 1
NOTSET    = 0
_FMT_CHAR = {2: 'h', 4: 'f', 8: 'd'}   # byte-size → struct char

# Shift amounts to extract 4 × 2-bit fields from one byte (MSB first)
_SHIFTS = np.array([6, 4, 2, 0], dtype=np.int32)


# ── helpers ──────────────────────────────────────────────────────────────────

def _read_file(filename: str) -> bytes:
    """Return raw decompressed bytes for *filename* (handles .?cd/.?cg files)."""
    from dbdreader.decompress import is_compressed, Decompressor
    if is_compressed(filename):
        with Decompressor(filename) as d:
            return d.decompress()
    with open(filename, 'rb') as fh:
        return fh.read()


def _insert_ti(vi_list: list, ti: int):
    """
    Insert *ti* into sorted *vi_list* before the first element > ti,
    replicating the C code in get_variable().

    Returns (vit, nti) where vit is the extended list and nti is the index
    of ti within vit.
    """
    vit = []
    i   = 0
    while i < len(vi_list):
        if vi_list[i] > ti:
            break
        vit.append(vi_list[i])
        i += 1
    vit.append(ti)
    nti = i
    for j in range(i, len(vi_list)):
        vit.append(vi_list[j])
    return vit, nti


def _build_chunk_lut(n_state_bytes: int, n_sensors: int, bs_list: list) -> list:
    """
    Build a lookup table: lut[byte_pos][byte_value] = total data bytes
    contributed to the chunk by the four sensors encoded in that state byte.

    Used in Pass 1 to compute chunksize per cycle in O(n_state_bytes) ops.
    """
    byte_vals = np.arange(256, dtype=np.int32)
    lut = np.zeros((n_state_bytes, 256), dtype=np.int32)
    for bpos in range(n_state_bytes):
        for slot in range(4):
            sidx = bpos * 4 + slot
            if sidx >= n_sensors:
                break
            shift = 6 - slot * 2          # 6, 4, 2, 0
            states = (byte_vals >> shift) & 3          # (256,)
            lut[bpos] += (states == UPDATED) * bs_list[sidx]
    return lut.tolist()                    # nested Python list for fast indexing


# ── public API ───────────────────────────────────────────────────────────────

def get(n_state_bytes, n_sensors, bin_offset, byte_sizes,
        filename, ti, vi, return_nans, skip_initial_line, max_values_to_read):
    """
    Read one or more sensor time-series from a glider binary data file.

    Parameters match the C extension exactly:

    n_state_bytes      : int   – number of state bytes per cycle
    n_sensors          : int   – total sensors in the file
    bin_offset         : int   – byte offset to the start of binary data
    byte_sizes         : tuple – byte size for each of the n_sensors sensors
    filename           : str   – path to the data file (compressed or not)
    ti                 : int   – sensor index of the time variable
    vi                 : tuple – sorted sensor indices to retrieve
    return_nans        : int   – 1 → include NOTSET slots as FILLVALUE rows
    skip_initial_line  : int   – 1 → discard first data cycle
    max_values_to_read : int   – stop after this many rows (0 = unlimited)

    Returns
    -------
    (error_no, result) where error_no is 0 on success and result is a
    list of 2*nv lists:
        [t_0, t_1, …, t_{nv-1}, v_0, v_1, …, v_{nv-1}]
    where each t_i / v_i is a Python list of floats.
    """

    try:
        data = _read_file(filename)
    except FileNotFoundError:
        return 2, []   # ERROR_FILE_NOT_FOUND
    except Exception:
        return 1, []   # ERROR_UNEXPECTED_END_OF_FILE
    nv       = len(vi)
    bs_list  = list(byte_sizes)
    vit, nti = _insert_ti(list(vi), ti)
    nvt      = len(vit)          # = nv + 1

    # ── byte-order detection ─────────────────────────────────────────────────
    endian = '<' if struct.unpack_from('<H', data, bin_offset + 2)[0] == 4660 else '>'

    # ── numpy array of byte sizes (used in vectorised pass 2) ────────────────
    bs_arr = np.array(bs_list, dtype=np.int32)    # (n_sensors,)
    vit_arr = np.array(vit,    dtype=np.intp)     # (nvt,)

    # ── chunk-size lookup table (for pass 1) ─────────────────────────────────
    chunk_lut = _build_chunk_lut(n_state_bytes, n_sensors, bs_list)

    # ── PASS 1: locate cycle boundaries ──────────────────────────────────────
    # For each cycle record (state_bytes + data_chunk + separator):
    #   * record the file position of the state bytes
    #   * compute the data-chunk size using the lookup table
    # Cost: O(n_cycles × n_state_bytes) pure-Python ops — cheap.

    min_offset_value = -2 if return_nans else -1
    file_size        = len(data)
    pos              = bin_offset + 17      # skip known cycle
    write_data       = not bool(skip_initial_line)

    state_positions = []    # file pos of state bytes for each cycle
    chunk_sizes     = []    # data-chunk byte count for each cycle
    write_flags     = []    # whether to emit output for each cycle

    while pos < file_size:
        if pos + n_state_bytes > file_size:
            break

        # Chunksize via LUT: O(n_state_bytes) lookups
        chunksize = 0
        for bpos in range(n_state_bytes):
            chunksize += chunk_lut[bpos][data[pos + bpos]]

        state_positions.append(pos)
        chunk_sizes.append(chunksize)
        write_flags.append(write_data)

        pos        += n_state_bytes + chunksize + 1
        write_data  = True

    n_cycles = len(state_positions)
    if n_cycles == 0:
        return 0, [[] for _ in range(nv)] + [[] for _ in range(nv)]

    # ── PASS 2: vectorised processing of all cycles at once ──────────────────
    data_u8   = np.frombuffer(data, dtype=np.uint8)
    sp_arr    = np.array(state_positions, dtype=np.intp)   # (n_cycles,)
    cstart    = sp_arr + n_state_bytes                      # chunk start positions

    # Extract state bytes for ALL cycles: shape (n_cycles, n_state_bytes)
    sb_idx   = sp_arr[:, np.newaxis] + np.arange(n_state_bytes, dtype=np.intp)
    all_sb   = data_u8[sb_idx]          # uint8, (n_cycles, n_state_bytes)

    # Decode 2-bit fields: (n_cycles, n_state_bytes, 4) → (n_cycles, n_sensors)
    all_fields = ((all_sb[:, :, np.newaxis] >> _SHIFTS) & 3)   # int, (n_cycles, n_state_bytes, 4)
    all_fields = all_fields.reshape(n_cycles, n_state_bytes * 4)[:, :n_sensors]

    # Compute byte offsets within the data chunk for every sensor in every cycle.
    # UPDATED → cumulative offset; SAME → -1; NOTSET → -2.
    upd_mask  = (all_fields == UPDATED)                             # bool, (n_cycles, n_sensors)
    w_bs      = np.where(upd_mask, bs_arr[np.newaxis, :], 0)       # int32, (n_cycles, n_sensors)
    cum_bs    = np.cumsum(w_bs, axis=1)                             # int32, (n_cycles, n_sensors)
    all_off   = np.where(upd_mask, cum_bs - w_bs, np.int32(-1))    # (n_cycles, n_sensors)
    all_off   = np.where(all_fields == NOTSET, np.int32(-2), all_off)

    # Offsets for only the wanted sensors: (n_cycles, nvt)
    wanted_off = all_off[:, vit_arr]    # int32, (n_cycles, nvt)

    # ── helper: read all values for one column of wanted_off ─────────────────
    def _read_col(col: int) -> np.ndarray:
        """
        Return float64 array (n_cycles,) for wanted sensor at column *col*.
        UPDATED cycles → actual data value.
        SAME cycles    → carry-forward of last UPDATED value (numpy ffill).
        NOTSET cycles  → NaN (or FILLVALUE if return_nans).
        """
        sidx    = vit[col]
        bs      = bs_list[sidx]
        offsets = wanted_off[:, col]            # int32, (n_cycles,)
        vals    = np.full(n_cycles, np.nan, dtype=np.float64)

        upd = np.where(offsets >= 0)[0]        # indices of UPDATED cycles
        if upd.size:
            abs_pos = cstart[upd] + offsets[upd].astype(np.intp)

            if bs == 1:
                raw = data_u8[abs_pos].view(np.int8).astype(np.float64)
                vals[upd] = raw
            else:
                # Gather bs consecutive bytes for each updated cycle,
                # reinterpret as the sensor's native type.
                bidx = abs_pos[:, np.newaxis] + np.arange(bs, dtype=np.intp)
                raw  = data_u8[bidx].tobytes()          # flat byte buffer
                dt   = np.dtype(endian + _FMT_CHAR[bs])
                vals[upd] = np.frombuffer(raw, dtype=dt)

        # Forward-fill: propagate each UPDATED value into subsequent SAME slots.
        # Classic numpy trick: build an index array that "sticks" at the last
        # non-NaN position, then use it to index vals.
        has_val = ~np.isnan(vals)
        ff_idx  = np.where(has_val, np.arange(n_cycles, dtype=np.intp), np.intp(0))
        np.maximum.accumulate(ff_idx, out=ff_idx)
        vals = vals[ff_idx]

        # NOTSET cycles: mark as FILLVALUE (if return_nans) or leave as
        # carried-forward value (which will be excluded by the mask below).
        if return_nans:
            vals[offsets == np.int32(-2)] = FILLVALUE

        return vals

    # ── read time and sensor values ───────────────────────────────────────────
    t_vals = _read_col(nti)                     # (n_cycles,) float64
    write_arr = np.array(write_flags, dtype=bool)

    result_t = [None] * nv
    result_v = [None] * nv

    for col in range(nvt):
        if col == nti:
            continue
        j = col - (1 if col > nti else 0)      # output index in result_t/v

        v_vals   = _read_col(col)
        v_off    = wanted_off[:, col]

        # Include this cycle in output if:
        #   • write_flags says so (skip_initial_line handling)
        #   • sensor has a valid offset (UPDATED or SAME; also NOTSET if return_nans)
        include  = (v_off >= min_offset_value)
        mask     = write_arr & include

        if max_values_to_read > 0:
            keep = np.where(mask)[0]
            if keep.size > max_values_to_read:
                mask          = np.zeros(n_cycles, dtype=bool)
                mask[keep[:max_values_to_read]] = True

        result_t[j] = t_vals[mask].tolist()
        result_v[j] = v_vals[mask].tolist()

    return 0, [result_t[j] for j in range(nv)] + [result_v[j] for j in range(nv)]
