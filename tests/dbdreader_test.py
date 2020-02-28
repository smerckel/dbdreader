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
        self.assertRaises(dbdreader.DbdError,
                          self.get,
                          "../data/amadeus-2014-204-05-000.sbd","M_DEPTH")

    def test_get_sync_non_existing_variable(self):
        print("get_sync_non_existing_variable")
        self.assertRaises(dbdreader.DbdError,
                          self.get_method,"sync",
                          "../data/amadeus-2014-204-05-000.sbd",
                          "m_depth",'m_lat','M_LON')

    def test_get_sync(self):
        print("get_sync")
        self.get_method("sync",
                        "../data/amadeus-2014-204-05-000.sbd",
                        "m_depth",'m_lat','m_lon')

    def test_get_sync_obselete(self):
        print("get_sync_obselete")
        dbd=dbdreader.DBD("../data/amadeus-2014-204-05-000.sbd")
        dbd.close()
        x = dbd.get_sync("m_depth", ['m_lat','m_lon'])

    def test_get_xy(self):
        print("get_xy")
        self.get_method("xy",
                        "../data/amadeus-2014-204-05-000.sbd",
                        'm_lat','m_lon')

    def test_get_list(self):
        print("get_list")
        dbd=dbdreader.DBD("../data/amadeus-2014-204-05-000.sbd")
        dbd.close()
        x, y = dbd.get_list("m_lat", "m_lon")


    def test_file_open_time(self):
        print("file_open_time")
        dbd=dbdreader.DBD("../data/amadeus-2014-204-05-000.sbd")
        t=dbd.get_fileopen_time()
        dbd.close()
        self.assertEqual(t,1406221414)

    def test_get_mission_name(self):
        print("get_mission_name")
        dbd=dbdreader.DBD("../data/amadeus-2014-204-05-000.sbd")
        t=dbd.get_mission_name()
        dbd.close()
        self.assertEqual(t,"micro.mi")

    def test_non_standard_cache_dir(self):
        print("non_standard_cache_dir")
        dbd=dbdreader.DBD("../data/amadeus-2014-204-05-000.sbd", cacheDir='../data/cac')
        dbd.close()
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
        dbd.close()
        depth = dbd.get("m_depth")
        self.assertEqual(len(depth), 2)

        
    def donottest_non_standard_cache_dir_fail(self):
        print("non_standard_cache_dir_fail")
        kwds = dict(cacheDir='../data/not_there')
        self.assertRaises(dbdreader.DbdError, dbdreader.DBD, "../data/amadeus-2014-204-05-000.sbd", **kwds)
        
    def get(self,fn,x):
        try:
            dbd=dbdreader.DBD(fn)
            v=dbd.get(x)
        except Exception as e:
            raise e
        finally:
            try:
                dbd.close()
            except:
                pass
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
        finally:
            try:
                dbd.close()
            except:
                pass
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
        self.assertRaises(dbdreader.DbdError,
                          self.get_method,"get",
                          self.pattern,"M_DEPTH",[])

    def test_get_sync_non_existing_variable(self):
        print("get_sync_non_existing_variable")
        self.assertRaises(dbdreader.DbdError,
                          self.get_method,"sync",
                          self.pattern,
                          "m_depth",['m_lat','M_LON'])

    def test_get_sync(self):
        print("get_sync")
        dbd=dbdreader.MultiDBD(pattern=self.pattern)
        dbd.close()
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
        dbd.close()
        self.assertEqual(t,['24 Jul 2014 17:02', '24 Jul 2014 18:20'])
        self.assertEqual(t,t1)
        self.assertEqual(t2[0],'24 Jul 2014 18:00')
        self.assertLess(len(v1[0]),len(v0[0]))

    def test_non_standard_cache_dir(self):
        print("non_standard_cache_dir")
        dbd=dbdreader.MultiDBD(pattern = self.pattern, cacheDir='../data/cac')
        dbd.close()
        depth = dbd.get("m_depth")
        self.assertEqual(len(depth), 2)

    def donottest_non_standard_cache_dir_fail(self):
        kwds = dict(pattern=self.pattern, cacheDir='../data/not_there')
        self.assertRaises(dbdreader.DbdError, dbdreader.MultiDBD, **kwds)

    def test_get_ctd_sync(self):
        print("get_ctd_sync")
        pattern="../data/amadeus-2014-*.[de]bd"
        dbd=dbdreader.MultiDBD(pattern = pattern, cacheDir='../data/cac')
        dbd.close()
        tctd, C, T, P, depth = dbd.get_CTD_sync("m_depth")
        
        
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
        finally:
            try:
                dbd.close()
            except:
                pass
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
                            
                            
unittest.main()
