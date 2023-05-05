Class DBD : reading single files
********************************

DBD API
=======

The DBD class is designed to be used with a single file, either a dbd
(sbd) or ebd (tbd) file. The actual reading of the binary files if
offloaded to a C-extension.

There is a small issue with the way the glider creates a new
file. When opening a new file, all sensors are reported as updated,
even though most sensors are not, and report whatever value is stored
in memory. As a result all sensors that update regularly will be
reported with old values. Therefore the default behaviour is to
disregard the first data entry for each sensor. There are, however,
some sensors that are set once, and never update. Dropping the first
data entry, also drops this information. Therefore, for specific or
debugging purposes, the default behaviour can be altered to also
include the first data entries of all sensors, by setting the optional
keyword ``skip_initial_line`` to False, when calling the constructor.

.. autoclass:: dbdreader.DBD
   :members: 
   
DBD Example
===========
::

   import numpy as np
   import dbdreader

   # open a given file
   dbd=dbdreader.DBD("data/amadeus-2014-204-05-000.sbd")

   # print what parameters are available:
   for i,p in enumerate(dbd.parameterNames):
       print("%2d: %s"%(i,p))

   # get the measured depth
   tm,depth=dbd.get("m_depth")

   # print maximum depth
   max_depth=depth.max()
   print("\nmax depth %f m"%(max_depth))

   # get lat lon
   lat,lon=dbd.get_xy("m_lat","m_lon")

   # interpolate roll speed on depth time
   tm,depth,roll,speed=dbd.get_sync("m_depth","m_roll","m_speed")
   print("\nmax speed %f m/s"%(np.nanmax(speed)))
