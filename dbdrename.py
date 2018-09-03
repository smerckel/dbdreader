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
import getopt

def usage():
    print('')
    print('Script to flip back and forth between the long and short names of the')
    print('dbd or sbd files.')
    print('')
    print('Optionally supply -s to make the filenames sortable using sort()')
    print('or supply -n to keep the original filename')
    print('')
    print('supply -c to convert between old style to new style')
    print('supply -C to convert between new style to old style')
    print('Default is sorting activated.')
    print(' Lmm 27 Mar 2007')
    sys.exit(0)

def makeSortable(filename):
    [basename,ext]=filename.split('.')
    [g,y,d,m,s]=basename.split('-')
    s="%03d"%(int(s))
    m="%02d"%(int(m))
    d="%03d"%(int(d))
    basename="-".join([g,y,d,m,s])
    filename=".".join([basename,ext])
    return(filename)
    
SORT=True # default
CONVERTold=False # default
CONVERTnew=False # default
try:
    R=getopt.getopt(sys.argv[1:],'cCsnh')
except getopt.GetoptError:
    print("Wrong option(s)!")
    usage()
    
for (o,a) in R[0]:
    if o=='-s':
        SORT=True
    if o=='-n':
        SORT=False
    if o=='-c':
        CONVERTnew=True
    if o=='-C':
        CONVERTold=True

    if o=='-h':
        usage()
        

files=R[1]

for i in files:
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
        if CONVERTnew or CONVERTold: # input filename must be the longfilename
            # check if we have a longfilename
            if i not in [longfilename,makeSortable(longfilename)]:
                print("Chose to ignore processing ",i)
            else:
                if i==makeSortable(longfilename) and CONVERTold:
                    # switch to old format
                    command="mv "+i+" "+longfilename
                elif i==longfilename and CONVERTnew:
                    command="mv "+longfilename+" "+makeSortable(longfilename)
                else:
                    print("ignoring "+i)
        else: # changing from long to short names or vice versa
            if SORT:
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
