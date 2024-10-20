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
    v = dbd.get("m_depth")
    assert len(v) == 2 and len(v[0]) > 0


def test_get_non_existing_variable():
    dbd = dbdreader.DBD("dbdreader/data/amadeus-2014-204-05-000.sbd")
    v = dbd.get("sci_water_pressure")
    assert len(v) == 2 and len(v[0]) == 0


def test_get_invalid_variable():
    dbd = dbdreader.DBD("dbdreader/data/amadeus-2014-204-05-000.sbd")
    with pytest.raises(dbdreader.DbdError) as e:
        v = dbd.get("sci_pressure")
    assert e.value.value == dbdreader.DBD_ERROR_NO_VALID_PARAMETERS


def test_get_sync():
    dbd = dbdreader.DBD("dbdreader/data/amadeus-2014-204-05-000.sbd")
    v = dbd.get_sync("m_depth", 'm_lat', 'm_lon')
    checks = [len(v[i]) == len(v[0]) for i in range(1, 4)]
    assert len(v) == 4 and len(v[0] == 67) and all(checks)


def test_get_sync_non_existing_variable():
    dbd = dbdreader.DBD("dbdreader/data/amadeus-2014-204-05-000.sbd")
    v = dbd.get_sync("m_depth", 'sci_water_pressure', 'm_lon')
    checks = [len(v[i]) == len(v[0]) for i in range(1, 4)]
    assert len(v) == 4 and len(v[0] == 67) and \
        all(checks) and np.all(np.isnan(v[2]))


def test_get_sync_invalid_variable():
    dbd = dbdreader.DBD("dbdreader/data/amadeus-2014-204-05-000.sbd")
    with pytest.raises(dbdreader.DbdError) as e:
        v = dbd.get_sync("m_depth", 'sci_pressure', 'm_lon')
    assert e.value.value == dbdreader.DBD_ERROR_NO_VALID_PARAMETERS


def test_get_sync_obselete():
    dbd = dbdreader.DBD("dbdreader/data/amadeus-2014-204-05-000.sbd")
    x = dbd.get_sync("m_depth", ['m_lat', 'm_lon'])
    y = dbd.get_sync("m_depth", 'm_lat', 'm_lon')
    assert all([np.all(i.compress(np.isfinite(i)) == j.compress(np.isfinite(j))) \
                for i, j in zip(x, y)])


def test_get_xy():
    dbd = dbdreader.DBD("dbdreader/data/amadeus-2014-204-05-000.sbd")
    x, y = dbd.get_xy('m_lat', 'm_lon')
    assert np.allclose(x, np.array([54.26715942, 54.26802426])) and \
        np.allclose(y, np.array([7.41679603, 7.42362288]))


def test_get_list():
    dbd = dbdreader.DBD("dbdreader/data/amadeus-2014-204-05-000.sbd")
    x, y = dbd.get_list("m_lat", "m_lon")
    xp, yp = dbd.get("m_lat", "m_lon")
    assert np.allclose(x[1], xp[1]) and np.allclose(y[1], yp[1])


def test_file_open_time():
    dbd = dbdreader.DBD("dbdreader/data/amadeus-2014-204-05-000.sbd")
    t = dbd.get_fileopen_time()
    assert t == 1406221414


def test_get_mission_name():
    dbd = dbdreader.DBD("dbdreader/data/amadeus-2014-204-05-000.sbd")
    t = dbd.get_mission_name()
    assert t == "micro.mi"

def test_non_standard_cache_dir():
    dbd = dbdreader.DBD("dbdreader/data/amadeus-2014-204-05-000.sbd",
                        cacheDir='dbdreader/data/cac')
    depth = dbd.get("m_depth")
    assert len(depth) == 2


def test_non_standard_cache_dir_generate_cachefile():
    #  this should create a cache file. Remove it if already present.
    try:
        os.unlink('dbdreader/data/cac/(813b137d.cac')
    except FileNotFoundError:
        pass
    dbd = dbdreader.DBD("dbdreader/data/ammonite-2008-028-01-000.mbd",
                        cacheDir='dbdreader/data/cac')
    depth = dbd.get("m_depth")
    assert len(depth) == 2

    
def test_G3S_data_file():
    #  Reading a G3S data file for which the byte order needs to be swapped
    dbd = dbdreader.DBD("dbdreader/data/unit_887-2021-321-3-0.sbd",
                        cacheDir='dbdreader/data/cac')
    tm, depth = dbd.get("m_depth")
    assert np.allclose(depth.max(), 34.45457458496094)


def test_missing_cache_file():
    #  Throw an error when cache file is missing...
    with pytest.raises(dbdreader.DbdError) as e:
        dbd = dbdreader.DBD("dbdreader/data/hal_1002-2024-183-4-4.sbd")
    assert e.value.value == dbdreader.DBD_ERROR_CACHE_NOT_FOUND  


def test_donottest_non_standard_cache_dir_fail():
    #  non_standard_cache_dir_fail
    kwds = dict(cacheDir='dbdreader/data/not_there')
    with pytest.raises(dbdreader.DbdError):
        dbd = dbdreader.DBD("dbdreader/data/amadeus-2014-204-05-000.sbd",
                            **kwds)


def test_missing_cache_file_data_feature():
    # Throw an error when cache file is missing, and check who is missing.
    try:
        dbd = dbdreader.DBD("dbdreader/data/unit_887-2021-321-3-0.sbd")
    except dbdreader.DbdError as e:
        data = e.data
        for k, v in data.missing_cache_files.items():
            assert k == 'd6f44165' and \
                v[0] == "dbdreader/data/unit_887-2021-321-3-0.sbd"


def test_handling_inf():
    dbd = dbdreader.DBD("dbdreader/data/amadeus-2014-204-05-000.dbd",
                        cacheDir="dbdreader/data/cac")
    t, v = dbd.get("m_time_til_wpt", return_nans=True)
    t = t[:24]
    v = v[:24]
    #  Now read the output by dbd2asc
    with open("dbdreader/data/dbd2asc_output.txt") as fp:
        lines = fp.readlines()
    lines.pop(0)  # remark
    tp = np.zeros_like(t)
    vp = np.zeros_like(t)
    for i, line in enumerate(lines):
        _x, _y = line.strip().split()
        tp[i] = _x
        vp[i] = _y
    condition1 = np.isclose(t, tp)
    condition3 = np.isfinite(vp)
    condition2 = np.isclose(v, vp).compress(condition3)
    assert np.all(condition1) and np.all(condition2)

def test_get_sync_on_parameter_without_values():
    # Reads in a parameter to sync that has no values.
    dbd = dbdreader.DBD("dbdreader/data/sebastian-2014-204-05-001.dbd")
    _, _, x = dbd.get_sync("m_depth", "u_dbd_sensor_list_xmit_control")
    assert np.all(np.isfinite(x) == False)


def test_get_reading_initial_data_line():
    # Tests whether initial data line can be read if requested.
    dbd = dbdreader.DBD("dbdreader/data/sebastian-2014-204-05-001.dbd")
    t0, v0 = dbd.get("m_depth")
    dbd = dbdreader.DBD("dbdreader/data/sebastian-2014-204-05-001.dbd",
                        skip_initial_line=False)
    t1, v1 = dbd.get("m_depth")
    assert len(v0) == len(v1) - 1


def test_get_reading_limited_values():
    # Test whether we can read in only 10 depth values from a file.
    dbd = dbdreader.DBD("dbdreader/data/sebastian-2014-204-05-001.dbd")
    t0, v0 = dbd.get("m_depth", max_values_to_read=10)
    assert len(t0) == len(v0) and len(t0) == 10
  

def test_get_reading_limited_values_requesting_multiple_parameters():
    # Test whether reading a limited number of values from multiple
    # values fails.
    with pytest.raises(ValueError):
        fn = "dbdreader/data/sebastian-2014-204-05-001.dbd"
        dbd = dbdreader.DBD(fn)
        dbd.get("m_depth", "m_pitch", max_values_to_read=10)

        
@pytest.fixture
def multiSBDData(scope='class'):
    pattern = "dbdreader/data/amadeus-2014-*.[st]bd"
    dbd = dbdreader.MultiDBD(pattern)
    return dbd


@pytest.fixture
def multiDBDData(scope='class'):
    dbdreader.DBDCache.set_cachedir('dbdreader/data/cac')
    pattern = "dbdreader/data/amadeus-2014-*.[de]bd"
    dbd = dbdreader.MultiDBD(pattern)
    return dbd


class TestMultiDBD():
    pattern = "dbdreader/data/amadeus-2014-*.[st]bd"
    
    def test_open(self, multiSBDData):
        dbd = multiSBDData
        v = dbd.get("m_depth")
        assert len(v) == 2 and len(v[0] > 0)
        

    def test_get_non_existing_variable(self, multiSBDData):
        dbd = multiSBDData
        v = dbd.get("m_water_pressure")
        condition = len(v) == 2
        condition &= len(v[1]) == 0 and len(v[0]) == 0
        assert condition

    def test_get_sync_non_invalid_variable(self, multiSBDData):
        dbd = multiSBDData
        with pytest.raises(dbdreader.DbdError) as e:
            dbd.get_sync("m_lat", "M_LON")
            assert e.exception.value == dbdreader.DBD_ERROR_NO_VALID_PARAMETERS
          

    def test_get_sync_non_existing_variable(self, multiSBDData):
        dbd = multiSBDData
        v = dbd.get_sync("m_depth", "m_lat", "m_water_pressure")
        condition = len(v)==4 and len(v[2]==v[3]) and np.all(np.isnan(v[3]))
        assert condition

    def test_get_sync(self, multiSBDData):
        dbd = multiSBDData
        t, d, lat, lon = dbd.get_sync("m_depth", "m_lat", "m_lon")


    def test_get_sync_mixed_eng_sci_parameters(self, multiSBDData):
        dbd = multiSBDData
        dbd.get_sync("m_depth", 'sci_water_pressure', 'm_lon')


    def test_get_xy(self, multiSBDData):
        dbd = multiSBDData
        dbd.get_xy('m_lat', 'm_lon')

###
    def test_time_limits(self, multiSBDData):
        dbd = multiSBDData
        v0 = dbd.get("m_depth")
        t = dbd.get_global_time_range()
        t1 = dbd.get_time_range()
        dbd.set_time_limits(minTimeUTC='24 Jul 2014 18:00')
        v1 = dbd.get("m_depth")
        t2 = dbd.get_time_range()
        assert t == ['24 Jul 2014 17:02', '24 Jul 2014 18:20']
        assert t == t1
        assert t2[0] == '24 Jul 2014 18:00'
        assert len(v1[0]) < len(v0[0])


    def test_non_standard_cache_dir(self):
        dbd=dbdreader.MultiDBD(pattern = self.pattern,
                               cacheDir='dbdreader/data/cac')
        depth = dbd.get("m_depth")
        assert len(depth) == 2

    def test_non_standard_cache_dir_alternative(self):
        dbdreader.DBDCache.set_cachedir('dbdreader/data/cac')
        dbd=dbdreader.MultiDBD(pattern=self.pattern)
        depth = dbd.get("m_depth")
        assert len(depth) == 2
 
    def test_donottest_non_standard_cache_dir_fail(self):
        kwds = dict(pattern=self.pattern, cacheDir='dbdreader/data/not_there')
        with pytest.raises(dbdreader.DbdError):
            dbdreader.MultiDBD(self.pattern, **kwds)

    def test_get_ctd_sync(self, multiDBDData):
        dbd = multiDBDData
        tctd, C, T, P, depth = dbd.get_CTD_sync("m_depth")

    def test_get_ctd_sync_rbrCTD(self):
        pattern="dbdreader/data/electa-2023-143-00-050.[st]bd"
        dbd=dbdreader.MultiDBD(pattern = pattern, cacheDir='dbdreader/data/cac')
        tctd, C, T, P, pressure = dbd.get_CTD_sync("m_pressure")
        assert tctd.shape == (385,)
        assert C.shape == (385,)

    def test_missing_cache_files(self):
        #     print("Throw an error when cache file is missing...")
        #     read in a sbd and tbd file. Only the sbd's cac file is
        #     in cac_missing.
        with pytest.raises(dbdreader.DbdError):
            pattern="dbdreader/data/unit_887-2021-321-3-0.?bd"
            dbd = dbdreader.MultiDBD(pattern,
                                     cacheDir='dbdreader/data/cac_missing')
           

    def test_open_file_with_pattern_str_as_first_argument(self):
        #     Open multidbd with just a string as first argument. Should
        #     be interpreted as a pattern dbd 
        dbdreader.MultiDBD("dbdreader/data/amadeus-2014-*.*bd")

    def test_open_file_with_pattern_str_as_first_argument_and_pattern(self):
        #     Open multidbd with just a string as first argument and a
        #     pattern, which should fail.")
        with pytest.raises(dbdreader.DbdError):
            pattern="dbdreader/data/amadeus-2014-204-05-000.?bd"
            dbd = dbdreader.MultiDBD("dbdreader/data/amadeus-2014-*.*bd",
                                     pattern=pattern)

    def test_opening_empty_file(self):
        # Ignore empty files and files with wrong encodings...
        pattern = "dbdreader/data/*-2014-204-05-000.dbd"
        dbd = dbdreader.MultiDBD(pattern)
        dbd.get("m_depth")

    def test_opening_capitalised_files(self):
        # Allow opening of files with capitalised extensions.
        pattern = "dbdreader/data/amadeus-2014-203-00-000.[ST]BD"
        dbd = dbdreader.MultiDBD(pattern=pattern)
        dbd.get("m_depth")
     
    # def test_problem_causing_segfault(self):
    #     # this test caused a segfault as a result of a bug introduced in commit eeb64d8e8c20345dafcacebf074f098fa945fd46
    #     # Run this test only when this script has access to the data files.
    #     if RUNLONGTESTS and os.path.exists("/home/lucas/gliderdata/helgoland201407/hd"):
    #         print("Running (long test) that caused in segfault in the past.")
    #         dbd = dbdreader.MultiDBD("/home/lucas/gliderdata/helgoland201407/hd/amadeus-2014-*.[de]bd")
    #         data = dbd.get_CTD_sync("sci_flntu_turb_units")
   
    def test_missing_cache_file_data_feature(self):
        #     Throw an error when cache file is missing, and check who
        #     is missing.
        with pytest.raises(dbdreader.DbdError) as e:
            pattern = "dbdreader/data/unit_887-2021-321-3-0.?bd"
            cacheDir = 'dbdreader/data/cac_missing'
            dbdreader.MultiDBD(pattern=pattern, cacheDir=cacheDir)
        fn = e.value.data.missing_cache_files['c4ec741e'][0]
        assert fn == "dbdreader/data/unit_887-2021-321-3-0.tbd"

    def test_get_sync_on_parameter_without_values(self):
        # Reads in a parameter to sync that has no values.
        pattern = "dbdreader/data/sebastian-2014-204-05-00?.dbd"
        dbd = dbdreader.MultiDBD(pattern)
        _, _, x = dbd.get_sync("m_depth", "u_dbd_sensor_list_xmit_control")
        # x has a 2.0 as first value, but then all nans.
        assert not np.all(np.isfinite(x[1:])) and x[0] == 2.

    def test_get_CTD_sync_on_parameter_without_values(self, multiDBDData):
        # Reads in a parameter to get_CTD_sync that has no values;
        # Assert error.
        dbd = multiDBDData
        with pytest.raises(dbdreader.DbdError) as e:
            dbd.get_CTD_sync("m_depth", "u_dbd_sensor_list_xmit_control")
        assert e.value.value == dbdreader.DBD_ERROR_NO_DATA_TO_INTERPOLATE

    def test_get_CTD_sync_removes_empty_timestamps(self, multiDBDData):
        # Reads data using get_CTD_sync and empty timestamps should be
        # removed.
        dbd = multiDBDData
        tctd, T, C, P = dbd.get_CTD_sync()
        t, tctdp = dbd.get("sci_ctd41cp_timestamp")
        # timestamps equal to 0 and dt==0 should be removed.
        n_removed = (tctdp<1).sum() + (np.diff(tctdp) < 1e-9).sum()
        assert n_removed and len(tctd) == len(tctdp) - n_removed

    # def test_include_source_data(self):
    #     print("Verify that source DBDs correctly map to data points.")
    #     multi = dbdreader.MultiDBD(pattern=self.pattern)
    #     for parameter in multi.parameterNames["eng"] + multi.parameterNames["sci"]:
    #         data, dbd_source = multi.get(parameter, include_source=True)
    #         dbds = set(dbd_source)  # Unique source DBDs for this parameter
    #         for dbd in dbds:
    #             mask = [i==dbd for i in dbd_source]
    #             content = [data[0][mask], data[1][mask]]  # Only data attributed to this DBD
    #             single = dbd.get(parameter)
    #             # Data should be identical
    #             assert all(content[0] == single[0])
    #             assert all(content[1] == single[1])

    # def test_include_source_files(self):
    #     print("Verify that all designated files are represented in sources.")
    #     files = glob.glob(self.pattern)
    #     multi = dbdreader.MultiDBD(pattern=self.pattern)
    #     output = multi.get(*(multi.parameterNames["eng"] + multi.parameterNames["sci"]), include_source=True)
    #     sources = {dbd.filename for data in output for dbd in data[1]}
    #     # All files should be represented
    #     assert all(file in sources for file in files)
    #     assert all(source in files for source in sources)
        
    # def test_get_reading_initial_data_line(self):
    #     print("Tests whether initial data line can be read if requested.")
        
    #     dbd = dbdreader.MultiDBD(self.pattern)
    #     t0, v0 = dbd.get("m_depth")
    #     dbd = dbdreader.MultiDBD(self.pattern, skip_initial_line=False)
    #     t1, v1 = dbd.get("m_depth")
    #     dbd = dbdreader.MultiDBD(self.pattern)
    #     dbd.set_skip_initial_line(False)
    #     t2, v2 = dbd.get("m_depth")

    #     assert (len(v0) == len(v1) - len(dbd.dbds['eng'])) and (len(v1)==len(v2))


    # def test_get_reading_limited_values(self):
    #     print("Test whether we can read in only 10 depth values when reading multiple files.")
    #     dbd = dbdreader.MultiDBD("dbdreader/data/sebastian-2014-204-05-00?.dbd")
    #     t0, v0 = dbd.get("m_depth", max_values_to_read=10)
    #     assert len(t0)==len(v0) and len(t0)==10

    # def test_get_reading_limited_values_mixed_files(self):
    #     print("Test whether we can read in only 10 depth values when reading multiple dbd and ebd files.")
    #     dbd = dbdreader.MultiDBD("dbdreader/data/sebastian-2014-204-05-00?.?bd")
    #     t0, v0 = dbd.get("sci_water_pressure", max_values_to_read=10)
    #     assert len(t0)==len(v0) and len(t0)==10

        
    # def test_get_reading_limited_values_requesting_multiple_parameters(self):
    #     print("Test whether reading a limited number of values from multiple values fails.")
    #     with self.assertRaises(ValueError):
    #         dbd = dbdreader.MultiDBD("dbdreader/data/sebastian-2014-204-05-00?.dbd")
    #         result = dbd.get("m_depth", "m_pitch", max_values_to_read=10)

    # def test_get_missing_parameter_in_some_files(self):
    #     print("Test whether we can read multiple files and extract a parameter that is not available in all of them.")
    #     dbd = dbdreader.MultiDBD("dbdreader/data/hal_1002-2024-183-4-[46].tbd")
    #     (t1, v1), (t2, v2) = dbd.get("sci_water_temp", "sci_oxy4_oxygen")
    #     # we expect only data for oxygen from one of the two files, so get should return different lengths.
    #     assert len(t1)==21 and len(t2)==11
        
    # def test_get_sync_missing_parameter_in_some_files(self):
    #     print("Test whether we can read multiple files and extract and interpolate a parameter that is not available in all of them.")
    #     dbd = dbdreader.MultiDBD("dbdreader/data/hal_1002-2024-183-4-[46].tbd")
    #     t1, v1, v2 = dbd.get_sync("sci_water_temp", "sci_oxy4_oxygen")
    #     # we expect the first 10 data points for oxygen to be nans.
    #     assert len(t1)==21 and np.all(np.isnan(v2[:10]))
        
    # def get_method(self,method,fn,x,y):
    #     dbd=dbdreader.MultiDBD(pattern=fn)
    #     try:
    #         if method=="get":
    #             v=dbd.get(x)
    #         elif method=='sync':
    #             v=dbd.get_sync(x,y)
    #         elif method=='xy':
    #             v=dbd.get_xy(x,y)
    #         elif method=='list':
    #             v=dbd.get_list(y)
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
        
