import dbdreader
import numpy
import glob
import os


os.chdir(
    os.path.dirname(
        __file__
    )
)


print('Big endian file (Slogum G2, Persistor - Motorola MC68CK332)')
dbds = glob.glob('../data/amadeus*bd')
dbd = dbdreader.MultiDBD(filenames=dbds, cacheDir='../data/cac')
timestamps, data = dbd.get('m_battery')
print('timestamp min =', numpy.min(timestamps))
print('timestamp avg =', numpy.mean(timestamps))
print('timestamp max =', numpy.max(timestamps))
print('data min =', numpy.min(data))
print('data avg =', numpy.mean(data))
print('data max =', numpy.max(data))
print()


print('Little endian file (Slocum G3, ARM)')
dbds2 = glob.glob('../data/unit_887*bd')
dbd2 = dbdreader.MultiDBD(filenames=dbds2, cacheDir='../data/cac')
timestamps2, data2 = dbd2.get('m_battery')
print('timestamp min =', numpy.min(timestamps2))
print('timestamp avg =', numpy.mean(timestamps2))
print('timestamp max =', numpy.max(timestamps2))
print('data min =', numpy.min(data2))
print('data avg =', numpy.mean(data2))
print('data max =', numpy.max(data2))