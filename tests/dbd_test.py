import dbdreader

dbd=dbdreader.DBD("/home/lucas/gliderdata/helgoland201407/hd/sebastian-2014-227-00-160.dbd")

depth=dbd.get("m_depth")
print(depth[0].shape)
print(depth[0].mean())
