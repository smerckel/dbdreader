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
    
from functools import partial
import numpy as np
import pytest


import dbdreader
dbdreader.DBDCache.set_cachedir('../dbdreader/data/cac')

def test_multidbd_get_sync():
    ''' Test normal behaviour. Temperature should return all values, and oxygen has 10 leading nans'''
    dbd = dbdreader.MultiDBD('../dbdreader/data/hal_1002-2024-183-4-?.tbd')
    sensors=['sci_water_temp', 'sci_oxy4_oxygen']
    t, x, y = dbd.get_sync(*sensors)
    assert np.all(np.isnan(y[:10])) and np.isclose(x.mean(), 7.518728574117024)

def test_multidbd_get_sync_heading():
    ''' Test using interp1d and interpolate heading properly'''
    dbd = dbdreader.MultiDBD('../dbdreader/data/sebastian*.?bd')
    sensors=['sci_water_temp', 'm_heading']
    t, x, y = dbd.get_sync(*sensors, interpolating_function_factory=dbdreader.heading_interpolating_function_factory)
    assert len(y.compress(np.logical_and(y>3, y<5)))==0 # there should be no values in this range
    assert np.isclose(x.mean(), 16.568510801834467)

def test_multidbd_get_sync_specific_iff_handling():
    ''' Test using interpolating function for specific parameter'''
    dbd = dbdreader.MultiDBD('../dbdreader/data/sebastian*.?bd')
    sensors=['sci_water_temp', 'sci_bb3slo_b470_scaled', 'm_heading']
    interpolating_function_factory = dict(m_heading=dbdreader.heading_interpolating_function_factory)
    t, x, y, z = dbd.get_sync(*sensors, interpolating_function_factory=interpolating_function_factory)
    print(len(x))
    assert len(z.compress(np.logical_and(z>3, z<5)))==0 # there should be no values in this range
    assert np.isclose(x.mean(), 16.568510801834467)
    assert np.isclose(y.mean(), 0.0019145932901356323)


def test_multidbd_get_xy_heading():
    ''' Test whether custom interpolation works for get_xy() method.'''
    dbd = dbdreader.MultiDBD('../dbdreader/data/sebastian*.?bd')
    sensors=['sci_water_temp', 'm_heading']
    x, y = dbd.get_xy(*sensors, interpolating_function_factory=dbdreader.heading_interpolating_function_factory)
    assert len(y.compress(np.logical_and(y>3, y<5)))==0 # there should be no values in this range
    assert np.isclose(x.mean(), 16.568510801834467)

def test_multidbd_get_CTD_sync_heading_all_parameters():
    ''' Test the implementation of a custom interpolation scheme for get_CTD, using heading interpolation for all parameters'''
    dbd = dbdreader.MultiDBD('../dbdreader/data/sebastian*.?bd')
    sensors=['m_heading']
    tctd, C, T, D, y = dbd.get_CTD_sync(*sensors, interpolating_function_factory=dbdreader.heading_interpolating_function_factory)
    assert len(y.compress(np.logical_and(y>3, y<5)))==0 # there should be no values in this range
    assert np.all(T<2*np.pi) # all T values should be clipped below 2 pi.

def test_multidbd_get_CTD_sync_heading():
    ''' Test the implementation of a custom interpolation scheme for get_CTD, using heading interpolation for all parameters'''
    dbd = dbdreader.MultiDBD('../dbdreader/data/sebastian*.?bd')
    sensors=['m_heading']
    iff_dict = dict(m_heading=dbdreader.heading_interpolating_function_factory)
    tctd, C, T, D, y = dbd.get_CTD_sync(*sensors, interpolating_function_factory=iff_dict)
    assert len(y.compress(np.logical_and(y>3, y<5)))==0 # there should be no values in this range
    assert np.isclose(T.mean(), 16.572957188641585) # this is slightly different from other tests, because some values are dropped in get_CTD_sync.
        
