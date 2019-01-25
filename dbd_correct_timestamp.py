#!/bin/python3

import os
import sys

import dbdreader

if len(sys.argv)==1:
    raise ValueError("Supply one or more dbd/ebd files.")

for fn in sys.argv[1:]:
    if not os.path.isfile(fn):
        print("Skipping %s..."%(fn))
        continue
    try:
        dbd = dbdreader.DBD(fn)
    except:
        print("Skipping %s..."%(fn))
    else:
        fileopen_time = dbd.get_fileopen_time()
        os.utime(fn, times=(fileopen_time, fileopen_time))

