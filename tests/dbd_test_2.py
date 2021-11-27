import dbdreader
import numpy
import glob
import os


os.chdir(
    os.path.dirname(
        __file__
    )
)


variable = 'm_battery'


print('Big endian file (Slocum G2, Persistor - Motorola MC68CK332)')
dbds = glob.glob('../data/amadeus*bd')
dbd = dbdreader.MultiDBD(filenames=dbds, cacheDir='../data/cac')
timestamps, data = dbd.get(variable)
print('timestamp min =', numpy.min(timestamps))
print('timestamp avg =', numpy.mean(timestamps))
print('timestamp max =', numpy.max(timestamps))
print(variable, 'min =', numpy.min(data))
print(variable, 'avg =', numpy.mean(data))
print(variable, 'max =', numpy.max(data))
print()


print('Little endian file (Slocum G3, ARM)')
dbds2 = glob.glob('../data/unit_887*bd')
dbd2 = dbdreader.MultiDBD(filenames=dbds2, cacheDir='../data/cac')
timestamps2, data2 = dbd2.get(variable)
print('timestamp min =', numpy.min(timestamps2))
print('timestamp avg =', numpy.mean(timestamps2))
print('timestamp max =', numpy.max(timestamps2))
print(variable, 'min =', numpy.min(data2))
print(variable, 'avg =', numpy.mean(data2))
print(variable, 'max =', numpy.max(data2))
print()


cac_dir = '/tmp/cac2'
glider_dirs = glob.glob('/tmp/gliders2/unit*')
for glider_dir in glider_dirs:
    glider = os.path.basename(glider_dir)
    dbds = glob.glob(
        os.path.join(glider_dir, 'from-glider', 'unit*bd')
    )
    if len(dbds) == 0:
        continue
    print(glider)
    dbd = dbdreader.MultiDBD(
        filenames=dbds, cacheDir=cac_dir
    )
    timestamps, data = dbd.get(variable)
    print('timestamp min =', numpy.min(timestamps))
    print('timestamp avg =', numpy.mean(timestamps))
    print('timestamp max =', numpy.max(timestamps))
    print(variable, 'min =', numpy.min(data))
    print(variable, 'avg =', numpy.mean(data))
    print(variable, 'max =', numpy.max(data))
    print()
