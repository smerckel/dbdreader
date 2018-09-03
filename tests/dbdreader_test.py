from __future__ import unicode_literals
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import
from future import standard_library
standard_library.install_aliases()
import dbdreader
import glob
import numpy as np
import unittest

class Dbdreader_DBD_test(unittest.TestCase):
    
    def test_open(self):
        v=self.get("../data/amadeus-2014-204-05-000.sbd","m_depth")
        self.assertTrue(len(v)==2 and len(v[0])>0)
    
    def test_get_non_existing_variable(self):
        self.assertRaises(dbdreader.DbdError,
                          self.get,
                          "../data/amadeus-2014-204-05-000.sbd","M_DEPTH")

    def test_get_sync_non_existing_variable(self):
        self.assertRaises(dbdreader.DbdError,
                          self.get_method,"sync",
                          "../data/amadeus-2014-204-05-000.sbd",
                          "m_depth",['m_lat','M_LON'])

    def test_get_sync(self):
        self.get_method("sync",
                        "../data/amadeus-2014-204-05-000.sbd",
                        "m_depth",['m_lat','m_lon'])
    def test_get_xy(self):
        self.get_method("xy",
                        "../data/amadeus-2014-204-05-000.sbd",
                        'm_lat','m_lon')

    def test_get_list(self):
        self.get_method("list",
                        "../data/amadeus-2014-204-05-000.sbd",
                        "dmy",['m_lat','m_lon'])


    def test_file_open_time(self):
        dbd=dbdreader.DBD("../data/amadeus-2014-204-05-000.sbd")
        t=dbd.get_fileopen_time()
        dbd.close()
        self.assertEqual(t,1406221414)

    def test_get_mission_name(self):
        dbd=dbdreader.DBD("../data/amadeus-2014-204-05-000.sbd")
        t=dbd.get_mission_name()
        dbd.close()
        self.assertEqual(t,"micro.mi")

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

    def get_method(self,method,fn,x,y):
        dbd=dbdreader.DBD(fn)
        try:
            if method=='sync':
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



class Dbdreader_MultiDBD_test(unittest.TestCase):

    def setUp(self):
        self.pattern="../data/amadeus-2014-*.[st]bd"

    def test_open(self):
        v=self.get_method("get",self.pattern,"m_depth",[])
        self.assertTrue(len(v)==2 and len(v[0])>0)
    
    def test_get_non_existing_variable(self):
        self.assertRaises(dbdreader.DbdError,
                          self.get_method,"get",
                          self.pattern,"M_DEPTH",[])

    def test_get_sync_non_existing_variable(self):
        self.assertRaises(dbdreader.DbdError,
                          self.get_method,"sync",
                          self.pattern,
                          "m_depth",['m_lat','M_LON'])

    def test_get_sync(self):
        self.get_method("sync",
                        self.pattern,
                        "m_depth",['m_lat','m_lon'])

    def test_get_sync_mixed_eng_sci_parameters(self):
        self.get_method("sync",
                        self.pattern,
                        "m_depth",['sci_water_pressure','m_lon'])

    def test_get_xy(self):
        self.get_method("xy",
                        self.pattern,
                        'm_lat','m_lon')

    def test_get_list(self):
        self.get_method("list",
                        self.pattern,
                        "dmy",['m_lat','m_lon'])

    def test_time_limits(self):
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
