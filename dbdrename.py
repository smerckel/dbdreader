#!/bin/env python3

# Copyright 2006,2007,2014 Lucas Merckelbach
#
# This file is part of dbdreader.
#
# dbdreader is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# dbdreader is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with dbdreader.  If not, see <http://www.gnu.org/licenses/>.
#

import sys
import os
import re
import argparse


parser = argparse.ArgumentParser(
    prog=__name__,
    description='''Program to rename dbd files and friends from numeric format to long format, or vice versa,
    or convert the long format into a sortable name or the original Webb Research long format,
    or decompress LZ4 compressed files.''',
    epilog='')

parser.add_argument('filenames', nargs="*", help="Filename(s) to process")
parser.add_argument('-s', action='store_true', default=True, help='Ensures long format filenames are sortable')
parser.add_argument('-n', action='store_true', help='Keeps the original long format filenames (which do not sort correctly).')
parser.add_argument('-c', '--convertToSortable', action='store_true', help='Converts files from original long format to a sortable long format')
parser.add_argument('-C', '--convertToOriginal', action='store_true', help='Converts files from a sortable long format to the original long format')


def makeSortable(filename):
    [basename,ext]=filename.split('.')
    [g,y,d,m,s]=basename.split('-')
    s="%03d"%(int(s))
    m="%02d"%(int(m))
    d="%03d"%(int(d))
    basename="-".join([g,y,d,m,s])
    filename=".".join([basename,ext])
    return(filename)
    

args = parser.parse_args()


for i in args.filenames:
    fd=open(i,'br')
    ID=fd.readline().decode('ascii').strip()
    ignoreIt=False
    if ID=='dbd_label:    DBD(dinkum_binary_data)file':
        for j in range(4):
            shortfilename=fd.readline().decode('ascii').strip()
        longfilename=fd.readline().decode('ascii').strip()
        shortfilename=re.sub("^.* ","",shortfilename)
        longfilename=re.sub("^.* ","",longfilename)
        extension=re.sub("^.*\.","",i)
        shortfilename+="."+extension
        longfilename+="."+extension
    elif "the8x3_filename" in ID: # mlg file apparently...
        longfilename=fd.readline().decode('ascii').strip()
        tmp=fd.readline().decode('ascii').strip()
        if 'mlg' in tmp:
            extension='.mlg'
        else:
            extension='.nlg'
        shortfilename=re.sub("^the8x3_filename: +","",ID+extension)

        longfilename=re.sub("^full_filename: +","",longfilename)+extension
    else:
        sys.stderr.write("Ignoring %s\n"%(i))
        ignoreIt=True
    if not ignoreIt:
        command=None
        if args.convertToSortable or args.convertToOriginal: # input filename must be the longfilename
            # check if we have a longfilename
            if i not in [longfilename,makeSortable(longfilename)]:
                print("Chose to ignore processing ",i)
            else:
                if i==makeSortable(longfilename) and args.convertToOriginal:
                    # switch to old format
                    command="mv "+i+" "+longfilename
                elif i==longfilename and args.convertToSortable:
                    command="mv "+longfilename+" "+makeSortable(longfilename)
                else:
                    print("ignoring "+i)
        else: # changing from long to short names or vice versa
            if args.s and not args.n:
                longfilename=makeSortable(longfilename)
            if i==shortfilename:
                command="mv "+shortfilename+" "+longfilename
            else:
                command="mv "+longfilename+" "+shortfilename
        if command!=None:
            print("command: ",command)
            R=os.system(command)
            if R!=0:
                raise ValueError("Could not execute %s"%(command))
    fd.close()
