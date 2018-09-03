from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division
from __future__ import absolute_import
from future import standard_library
standard_library.install_aliases()
import numpy as np
import dbdreader

# open a given file

dbd=dbdreader.DBD("../data/amadeus-2014-204-05-000.sbd")

# print what parameters are available:

for i,p in enumerate(dbd.parameterNames):
    print("%2d: %s"%(i,p))

# get the measured depth

tm,depth=dbd.get("m_depth")

max_depth=depth.max()
print("\nmax depth %f m"%(max_depth))

# get lat lon
lat,lon=dbd.get_xy("m_lat","m_lon")

# interpolate roll speed on depth time
tm,depth,roll,speed=dbd.get_sync("m_depth",["m_roll","m_speed"])

print("\nmax speed %f m/s"%(speed.max()))

# close the file again.
dbd.close()
