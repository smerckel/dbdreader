#import sys
#sys.path.insert(0, '../')

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
dbdreader.DBDCache.set_cachedir('dbdreader/data/cac')


def test_open():
    dbd = dbdreader.DBD("dbdreader/data/amadeus-2014-204-05-000.sbd")
    v=dbd.get("m_depth")
    assert len(v)==2 and len(v[0])>0
    
def test_get_non_existing_variable():
    dbd = dbdreader.DBD("dbdreader/data/amadeus-2014-204-05-000.sbd")
    v=dbd.get("sci_water_pressure")
    assert len(v)==2 and len(v[0])==0

def test_get_invalid_variable():
    dbd = dbdreader.DBD("dbdreader/data/amadeus-2014-204-05-000.sbd")
    with pytest.raises(dbdreader.DbdError) as e:
        v=dbd.get("sci_pressure")
    assert e.value.value == dbdreader.DBD_ERROR_NO_VALID_PARAMETERS
    
def test_get_sync():
    dbd = dbdreader.DBD("dbdreader/data/amadeus-2014-204-05-000.sbd")
    v=dbd.get_sync("m_depth",'m_lat','m_lon')
    checks = [len(v[i]) == len(v[0]) for i in range(1,4)]
    assert len(v)==4 and len(v[0]==67) and all(checks)

    
def test_get_sync_non_existing_variable():
    dbd = dbdreader.DBD("dbdreader/data/amadeus-2014-204-05-000.sbd")
    v=dbd.get_sync("m_depth",'sci_water_pressure','m_lon')
    checks = [len(v[i]) == len(v[0]) for i in range(1,4)]
    assert len(v)==4 and len(v[0]==67) and all(checks) and np.all(np.isnan(v[2]))

def test_get_sync_invalid_variable():
    dbd = dbdreader.DBD("dbdreader/data/amadeus-2014-204-05-000.sbd")
    with pytest.raises(dbdreader.DbdError) as e:
        v=dbd.get_sync("m_depth",'sci_pressure','m_lon')
    assert e.value.value == dbdreader.DBD_ERROR_NO_VALID_PARAMETERS
    

def test_get_sync_obselete():
    dbd=dbdreader.DBD("dbdreader/data/amadeus-2014-204-05-000.sbd")
    x = dbd.get_sync("m_depth", ['m_lat','m_lon'])
    y = dbd.get_sync("m_depth", 'm_lat','m_lon')
    assert all([np.all(i.compress(np.isfinite(i))==j.compress(np.isfinite(j))) for i,j in zip(x,y)])

def test_get_xy():
    dbd=dbdreader.DBD("dbdreader/data/amadeus-2014-204-05-000.sbd")
    x,y = dbd.get_xy('m_lat','m_lon')
    assert np.allclose(x, np.array([54.26715942, 54.26802426])) and np.allclose(y, np.array([7.41679603, 7.42362288]))


def test_get_list():
    dbd=dbdreader.DBD("dbdreader/data/amadeus-2014-204-05-000.sbd")
    x, y = dbd.get_list("m_lat", "m_lon")
    xp, yp = dbd.get("m_lat", "m_lon")
    assert np.allclose(x[1], xp[1]) and np.allclose(y[1], yp[1])
    

def test_file_open_time():
    dbd=dbdreader.DBD("dbdreader/data/amadeus-2014-204-05-000.sbd")
    t=dbd.get_fileopen_time()
    assert t == 1406221414

def test_get_mission_name():
    dbd=dbdreader.DBD("dbdreader/data/amadeus-2014-204-05-000.sbd")
    t=dbd.get_mission_name()
    assert t == "micro.mi"

def test_non_standard_cache_dir():
    dbd=dbdreader.DBD("dbdreader/data/amadeus-2014-204-05-000.sbd", cacheDir='dbdreader/data/cac')
    depth = dbd.get("m_depth")
    assert len(depth) == 2


def test_non_standard_cache_dir_generate_cachefile():
    # this should create a cache file. Remove it if already present.
    try:
        os.unlink('dbdreader/data/cac/(813b137d.cac')
    except FileNotFoundError:
        pass
    dbd=dbdreader.DBD("dbdreader/data/ammonite-2008-028-01-000.mbd", cacheDir='dbdreader/data/cac')
    depth = dbd.get("m_depth")
    assert len(depth) == 2

def test_G3S_data_file():
     # Reading a G3S data file for which the byte order needs to be swapped
    dbd = dbdreader.DBD("dbdreader/data/unit_887-2021-321-3-0.sbd",
                        cacheDir='dbdreader/data/cac')
    tm, depth = dbd.get("m_depth")
    assert np.allclose(depth.max(),34.45457458496094)
        
def test_missing_cache_file():
    # Throw an error when cache file is missing...
    with pytest.raises(dbdreader.DbdError) as e:
        dbd = dbdreader.DBD("dbdreader/data/hal_1002-2024-183-4-4.sbd")
    assert e.value.value == dbdreader.DBD_ERROR_CACHE_NOT_FOUND
    

def test_donottest_non_standard_cache_dir_fail():
     # non_standard_cache_dir_fail 
    kwds = dict(cacheDir='dbdreader/data/not_there')
    with pytest.raises(dbdreader.DbdError) as e:
        dbd = dbdreader.DBD("dbdreader/data/amadeus-2014-204-05-000.sbd", **kwds)

def test_missing_cache_file_data_feature():
     # Throw an error when cache file is missing, and check who is missing.
        try:
            dbd = dbdreader.DBD("dbdreader/data/unit_887-2021-321-3-0.sbd")
        except dbdreader.DbdError as e:
            data = e.data
            for k,v in data.missing_cache_files.items():
                assert k == 'd6f44165' and v[0] == "dbdreader/data/unit_887-2021-321-3-0.sbd"


    # def test_handling_inf(self):
    #     dbd = dbdreader.DBD("dbdreader/data/amadeus-2014-204-05-000.dbd",
    #                         cacheDir="dbdreader/data/cac")

    #     t, v = dbd.get("m_time_til_wpt", return_nans =True)
    #     t = t[:24]
    #     v = v[:24]
    #     # Now read the output by dbd2asc
    #     with open("dbdreader/data/dbd2asc_output.txt") as fp:
    #         lines = fp.readlines()
    #     lines.pop(0) # remark
    #     tp = np.zeros_like(t)
    #     vp = np.zeros_like(t)
    #     for i, line in enumerate(lines):
    #         _x, _y = line.strip().split()
    #         tp[i] = _x
    #         vp[i] = _y
    #     #for a,b,c,d in zip(t, tp, v, vp):
    #     #    print(f"{a:16f} {b:16f}    {c:16f} {d:16f}")
    #     condition1 = np.isclose(t, tp)
    #     condition3 = np.isfinite(vp)
    #     condition2 = np.isclose(v, vp).compress(condition3)
    #     assert np.all(condition1) and np.all(condition2)

    # def test_get_sync_on_parameter_without_values(self):
    #     print("Reads in a parameter to sync that has no values.")
    #     dbd = dbdreader.DBD("dbdreader/data/sebastian-2014-204-05-001.dbd")
    #     _, _, x = dbd.get_sync("m_depth", "u_dbd_sensor_list_xmit_control")
    #     assert np.all(np.isfinite(x)==False)


    # def test_get_reading_initial_data_line(self):
    #     print("Tests whether initial data line can be read if requested.")
        
    #     dbd = dbdreader.DBD("dbdreader/data/sebastian-2014-204-05-001.dbd")
    #     t0, v0 = dbd.get("m_depth")
    #     dbd = dbdreader.DBD("dbdreader/data/sebastian-2014-204-05-001.dbd", skip_initial_line=False)
    #     t1, v1 = dbd.get("m_depth")
    #     assert len(v0) == len(v1) - 1
        

    # def test_get_reading_limited_values(self):
    #     print("Test whether we can read in only 10 depth values from a file.")
    #     dbd = dbdreader.DBD("dbdreader/data/sebastian-2014-204-05-001.dbd")
    #     t0, v0 = dbd.get("m_depth", max_values_to_read=10)
    #     assert len(t0)==len(v0) and len(t0)==10
        
    # def test_get_reading_limited_values_requesting_multiple_parameters(self):
    #     print("Test whether reading a limited number of values from multiple values fails.")
    #     with self.assertRaises(ValueError):
    #         dbd = dbdreader.DBD("dbdreader/data/sebastian-2014-204-05-001.dbd")
    #         result = dbd.get("m_depth", "m_pitch", max_values_to_read=10)
        
    # def get(self,fn,x):
    #     try:
    #         dbd=dbdreader.DBD(fn)
    #         v=dbd.get(x)
    #     except Exception as e:
    #         raise e
    #     return v

    # def get_method(self,method,fn,x,*y):
    #     dbd=dbdreader.DBD(fn)
    #     try:
    #         if method=='sync':
    #             v=dbd.get_sync(x,*y)
    #         elif method=='xy':
    #             v=dbd.get_xy(x,*y)
    #         elif method=='list':
    #             v=dbd.get_list(*y)
    #     except Exception as e:
    #         raise e
    #     return v































def test_multidbd_get_sync():
    ''' Test normal behaviour. Temperature should return all values, and oxygen has 10 leading nans'''
    dbd = dbdreader.MultiDBD('dbdreader/data/hal_1002-2024-183-4-?.tbd')
    sensors=['sci_water_temp', 'sci_oxy4_oxygen']
    t, x, y = dbd.get_sync(*sensors)
    assert np.all(np.isnan(y[:10])) and np.isclose(x.mean(), 7.518728574117024)

def test_multidbd_get_sync_heading():
    ''' Test using interp1d and interpolate heading properly'''
    dbd = dbdreader.MultiDBD('dbdreader/data/sebastian*.?bd')
    sensors=['sci_water_temp', 'm_heading']
    t, x, y = dbd.get_sync(*sensors, interpolating_function_factory=dbdreader.heading_interpolating_function_factory)
    assert len(y.compress(np.logical_and(y>3, y<5)))==0 # there should be no values in this range
    assert np.isclose(x.mean(), 16.568510801834467)

def test_multidbd_get_sync_specific_iff_handling():
    ''' Test using interpolating function for specific parameter'''
    dbd = dbdreader.MultiDBD('dbdreader/data/sebastian*.?bd')
    sensors=['sci_water_temp', 'sci_bb3slo_b470_scaled', 'm_heading']
    interpolating_function_factory = dict(m_heading=dbdreader.heading_interpolating_function_factory)
    t, x, y, z = dbd.get_sync(*sensors, interpolating_function_factory=interpolating_function_factory)
    assert len(z.compress(np.logical_and(z>3, z<5)))==0 # there should be no values in this range
    assert np.isclose(x.mean(), 16.568510801834467)
    assert np.isclose(y.mean(), 0.0019145932901356323)


def test_multidbd_get_xy_heading():
    ''' Test whether custom interpolation works for get_xy() method.'''
    dbd = dbdreader.MultiDBD('dbdreader/data/sebastian*.?bd')
    sensors=['sci_water_temp', 'm_heading']
    x, y = dbd.get_xy(*sensors, interpolating_function_factory=dbdreader.heading_interpolating_function_factory)
    assert len(y.compress(np.logical_and(y>3, y<5)))==0 # there should be no values in this range
    assert np.isclose(x.mean(), 16.568510801834467)

def test_multidbd_get_CTD_sync_heading_all_parameters():
    ''' Test the implementation of a custom interpolation scheme for get_CTD, using heading interpolation for all parameters'''
    dbd = dbdreader.MultiDBD('dbdreader/data/sebastian*.?bd')
    sensors=['m_heading']
    tctd, C, T, D, y = dbd.get_CTD_sync(*sensors, interpolating_function_factory=dbdreader.heading_interpolating_function_factory)
    assert len(y.compress(np.logical_and(y>3, y<5)))==0 # there should be no values in this range
    assert np.all(T<2*np.pi) # all T values should be clipped below 2 pi.

def test_multidbd_get_CTD_sync_heading():
    ''' Test the implementation of a custom interpolation scheme for get_CTD, using heading interpolation for all parameters'''
    dbd = dbdreader.MultiDBD('dbdreader/data/sebastian*.?bd')
    sensors=['m_heading']
    iff_dict = dict(m_heading=dbdreader.heading_interpolating_function_factory)
    tctd, C, T, D, y = dbd.get_CTD_sync(*sensors, interpolating_function_factory=iff_dict)
    assert len(y.compress(np.logical_and(y>3, y<5)))==0 # there should be no values in this range
    assert np.isclose(T.mean(), 16.572957188641585) # this is slightly different from other tests, because some values are dropped in get_CTD_sync.
        
