import dbdreader

pattern= "../data/amadeus-2014-*.[st]bd"
dbd=dbdreader.MultiDBD(pattern=pattern, cacheDir='../data/notherecac')
depth=dbd.get("m_depth")
Q
dbd=dbdreader.DBD("/home/lucas/gliderdata/helgoland201407/hd/sebastian-2014-227-00-160.dbd", cacheDir='../data/cac')

depth=dbd.get("m_depth")
print(depth[0].shape)
print(depth[0].mean())
