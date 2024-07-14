import dbdreader

cachedir = './cac/'
dbdreader.DBDCache(cachedir)

indir = './realtime_raw/'
search='*.[t|s]bd'


dbd = dbdreader.MultiDBD(pattern=f'{indir}/{search}')

sensors = ['sci_water_temp', 'sci_oxy4_oxygen']

fns = dbdreader.DBDList([i for i in dbd.filenames if i.endswith('tbd')])
fns.sort()
fns_shortlist = fns[12:] # works
fns_shortlist = fns[8:] # does not work
fns_shortlist = fns[:8] # does not work

dbd = dbdreader.MultiDBD(fns_shortlist)

sensors = ['sci_water_temp', 'sci_oxy4_oxygen']
data = list(dbd.get_sync(*sensors))

QQ
dbd = dbdreader.MultiDBD(fns)

for fn in fns:
    tbd = dbdreader.DBD(fn)
    print(fn, tbd.cacheID)
    try:
        data = tbd.get_sync(*sensors) 
    except dbdreader.DbdError as e:
        print("failed", e)
        print("sci_oxy4_oxygen" in tbd.parameterNames)
Q
print(data[1])
print(data[2])


fn = "realtime_raw/hal_1002-2024-183-4-11.tbd"

tbd = dbdreader.DBD(fn)
data = tbd.get_sync(*sensors) 
