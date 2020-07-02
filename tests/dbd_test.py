import sys
sys.path.insert(0, "..")

import dbdreader


#pattern= "../data/amadeus-2014-*.[st]bd"
#dbd=dbdreader.MultiDBD(pattern=pattern, cacheDir='../data/notherecac')
#depth=dbd.get("m_depth")

dbd=dbdreader.MultiDBD(pattern="/home/lucas/gliderdata/helgoland201407/hd/sebastian-2014-227-00-16?.?bd")
x = dbd.get_CTD_sync()

S = 29407.397545337677
print(x[1].sum()-S)
Q

ballast, pitch, alt, roll= dbd.get("m_ballast_pumped", "m_pitch","m_altitude", "m_roll" )
Q


depth = dbd.get("m_depth")

depth, roll = dbd.get("m_depth", "m_roll")

lt, ln = dbd.get_xy("m_gps_lat", "m_gps_lon")
tm, ballast, pitch, alt, roll= dbd.get_sync("m_ballast_pumped", "m_pitch","m_altitude", "m_roll" )
Q
t, d, r, lat =dbd.get_sync("m_depth", ["m_roll", "m_lat"])
t1, d1, r1, lat1 =dbd.get_sync("m_depth", "m_roll", "m_lat")

x =dbd.get_list("m_depth", "m_roll", "m_lat", return_nans=True)


dbd=dbdreader.MultiDBD(pattern="/home/lucas/gliderdata/helgoland201407/hd/sebastian-2014-227-00-16?.[de]bd")
x = dbd.get("m_depth", "m_roll", "m_lat")

depth = dbd.get("m_depth")
x = dbd.get_sync("m_depth", "m_roll", "m_lat", "sci_water_temp")

lt, ln = dbd.get_xy("m_gps_lat", "m_gps_lon")

x = dbd.get_CTD_sync("m_depth")

#t, d, lat, lon = dbd.get_sync("m_depth",'m_lat','m_lon')

#t, d, r, lat, T = dbd.get_sync("m_depth", "m_roll", "m_lat", "sci_water_temp")
#x = dbd.get_list("m_depth", "m_roll", "m_lat")

#t, d, r, lat =dbd.get_sync("m_depth", ["m_roll", "m_lat", "sci_water_temp"])
