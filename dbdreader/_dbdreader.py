"""
Pure Python/NumPy replacement for the _dbdreader C extension.

Reads Slocum glider binary DBD/SBD/MBD/etc. files.  The public API is a
single function ``get()`` whose signature matches the C extension exactly.

Binary file format
------------------
After the ASCII header the file contains a fixed-layout "known cycle" (17
bytes) that the glider always writes with known values so the reader can
detect byte order.  Every subsequent record ("cycle") holds one sample
from the glider and looks like:

    [ state bytes ]   n_state_bytes of 2-bit-packed status fields.
                      Each byte encodes the status of 4 sensors (MSB first);
                      each 2-bit field is one of:
                          UPDATED (2) – sensor has a new value this cycle
                          SAME    (1) – sensor value is unchanged since last UPDATED
                          NOTSET  (0) – sensor has never been set
    [ data bytes  ]   raw sensor values, concatenated in ascending sensor-index
                      order, for UPDATED sensors only.
    [ 0x64 'd'    ]   one separator byte before the next cycle's state bytes.

The number of data bytes in a cycle varies: it is the sum of the byte sizes
of all UPDATED sensors in that cycle.

Performance strategy
--------------------
Reading many files is split into two passes per file:

Pass 1 – scan the file sequentially to find the byte position of each cycle.
         Each cycle's length depends on which sensors were updated, so this
         is inherently sequential.  The per-cycle cost is computing the data
         chunk size from the state bytes:

           chunk_size = sum(byte_size[sensor]  for each UPDATED sensor)

         A precomputed lookup table (chunk_lut) maps each state-byte value
         to the total data bytes it contributes, so chunk_size reduces to
         n_state_bytes table lookups per cycle.

         For files with many sensors (n_state_bytes ≥ 32, i.e. ≥ ~128
         sensors) those lookups are batched into a single numpy fancy-index
         call, which is ~7× faster than an equivalent Python loop at
         n_state_bytes = 424 (1696-sensor files).

Pass 2 – once all cycle positions are known, extract sensor values with
         vectorised numpy operations across all cycles at once.  Only sensors
         up to the highest-indexed requested sensor are decoded; this avoids
         unnecessary work when only a few low-index sensors are requested
         from a file that defines hundreds.
"""

import struct
import numpy as np


# ── Sensor state codes ────────────────────────────────────────────────────────
UPDATED  = 2   # sensor wrote a new value this cycle
SAME     = 1   # sensor value carried forward from last UPDATED cycle
NOTSET   = 0   # sensor has never been set

FILLVALUE = 1e9   # placeholder for NOTSET slots when return_nans is set

# Struct format character for each supported sensor byte width
_STRUCT_FMT = {2: 'h', 4: 'f', 8: 'd'}

# Bit shifts to extract the four 2-bit status fields from one state byte (MSB first)
_FIELD_SHIFTS = np.array([6, 4, 2, 0], dtype=np.int32)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _read_file(filename: str) -> bytes:
    """Return the raw (decompressed) bytes of a DBD file.

    Handles both plain binary files and lz4-compressed files (.?cd/.?cg).
    """
    from dbdreader.decompress import is_compressed, Decompressor
    if is_compressed(filename):
        with Decompressor(filename) as d:
            return d.decompress()
    with open(filename, 'rb') as fh:
        return fh.read()


def _insert_time_sensor(sensor_indices: list, time_index: int):
    """Insert the time sensor index into a sorted list of sensor indices.

    The time sensor must be decoded alongside the requested sensors so that
    each returned value can be paired with a timestamp.  It is inserted in
    sorted order (matching the behaviour of the original C implementation).

    Returns
    -------
    combined : list
        sensor_indices with time_index inserted in sorted position.
    time_pos : int
        position of time_index within combined.
    """
    combined = []
    insert_pos = 0
    for i, idx in enumerate(sensor_indices):
        if idx > time_index:
            break
        combined.append(idx)
        insert_pos = i + 1
    combined.append(time_index)
    combined.extend(sensor_indices[insert_pos:])
    return combined, insert_pos


def _build_chunk_size_lut(n_state_bytes: int, n_sensors: int,
                          sensor_byte_sizes: list) -> list:
    """Build a lookup table for computing data chunk sizes from state bytes.

    Each cycle contains a variable-length data chunk whose size depends on
    which sensors were UPDATED.  Rather than inspecting each sensor's status
    field individually, this table lets us look up the total contribution of
    one state byte in O(1):

        chunk_size = sum(lut[byte_position][byte_value]
                        for byte_position in range(n_state_bytes))

    Returns a nested Python list (not a numpy array) so that inner-loop
    indexing stays in fast Python list-access territory for small files.
    """
    all_byte_values = np.arange(256, dtype=np.int32)
    lut = np.zeros((n_state_bytes, 256), dtype=np.int32)

    for byte_pos in range(n_state_bytes):
        for slot in range(4):
            sensor_idx = byte_pos * 4 + slot
            if sensor_idx >= n_sensors:
                break
            # Extract the 2-bit status field for this sensor from each possible
            # byte value, then add the sensor's byte size for any UPDATED case.
            shift = 6 - slot * 2          # slots 0-3 → shifts 6, 4, 2, 0
            status = (all_byte_values >> shift) & 3
            lut[byte_pos] += (status == UPDATED) * sensor_byte_sizes[sensor_idx]

    return lut.tolist()   # nested Python list for fast per-element access


# ── Public API ────────────────────────────────────────────────────────────────

def get(n_state_bytes, n_sensors, bin_offset, byte_sizes,
        filename, ti, vi, return_nans, skip_initial_line, max_values_to_read):
    """Read one or more sensor time-series from a glider binary data file.

    Parameters
    ----------
    n_state_bytes : int
        Number of state bytes per cycle (= ceil(n_sensors / 4)).
    n_sensors : int
        Total number of sensors defined in the file header.
    bin_offset : int
        Byte offset from the start of the file to the binary data section.
    byte_sizes : tuple of int
        Byte width of each sensor's value (indexed by sensor index).
    filename : str
        Path to the data file; may be lz4-compressed.
    ti : int
        Sensor index of the time variable.
    vi : tuple of int
        Sorted sensor indices to retrieve (not including ti).
    return_nans : int
        If 1, include NOTSET cycles as rows with value FILLVALUE (1e9).
    skip_initial_line : int
        If 1, discard the first data cycle (standard glider convention).
    max_values_to_read : int
        Cap the number of returned rows per sensor (0 = no limit).

    Returns
    -------
    (error_code, result)
        error_code is 0 on success.  result is a flat list of 2*len(vi) lists:
            [timestamps_0, …, timestamps_n, values_0, …, values_n]
        where timestamps_i and values_i correspond to vi[i].
    """

    # ── Read file ─────────────────────────────────────────────────────────────
    try:
        raw_bytes = _read_file(filename)
    except FileNotFoundError:
        return 2, []
    except Exception:
        return 1, []

    n_requested         = len(vi)
    sensor_byte_sizes   = list(byte_sizes)

    # Build the combined sensor list: requested sensors + time sensor in sorted order.
    # We decode the time sensor alongside the data sensors so values can be paired
    # with timestamps at the end.
    sensors_with_time, time_col = _insert_time_sensor(list(vi), ti)
    n_sensors_with_time         = len(sensors_with_time)   # = n_requested + 1

    # ── Byte-order detection ──────────────────────────────────────────────────
    # The known cycle contains a 2-byte value 0x1234; if it reads as 4660
    # (decimal) in little-endian, the file is little-endian.
    endian = '<' if struct.unpack_from('<H', raw_bytes, bin_offset + 2)[0] == 4660 else '>'

    # ── Precompute arrays used in both passes ─────────────────────────────────
    byte_size_arr  = np.array(sensor_byte_sizes, dtype=np.int32)  # (n_sensors,)
    wanted_idx_arr = np.array(sensors_with_time, dtype=np.intp)   # (n_sensors_with_time,)

    # Zero-copy uint8 view of the raw bytes — used for all byte-level reads.
    file_bytes = np.frombuffer(raw_bytes, dtype=np.uint8)
    file_size  = len(raw_bytes)

    # ── Build chunk-size lookup table ─────────────────────────────────────────
    chunk_size_lut = _build_chunk_size_lut(n_state_bytes, n_sensors, sensor_byte_sizes)

    # ── PASS 1: locate the byte position of every cycle ───────────────────────
    #
    # Walk through the file one cycle at a time.  Each cycle starts with
    # n_state_bytes status bytes; their values determine how many data bytes
    # follow.  We record each cycle's start position so Pass 2 can extract
    # sensor values for all cycles at once with vectorised numpy.
    #
    # Two strategies for computing the per-cycle chunk size:
    #
    #   Python list lookups  – fast for small n_state_bytes (few sensors).
    #
    #   Numpy fancy-index    – faster when n_state_bytes is large; replaces
    #                          n_state_bytes Python iterations with one numpy
    #                          call.  Break-even is ~40 state bytes; at 424
    #                          (1696-sensor files) numpy is ~7× faster.
    NUMPY_INNER_LOOP_THRESHOLD = 32   # state bytes (~128 sensors)

    # skip_initial_line: the first cycle after the known cycle is normally
    # excluded because glider firmware writes it with carry-over values from
    # the previous file.
    emit_this_cycle = not bool(skip_initial_line)
    pos             = bin_offset + 17   # skip the 17-byte known cycle

    cycle_positions = []   # start position of each cycle's state bytes
    emit_flags      = []   # whether to include each cycle in output

    if n_state_bytes >= NUMPY_INNER_LOOP_THRESHOLD:
        # Numpy path: one fancy-index lookup across all state bytes at once.
        chunk_size_lut_np = np.array(chunk_size_lut, dtype=np.int32)
        state_byte_indices = np.arange(n_state_bytes, dtype=np.intp)

        while pos < file_size:
            if pos + n_state_bytes > file_size:
                break
            state_bytes = file_bytes[pos : pos + n_state_bytes]
            chunk_size  = int(chunk_size_lut_np[state_byte_indices, state_bytes].sum())
            cycle_positions.append(pos)
            emit_flags.append(emit_this_cycle)
            pos            += n_state_bytes + chunk_size + 1
            emit_this_cycle = True
    else:
        # Python path: simple list indexing, faster for small n_state_bytes.
        while pos < file_size:
            if pos + n_state_bytes > file_size:
                break
            chunk_size = 0
            for byte_pos in range(n_state_bytes):
                chunk_size += chunk_size_lut[byte_pos][raw_bytes[pos + byte_pos]]
            cycle_positions.append(pos)
            emit_flags.append(emit_this_cycle)
            pos            += n_state_bytes + chunk_size + 1
            emit_this_cycle = True

    n_cycles = len(cycle_positions)
    if n_cycles == 0:
        return 0, [[] for _ in range(n_requested)] * 2

    # ── PASS 2: extract sensor values across all cycles at once ───────────────
    cycle_start_arr  = np.array(cycle_positions, dtype=np.intp)    # (n_cycles,)
    data_start_arr   = cycle_start_arr + n_state_bytes             # first data byte of each cycle
    emit_arr         = np.array(emit_flags, dtype=bool)

    # We only need to decode sensors up to the highest-indexed requested sensor.
    # The byte-offset computation (cumsum below) is correct when truncated this
    # way because only sensors with lower indices contribute to the offset of a
    # given sensor within the data chunk.
    max_sensor_needed   = int(wanted_idx_arr.max()) + 1            # ≤ n_sensors
    n_state_bytes_needed = (max_sensor_needed + 3) // 4           # ceil(max_sensor_needed/4)

    # Gather state bytes for every cycle, for the sensors we care about.
    # Result shape: (n_cycles, n_state_bytes_needed)
    state_byte_col_offsets = np.arange(n_state_bytes_needed, dtype=np.intp)
    state_byte_positions   = cycle_start_arr[:, np.newaxis] + state_byte_col_offsets
    all_state_bytes        = file_bytes[state_byte_positions]

    # Decode 2-bit status fields.
    # all_state_bytes shape: (n_cycles, n_state_bytes_needed)
    # After broadcasting _FIELD_SHIFTS: (n_cycles, n_state_bytes_needed, 4)
    # After reshape and truncation: (n_cycles, max_sensor_needed)
    all_status_fields = ((all_state_bytes[:, :, np.newaxis] >> _FIELD_SHIFTS) & 3)
    all_status_fields = all_status_fields.reshape(n_cycles, n_state_bytes_needed * 4)
    all_status_fields = all_status_fields[:, :max_sensor_needed]

    # Compute each sensor's byte offset within its cycle's data chunk.
    # For UPDATED sensors the offset is the cumulative sum of byte sizes for
    # all preceding UPDATED sensors in the same cycle.
    # SAME    → -1  (value will be forward-filled from the last UPDATED cycle)
    # NOTSET  → -2  (no value ever; excluded from output or filled with FILLVALUE)
    is_updated  = (all_status_fields == UPDATED)                              # (n_cycles, max_sensor_needed)
    update_sizes = np.where(is_updated,
                            byte_size_arr[:max_sensor_needed][np.newaxis, :],
                            0)                                                # (n_cycles, max_sensor_needed)
    cumulative_sizes = np.cumsum(update_sizes, axis=1)                       # (n_cycles, max_sensor_needed)
    byte_offsets = np.where(is_updated, cumulative_sizes - update_sizes,
                            np.int32(-1))                                     # (n_cycles, max_sensor_needed)
    byte_offsets = np.where(all_status_fields == NOTSET,
                            np.int32(-2), byte_offsets)

    # Select only the columns for sensors we actually want (time + requested).
    wanted_offsets = byte_offsets[:, wanted_idx_arr]   # (n_cycles, n_sensors_with_time)

    # ── Helper: decode all values for one sensor column ───────────────────────
    def _decode_sensor_column(col_index: int) -> np.ndarray:
        """Return a float64 array of length n_cycles for sensors_with_time[col_index].

        UPDATED cycles carry the raw sensor value.
        SAME cycles carry the most recent UPDATED value (forward-fill).
        NOTSET cycles are NaN, or FILLVALUE if return_nans is set.
        """
        sensor_idx   = sensors_with_time[col_index]
        n_bytes      = sensor_byte_sizes[sensor_idx]
        offsets      = wanted_offsets[:, col_index]       # (n_cycles,)
        values       = np.full(n_cycles, np.nan, dtype=np.float64)

        updated_cycles = np.where(offsets >= 0)[0]
        if updated_cycles.size:
            # Absolute byte position of this sensor's value in each UPDATED cycle.
            abs_positions = data_start_arr[updated_cycles] + offsets[updated_cycles].astype(np.intp)

            if n_bytes == 1:
                values[updated_cycles] = file_bytes[abs_positions].view(np.int8).astype(np.float64)
            else:
                # Gather n_bytes consecutive bytes for each updated cycle and
                # reinterpret them as the sensor's native numeric type.
                byte_indices = abs_positions[:, np.newaxis] + np.arange(n_bytes, dtype=np.intp)
                raw_buffer   = file_bytes[byte_indices].tobytes()
                dtype        = np.dtype(endian + _STRUCT_FMT[n_bytes])
                values[updated_cycles] = np.frombuffer(raw_buffer, dtype=dtype)

        # Forward-fill: carry each UPDATED value forward through subsequent
        # SAME cycles.  The trick is to build an index array where SAME and
        # NOTSET positions point back to the most recent UPDATED position.
        has_value = ~np.isnan(values)
        fill_idx  = np.where(has_value, np.arange(n_cycles, dtype=np.intp), np.intp(0))
        np.maximum.accumulate(fill_idx, out=fill_idx)
        values = values[fill_idx]

        if return_nans:
            values[offsets == np.int32(-2)] = FILLVALUE

        return values

    # ── Decode time column and all requested sensor columns ───────────────────
    # min_valid_offset: threshold for "this cycle has a usable value".
    # With return_nans=True we include NOTSET (-2); otherwise only UPDATED/SAME (-1 or ≥0).
    min_valid_offset = -2 if return_nans else -1

    time_values = _decode_sensor_column(time_col)

    out_timestamps = [None] * n_requested
    out_values     = [None] * n_requested

    for col in range(n_sensors_with_time):
        if col == time_col:
            continue
        # Map col back to an output index, skipping the time column.
        out_idx = col - (1 if col > time_col else 0)

        sensor_values  = _decode_sensor_column(col)
        sensor_offsets = wanted_offsets[:, col]

        # A cycle is included in the output for this sensor if:
        #   • it is not the skipped initial line, AND
        #   • the sensor has a value (UPDATED or SAME, or NOTSET when return_nans)
        has_value = (sensor_offsets >= min_valid_offset)
        output_mask = emit_arr & has_value

        if max_values_to_read > 0:
            keep = np.where(output_mask)[0]
            if keep.size > max_values_to_read:
                output_mask = np.zeros(n_cycles, dtype=bool)
                output_mask[keep[:max_values_to_read]] = True

        out_timestamps[out_idx] = time_values[output_mask].tolist()
        out_values[out_idx]     = sensor_values[output_mask].tolist()

    return 0, out_timestamps + out_values
