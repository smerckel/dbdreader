import sys
sys.path.insert(0, "..")
import dbdreader
import glob
import numpy as np
import os
import unittest

class Dbdreader_DBD_test(unittest.TestCase):
    
    def test_open(self):
        print("Open")
        v=self.get("../data/amadeus-2014-204-05-000.sbd","m_depth")
        self.assertTrue(len(v)==2 and len(v[0])>0)
    
    def test_get_non_existing_variable(self):
        print("get_non_existing_variable")
        v=self.get("../data/amadeus-2014-204-05-000.sbd","sci_water_pressure")
        self.assertTrue(len(v)==2 and len(v[0])==0 and len(v[1])==0)

    def test_get_sync_non_existing_variable(self):
        print("get_sync_non_existing_variable")
        v = self.get_method("sync",
                          "../data/amadeus-2014-204-05-000.sbd",
                            "m_depth",'sci_water_pressure','m_lon')
        self.assertTrue(len(v)==4 and len(v[2])==len(v[1]) and np.all(np.isnan(v[2])))

    def test_get_non_valid_variable(self):
        print("get_non_valid_variable")
        with self.assertRaises(dbdreader.DbdError) as e:
            v=self.get("../data/amadeus-2014-204-05-000.sbd","M_LON")
        # We expect an exception when an non-existing parameter is being requested.
        self.assertTrue(e.exception.value==dbdreader.DBD_ERROR_NO_VALID_PARAMETERS)


    def test_get_sync(self):
        print("get_sync")
        self.get_method("sync",
                        "../data/amadeus-2014-204-05-000.sbd",
                        "m_depth",'m_lat','m_lon')

    def test_get_sync_obselete(self):
        print("get_sync_obselete")
        dbd=dbdreader.DBD("../data/amadeus-2014-204-05-000.sbd")
        x = dbd.get_sync("m_depth", ['m_lat','m_lon'])

    def test_get_xy(self):
        print("get_xy")
        self.get_method("xy",
                        "../data/amadeus-2014-204-05-000.sbd",
                        'm_lat','m_lon')

    def test_get_list(self):
        print("get_list")
        dbd=dbdreader.DBD("../data/amadeus-2014-204-05-000.sbd")
        x, y = dbd.get_list("m_lat", "m_lon")


    def test_file_open_time(self):
        print("file_open_time")
        dbd=dbdreader.DBD("../data/amadeus-2014-204-05-000.sbd")
        t=dbd.get_fileopen_time()
        self.assertEqual(t,1406221414)

    def test_get_mission_name(self):
        print("get_mission_name")
        dbd=dbdreader.DBD("../data/amadeus-2014-204-05-000.sbd")
        t=dbd.get_mission_name()
        self.assertEqual(t,"micro.mi")

    def test_non_standard_cache_dir(self):
        print("non_standard_cache_dir")
        dbd=dbdreader.DBD("../data/amadeus-2014-204-05-000.sbd", cacheDir='../data/cac')
        depth = dbd.get("m_depth")
        self.assertEqual(len(depth), 2)


    def test_non_standard_cache_dir_generate_cachefile(self):
        print("non_standard_cache_dir_generated_cachefile")
        # this should create a cache file. Remove it if already present.
        try:
            os.unlink('../data/cac/(813b137d.cac')
        except FileNotFoundError:
            pass
        dbd=dbdreader.DBD("../data/ammonite-2008-028-01-000.mbd", cacheDir='../data/cac')
        depth = dbd.get("m_depth")
        self.assertEqual(len(depth), 2)

    def test_G3S_data_file(self):
        print("Reading a G3S data file for which the byte order needs to be swapped.")
        dbd = dbdreader.DBD("../data/unit_887-2021-321-3-0.sbd",
                            cacheDir='../data/cac')
        tm, depth = dbd.get("m_depth")
        self.assertAlmostEqual(depth.max(),34.5, delta=0.1)
        
    def test_missing_cache_file(self):
        print("Throw an error when cache file is missing...")
        with self.assertRaises(dbdreader.DbdError) as e:
            dbd = dbdreader.DBD("../data/unit_887-2021-321-3-0.sbd")
            #tm, depth = dbd.get("m_depth")

    def test_donottest_non_standard_cache_dir_fail(self):
        print("non_standard_cache_dir_fail")
        kwds = dict(cacheDir='../data/not_there')
        self.assertRaises(dbdreader.DbdError, dbdreader.DBD, "../data/amadeus-2014-204-05-000.sbd", **kwds)

    def test_missing_cache_file_data_feature(self):
        print("Throw an error when cache file is missing, and check who is missing.")
        try:
            dbd = dbdreader.DBD("../data/unit_887-2021-321-3-0.sbd")
        except dbdreader.DbdError as e:
            data = e.data
            for k,v in data.missing_cache_files.items():
                assert k == 'd6f44165' and v[0] == "../data/unit_887-2021-321-3-0.sbd"


    def test_handling_inf(self):
        dbd = dbdreader.DBD("../data/amadeus-2014-204-05-000.dbd",
                            cacheDir="../data/cac")

        t, v = dbd.get("m_time_til_wpt", return_nans =True)
        t = t[:24]
        v = v[:24]
        # Now read the output by dbd2asc
        with open("../data/dbd2asc_output.txt") as fp:
            lines = fp.readlines()
        lines.pop(0) # remark
        tp = np.zeros_like(t)
        vp = np.zeros_like(t)
        for i, line in enumerate(lines):
            _x, _y = line.strip().split()
            tp[i] = _x
            vp[i] = _y
        #for a,b,c,d in zip(t, tp, v, vp):
        #    print(f"{a:16f} {b:16f}    {c:16f} {d:16f}")
        condition1 = np.isclose(t, tp)
        condition3 = np.isfinite(vp)
        condition2 = np.isclose(v, vp).compress(condition3)
        assert np.all(condition1) and np.all(condition2)

    def test_get_sync_on_parameter_without_values(self):
        print("Reads in a parameter to sync that has no values.")
        dbd = dbdreader.DBD("../data/sebastian-2014-204-05-001.dbd")
        _, _, x = dbd.get_sync("m_depth", "u_dbd_sensor_list_xmit_control")
        assert np.all(np.isfinite(x)==False)
        
    def get(self,fn,x):
        try:
            dbd=dbdreader.DBD(fn)
            v=dbd.get(x)
        except Exception as e:
            raise e
        return v

    def get_method(self,method,fn,x,*y):
        dbd=dbdreader.DBD(fn)
        try:
            if method=='sync':
                v=dbd.get_sync(x,*y)
            elif method=='xy':
                v=dbd.get_xy(x,*y)
            elif method=='list':
                v=dbd.get_list(*y)
        except Exception as e:
            raise e
        return v



class Dbdreader_MultiDBD_test(unittest.TestCase):

    def setUp(self):
        self.pattern="../data/amadeus-2014-*.[st]bd"

    def test_open(self):
        print("Open")
        v=self.get_method("get",self.pattern,"m_depth",[])
        self.assertTrue(len(v)==2 and len(v[0])>0)
    
    def test_get_non_existing_variable(self):
        print("get_non_existing_variable")
        v = self.get_method("get",self.pattern,"m_water_pressure",[])
        condition = len(v)==2 and len(v[1])==0 and len(v[0])==0
        self.assertTrue(condition)

    def test_get_sync_non_invalid_variable(self):
        print("get_sync_non_invalid_variable")
        with self.assertRaises(dbdreader.DbdError) as e:
            v = self.get_method("sync",
                                self.pattern,
                                "m_depth",['m_lat','M_LON'])
        # We expect an exception when an non-existing parameter is being requested.
        self.assertTrue(e.exception.value==dbdreader.DBD_ERROR_NO_VALID_PARAMETERS)


    def test_get_sync_non_existing_variable(self):
        print("get_sync_non_existing_variable")
        v = self.get_method("sync",
                            self.pattern,
                            "m_depth",['m_lat','m_water_pressure'])

        condition = len(v)==4 and len(v[2]==v[3]) and np.all(np.isnan(v[3]))
        self.assertTrue(condition)

        
    def test_get_sync(self):
        print("get_sync")
        dbd=dbdreader.MultiDBD(pattern=self.pattern)
        t, d, lat, lon = dbd.get_sync("m_depth",'m_lat','m_lon')


    def test_get_sync_mixed_eng_sci_parameters(self):
        print("get_sync_obselete")
        self.get_method("sync",
                        self.pattern,
                        "m_depth",['sci_water_pressure','m_lon'])

    def test_get_xy(self):
        print("get_xy")
        self.get_method("xy",
                        self.pattern,
                        'm_lat','m_lon')
        
    # def test_get_list(self):
    #     self.get_method("list",
    #                     self.pattern,
    #                     None,['m_lat','m_lon'])
        
    def test_time_limits(self):
        print("time_limits")
        dbd=dbdreader.MultiDBD(pattern=self.pattern)
        v0=dbd.get("m_depth")
        t=dbd.get_global_time_range()
        t1=dbd.get_time_range()
        dbd.set_time_limits(minTimeUTC='24 Jul 2014 18:00')
        v1=dbd.get("m_depth")
        t2=dbd.get_time_range()
        self.assertEqual(t,['24 Jul 2014 17:02', '24 Jul 2014 18:20'])
        self.assertEqual(t,t1)
        self.assertEqual(t2[0],'24 Jul 2014 18:00')
        self.assertLess(len(v1[0]),len(v0[0]))

    def test_non_standard_cache_dir(self):
        print("non_standard_cache_dir")
        dbd=dbdreader.MultiDBD(pattern = self.pattern, cacheDir='../data/cac')
        depth = dbd.get("m_depth")
        self.assertEqual(len(depth), 2)

    def test_donottest_non_standard_cache_dir_fail(self):
        kwds = dict(pattern=self.pattern, cacheDir='../data/not_there')
        self.assertRaises(dbdreader.DbdError, dbdreader.MultiDBD, **kwds)

    def test_get_ctd_sync(self):
        print("get_ctd_sync")
        pattern="../data/amadeus-2014-*.[de]bd"
        dbd=dbdreader.MultiDBD(pattern = pattern, cacheDir='../data/cac')
        tctd, C, T, P, depth = dbd.get_CTD_sync("m_depth")
        
    def test_missing_cache_files(self):
        print("Throw an error when cache file is missing...")
        # read in a sbd and tbd file. Only the sbd's cac file is in cac_missing.
        with self.assertRaises(dbdreader.DbdError) as e:
            dbd = dbdreader.MultiDBD(pattern="../data/unit_887-2021-321-3-0.?bd",
                                     cacheDir='../data/cac_missing')
        

    def test_open_file_with_pattern_str_as_first_argument(self):
        print("Open multidbd with just a string as first argument. Should be interpreted as a pattern")
        dbd = dbdreader.MultiDBD("../data/amadeus-2014-*.*bd")

    def test_open_file_with_pattern_str_as_first_argument_and_pattern(self):
        print("Open multidbd with just a string as first argument and a pattern, which should fail.")
        with self.assertRaises(dbdreader.DbdError) as e:
            dbd = dbdreader.MultiDBD("../data/amadeus-2014-*.*bd", pattern="../data/amadeus-2014-204-05-000.?bd")

    def test_opening_empty_file(self):
        print("Ignore empty files and files with wrong encodings...")
        dbd = dbdreader.MultiDBD(pattern = "../data/*-2014-204-05-000.dbd")

    def test_opening_capitalised_files(self):
        print("Allow opening of files with capitalised extensions.")
        dbd = dbdreader.MultiDBD(pattern = "../data/amadeus-2014-203-00-000.[ST]BD")

    def test_problem_causing_segfault(self):
        # this test caused a segfault as a result of a bug introduced in commit eeb64d8e8c20345dafcacebf074f098fa945fd46
        # Run this test only when this script has access to the data files.
        if True and os.path.exists("/home/lucas/gliderdata/helgoland201407/hd"):
            print("Running (long test) that caused in segfault in the past.")
            dbd = dbdreader.MultiDBD("/home/lucas/gliderdata/helgoland201407/hd/amadeus-2014-*.[de]bd")
            data = dbd.get_CTD_sync("sci_flntu_turb_units")
        
    def test_missing_cache_file_data_feature(self):
        print("Throw an error when cache file is missing, and check who is missing.")
        try:
            dbd = dbdreader.MultiDBD("../data/unit_887-2021-321-3-0.?bd")
        except dbdreader.DbdError as e:
            data = e.data
            assert data.missing_cache_files['c4ec741e'][0] =="../data/unit_887-2021-321-3-0.tbd"

    def test_get_sync_on_parameter_without_values(self):
        print("Reads in a parameter to sync that has no values.")
        dbd = dbdreader.MultiDBD("../data/sebastian-2014-204-05-00?.dbd")
        _, _, x = dbd.get_sync("m_depth", "u_dbd_sensor_list_xmit_control")
        # x has a 2.0 as first value, but then all nans.
        assert np.all(np.isfinite(x[1:])==False) and x[0]==2.

    def test_get_CTD_sync_on_parameter_without_values(self):
        print("Reads in a parameter to get_CTD_sync that has no values; Assert error.")
        dbd = dbdreader.MultiDBD("../data/sebastian-2014-204-05-00?.dbd",
                                 complement_files=True)
        try:
            x = dbd.get_CTD_sync("m_depth", "u_dbd_sensor_list_xmit_control")
        except dbdreader.DbdError as e:
            assert e.value == dbdreader.DBD_ERROR_NO_DATA_TO_INTERPOLATE

    def test_get_CTD_sync_removes_empty_timestamps(self):
        print("Reads data using get_CTD_sync and empty timestamps should be removed.")
        dbd = dbdreader.MultiDBD("../data/sebastian-2014-204-05-00?.dbd",
                                 complement_files=True)
        tctd, T, C, P = dbd.get_CTD_sync()
        t, tctdp = dbd.get("sci_ctd41cp_timestamp")
        idx = np.where(tctdp<1)[0]
        assert len(idx) and len(tctd) == len(tctdp) - len(idx)

    def test_include_source_data(self):
        print("Verify that source DBDs correctly map to data points.")
        multi = dbdreader.MultiDBD(pattern=self.pattern)
        for parameter in multi.parameterNames["eng"] + multi.parameterNames["sci"]:
            data, dbd_source = multi.get(parameter, include_source=True)
            dbds = set(dbd_source)  # Unique source DBDs for this parameter
            for dbd in dbds:
                mask = [i==dbd for i in dbd_source]
                content = [data[0][mask], data[1][mask]]  # Only data attributed to this DBD
                single = dbd.get(parameter)
                # Data should be identical
                assert all(content[0] == single[0])
                assert all(content[1] == single[1])

    def test_include_source_files(self):
        print("Verify that all designated files are represented in sources.")
        files = glob.glob(self.pattern)
        multi = dbdreader.MultiDBD(pattern=self.pattern)
        output = multi.get(*(multi.parameterNames["eng"] + multi.parameterNames["sci"]), include_source=True)
        sources = {dbd.filename for data in output for dbd in data[1]}
        # All files should be represented
        assert all(file in sources for file in files)
        assert all(source in files for source in sources)
        
            
    def get_method(self,method,fn,x,y):
        dbd=dbdreader.MultiDBD(pattern=fn)
        try:
            if method=="get":
                v=dbd.get(x)
            elif method=='sync':
                v=dbd.get_sync(x,y)
            elif method=='xy':
                v=dbd.get_xy(x,y)
            elif method=='list':
                v=dbd.get_list(y)
        except Exception as e:
            raise e
        return v
        
class DBDPatternSelect_test(unittest.TestCase):

    def test_select_from_pattern(self):
        print("select from pattern")
        PS=dbdreader.DBDPatternSelect(date_format="%d %m %Y %H:%M")
        fns=PS.select(pattern="../data/ama*.sbd",from_date="24 7 2014 00:00")
        fns.sort()
        self.assertEqual(fns[0],"../data/amadeus-2014-204-05-000.sbd")
        fns=PS.select(pattern="../data/ama*.sbd",from_date="24 7 2014 18:00")
        fns.sort()
        self.assertEqual(fns[0],"../data/amadeus-2014-204-05-001.sbd")
        fns=PS.select(pattern="../data/ama*.sbd",until_date="24 7 2014 18:00")
        self.assertEqual(len(fns),1)

    def test_select_from_pattern_non_standard_cache_dir(self):
        print("select from pattern non standard cache dir")
        dbdreader.DBDPatternSelect.cache.clear()
        PS=dbdreader.DBDPatternSelect(date_format="%d %m %Y %H:%M", cacheDir='../data/cac')
        fns=PS.select(pattern="../data/ama*.sbd",from_date="24 7 2014 00:00")
        fns.sort()
        self.assertEqual(fns[0],"../data/amadeus-2014-204-05-000.sbd")

unittest.main()
