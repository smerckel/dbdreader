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
tm,depth,roll,speed=dbd.get_sync("m_depth","m_roll","m_speed")

print("\nmax speed %f m/s"%(np.nanmax(speed)))

# close the file again.
dbd.close()
