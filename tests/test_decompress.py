import sys
sys.path.insert(0, '../')

import os
from hashlib import md5

if not __name__ == '__main__':
    from pytest import fixture
else:
    def fixture(func):
        def inner():
            return func()
        return inner

import pytest
import numpy as np

import dbdreader
from dbdreader.decompress import *


@fixture
def load_verification_data():
    filename_verify = '../dbdreader/data/01600000.mlg'
    with open(filename_verify, 'r') as fp:
        data = fp.read()
    return data
        
# Open a file and lazy read block by block. Compares with 
# uncompressed file
#
def test_read_file(load_verification_data):
    verification_data = load_verification_data
    filename = '../dbdreader/data/01600000.mcg'
    data = b''
    with Decompressor(filename) as d:
        for block in d.decompressed_blocks():
            data += block
    assert data.decode('ascii') == verification_data

# Open a file and decompress whole file. Compares with 
# uncompressed file
#
def test_read_file_in_memory(load_verification_data):
    verification_data = load_verification_data
    filename = '../dbdreader/data/01600000.mcg'
    with Decompressor(filename) as d:
        data = d.decompress()
    assert data.decode('ascii') == verification_data

# Open a file and decompress first block only. 
# 
#
def test_read_file_one_block_only():
    filename = '../dbdreader/data/01600000.mcg'
    with Decompressor(filename) as d:
        blocks = [block for block in d.decompressed_blocks(n=1)]
    assert len(blocks) == 1

# Open a file and lazy read block by block. Compares with 
# uncompressed file. Instead of using with statement, open file
# explicitly
def test_read_file_explicit_file_opener(load_verification_data):
    verification_data = load_verification_data
    filename = '../dbdreader/data/01600000.mcg'
    data = b''
    d = Decompressor()
    with open(filename, 'rb') as fp:
        for block in d.decompressed_blocks(fp=fp):
            data += block
    assert data.decode('ascii') == verification_data

# Open a file and decompress whole file. Compares with 
# uncompressed file. Instead of using with statement, open file
# explicitly
def test_read_file_in_memory_explicit_file_opener(load_verification_data):
    verification_data = load_verification_data
    filename = '../dbdreader/data/01600000.mcg'
    d = Decompressor()
    with open(filename, 'rb') as fp:
        data = d.decompress(fp=fp)
    assert data.decode('ascii') == verification_data

# using the convenience function decompress_file
def test_convenience_function():
    filename = '../dbdreader/data/01600000.dcd'
    filename_decompressed = filename.replace('dcd','dbd')
    try:
        os.unlink(filename_decompressed)
    except:
        pass
    decompress_file(filename)
    assert os.path.exists(filename_decompressed)
    with open(filename_decompressed, 'rb') as fp:
        data_decompressed = fp.read()
    try:
        os.unlink(filename_decompressed)
    except:
        pass
    assert md5(data_decompressed).hexdigest() == 'f6935ba8307efb29dcb16fb2429e167d'

# Test whether all extensions are translated correctly.
def test_extension_generator():
    fd = FileDecompressor()
    s = fd._generate_filename_for_output('01600000.dcd')
    assert s == '01600000.dbd'
    infiles = ['../dbdreader/data/01600000.dcd',
               '../dbdreader/data/01600000.ecd',
               '../dbdreader/data/01600000.mcd',
               '../dbdreader/data/01600000.mcg',
               '../dbdreader/data/01600000.ncd',
               '../dbdreader/data/01600000.ncg',
               '../dbdreader/data/01600000.scd',
               '../dbdreader/data/01600000.tcd',
               '../dbdreader/data/00aa00aa.ccc']
    outfiles = ['../dbdreader/data/01600000.dbd',
               '../dbdreader/data/01600000.ebd',
               '../dbdreader/data/01600000.mbd',
               '../dbdreader/data/01600000.mlg',
               '../dbdreader/data/01600000.nbd',
               '../dbdreader/data/01600000.nlg',
               '../dbdreader/data/01600000.sbd',
                '../dbdreader/data/01600000.tbd',
                '../dbdreader/data/00aa00aa.cac']
    for a, b in zip(infiles, outfiles):
        assert fd._generate_filename_for_output(a) == b

# Test behaviour for invalid file.
def test_extension_generator_with_invalid_extension():
    fd = FileDecompressor()
    with pytest.raises(ValueError):
        s = fd._generate_filename_for_output('01600000.cd')


        
# Open a file and lazy read block by block. Check cac filesCompares with 
# uncompressed file
#
def test_read_ccc_file():
    with open('../dbdreader/data/cac/06a36d4e.cac', 'r') as fp:
        verification_data = fp.read()
    filename = '../dbdreader/data/cac/06a36d4e.ccc'
    data = b''
    with Decompressor(filename) as d:
        for block in d.decompressed_blocks():
            data += block
    assert data.decode('ascii') == verification_data

# Using the CompressedFile object to read a compressed text file
def test_CompressedFile(load_verification_data):
    verification_data = load_verification_data
    filename = '../dbdreader/data/01600000.mcg'
    lines = []
    with CompressedFile(filename) as fd:
        while True:
            line = fd.readline()
            if not line:
                break
            lines.append(line)
        data = b"".join(lines)
    assert data.decode('ascii') == verification_data

# Using the CompressedFile object to read a compressed text file, using readlines() method.
def test_CompressedFileReadlines(load_verification_data):
    verification_data = load_verification_data
    filename = '../dbdreader/data/01600000.mcg'
    with CompressedFile(filename) as fd:
        lines = fd.readlines()
        data = b"".join(lines)
    assert data.decode('ascii') == verification_data

    
    
# Test reading of data/01600001.dcd and check it is identical to data/01600001.dbd
def test_read_compressed_file_C_code():
    compressed_filename = '../dbdreader/data/01600001.dcd'
    regular_filename = '../dbdreader/data/01600001.dbd'
    compressed_dbd = dbdreader.DBD(compressed_filename, cacheDir='../dbdreader/data/cac')
    regular_dbd = dbdreader.DBD(regular_filename, cacheDir='../dbdreader/data/cac')
    compressed_data = compressed_dbd.get("m_depth")
    regular_data = regular_dbd.get("m_depth")
    assert np.all(compressed_data[0]==regular_data[0]) and np.all(compressed_data[1]==regular_data[1])
    
# Test reading of data/0160000?.dcd MultiDBD
def test_read_compressed_files_C_code():
    pattern = '../dbdreader/data/0160000?.dcd'
    dbd = dbdreader.MultiDBD(pattern, cacheDir='../dbdreader/data/cac')
    t, d = dbd.get("m_depth")
    assert t.ptp() == pytest.approx(2511.95, 0.01)


# Test missing cac file for single dbd_label
def test_missing_cac_file_for_single_compressed_file():
    try:
        os.unlink('../dbdreader/data/cac/daad1b20.cac')
    except:
        pass
    
    with pytest.raises(dbdreader.DbdError):
        dbd = dbdreader.DBD('../dbdreader/data/01600000.ecd', cacheDir='../dbdreader/data/cac')

# Test missing cac file being created from ccc file for MultiDBD
def test_missing_cac_file_for_compressed_file_multidbd():
    try:
        os.unlink('../dbdreader/data/cac/daad1b20.cac')
    except:
        pass
    
    dbd = dbdreader.MultiDBD('../dbdreader/data/0160000?.ecd', cacheDir='../dbdreader/data/cac')
    assert os.path.exists('../dbdreader/data/cac/daad1b20.cac')


# Test we can open compressed flight and science files.
def test_open_flight_and_science_files():
    dbd = dbdreader.MultiDBD('../dbdreader/data/0160000?.?cd', cacheDir='../dbdreader/data/cac')

# Test we can open compressed flight and science files.
def test_open_flight_and_science_files_finding_complement_files():
    dbd = dbdreader.MultiDBD('../dbdreader/data/0160000?.dcd', complement_files=True, cacheDir='../dbdreader/data/cac')

    

    
        
