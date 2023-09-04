# Copyright 2006,2007,2014, 2023 Lucas Merckelbach
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
6#
# You should have received a copy of the GNU General Public License
# along with dbdreader.  If not, see <http://www.gnu.org/licenses/>.
#

from collections import OrderedDict
import sys
import os
import argparse
import re



import dbdreader.decompress 


def _makeSortable(filename):
    [basename,ext]=filename.split('.')
    [g,y,d,m,s]=basename.split('-')
    s="%03d"%(int(s))
    m="%02d"%(int(m))
    d="%03d"%(int(d))
    basename="-".join([g,y,d,m,s])
    filename=".".join([basename,ext])
    return(filename)
    



def _get_short_and_long_filenames(lines, filename):
    ID=lines[0]
    ignoreIt=False
    shortfilename=''
    longfilename=''
    if ID=='dbd_label:    DBD(dinkum_binary_data)file':
        shortfilename=lines[4]
        longfilename=lines[5]
        shortfilename=re.sub("^.* ","",shortfilename)
        longfilename=re.sub("^.* ","",longfilename)
        extension=re.sub("^.*\.","",filename)
        shortfilename+="."+extension
        longfilename+="."+extension
    elif "the8x3_filename" in ID: # mlg file apparently...
        longfilename=lines[1]
        if filename.lower().endswith('mlg'):
            extension='.mlg'
        else:
            extension='.nlg'
        shortfilename=re.sub("^the8x3_filename: +","",ID+extension)

        longfilename=re.sub("^full_filename: +","",longfilename)+extension
    else:
        sys.stderr.write("Ignoring %s\n"%(filename))
        ignoreIt=True
    return ignoreIt, shortfilename, longfilename

def dbdrename():
    ''' Standalone script to rename dbd files

    Use dbdrename -h for help.
    '''
    parser = argparse.ArgumentParser(
        prog='dbdrename',
        description='''Program to rename dbd files and friends from numeric format to long format, or vice versa,
        or convert the long format into a sortable name or the original Webb Research long format,
        or decompress LZ4 compressed files.''',
        epilog='')

    parser.add_argument('filenames', nargs="*", help="Filename(s) to process")
    parser.add_argument('-s', action='store_true', default=True, help='Ensures long format filenames are sortable')
    parser.add_argument('-n', action='store_true', help='Keeps the original long format filenames (which do not sort correctly).')
    parser.add_argument('-c', '--convertToSortable', action='store_true', help='Converts files from original long format to a sortable long format')
    parser.add_argument('-C', '--convertToOriginal', action='store_true', help='Converts files from a sortable long format to the original long format')
    parser.add_argument('-x', '--decompress', action='store_true', help='Decompresses LZ4 comrpessed files.')
    parser.add_argument('-X', '--decompressAndRemoveCompressed', action='store_true', help='Decompresses LZ4 comrpessed files, and removes the compressed file')
    parser.add_argument('-d', '--doNotChangeNameFormat', action='store_true', help='Does not change the filename format. (Only useful in combination with -x or -X)')



    args = parser.parse_args()

    # override the default value of -s if -d is specified
    if args.doNotChangeNameFormat:
        args.s=False

    for i in args.filenames:
        if not os.path.exists(i):
            print(f"{i} does not exist. Ignoring.")
            continue
        if dbdreader.decompress.is_compressed(i):
            with dbdreader.decompress.CompressedFile(i) as fd:
                lines = [fd.readline().decode('ascii').strip() for j in range(7)]
        else:
            with open(i,'br') as fd:
                lines = [fd.readline().decode('ascii').strip() for j in range(7)]
        ignoreIt, shortfilename, longfilename = _get_short_and_long_filenames(lines, i)

        basename = os.path.basename(i)
        prefix = i.replace(basename, "")

        if not ignoreIt:
            command=None
            if args.convertToSortable or args.convertToOriginal: # input filename must be the longfilename
                # check if we have a longfilename
                if i not in [longfilename,_makeSortable(longfilename)]:
                    print("Chose to ignore processing ",i)
                else:
                    if i==_makeSortable(longfilename) and args.convertToOriginal:
                        # switch to old format
                        command="mv "+i+" "+longfilename
                        new_filename = longfilename
                    elif i==longfilename and args.convertToSortable:
                        command="mv "+longfilename+" "+_makeSortable(longfilename)
                        new_filename = _makeSortable(longfilename)
                    else:
                        print("ignoring "+i)
            else: # changing from long to short names or vice versa
                if not args.n and not args.s: # -d has been requested
                    new_filename = i
                    if args.decompress or args.decompressAndRemoveCompressed:
                        command = ""
                else: # create the new_filename by translating
                    if args.s and not args.n:
                        longfilename=_makeSortable(longfilename)
                    if basename==shortfilename:
                        new_filename = os.path.join(prefix, longfilename)
                        old_filename = os.path.join(prefix, shortfilename)
                        command = f"mv {old_filename} {new_filename}"
                    else:
                        new_filename = os.path.join(prefix, shortfilename)
                        old_filename = os.path.join(prefix, longfilename)
                        command = f"mv {old_filename} {new_filename}"

            if command!=None:
                target = new_filename
                if command:
                    R=os.system(command)
                else:
                    R=0
                msg = f"{i} ->"
                if R!=0:
                    raise ValueError("Could not execute %s"%(command))
                if args.decompress or args.decompressAndRemoveCompressed:
                    target = dbdreader.decompress.decompress_file(new_filename)
                    if args.decompressAndRemoveCompressed:
                        os.unlink(new_filename)
                        msg = f"{msg} {target}"
                    else:
                        msg = f"{msg} {target}/{new_filename}"
                else:
                    msg = f"{msg} {target}"
                print(msg)


''' =====================================================================================================

    cac_gen

    ===================================================================================================== '''


def _parse_line(line):
    fields=line.rstrip().split()
    s=dict(flag=fields[1],
           global_index=int(fields[2]),
           index=int(fields[3]),
           bytesize=int(fields[4]),
           name=fields[5],
           unit=fields[6])
    return s['name'],s

def _read_cac_file(fn):
    sensors=OrderedDict()
    fd=open(fn,'r')
    while True:
        line=fd.readline()
        if not line:
            break
        n,s=_parse_line(line)
        sensors[n]=s
    fd.close()
    return sensors

def _read_mbdlist(fn):
    params=[]
    fd=open(fn,'r')
    while True:
        line=fd.readline()
        if not line:
            break
        line=line.rstrip().lstrip()
        if not line:
            continue # empty line
        if line.startswith("#"):
            continue
        s=line.lower().split()
        params.append(s[0])
    fd.close()
    return params
        
def _generate_cac(s,params):
    # sort params:
    params_in_order=[]
    for k in list(s.keys()):
        if k in params:
            params_in_order.append(k)
    # set all indices to -1
    for v in s.values():
        v['index']=-1
        v['flag']='F'
    for i,p in enumerate(params_in_order):
        s[p]['index']=i
        s[p]['flag']='T'
    return s

def _write_cac(s,fd):
    for k,v in s.items():
        fd.write("s: %s%5d%5d%2d %s %s\n"%(v['flag'],
                                           v['global_index'],
                                           v['index'],
                                           v['bytesize'],
                                           v['name'],
                                           v['unit']))


def _generate_cac_file(mbdlist_filename,template,output):
    s=_read_cac_file(template)
    params=_read_mbdlist(mbdlist_filename)
    s=_generate_cac(s,params)
    if output:
        fd=open(output,'w')
        _write_cac(s,fd)
        fd.close()
    else:
        _write_cac(s,sys.stdout)


def cac_gen():
    ''' A script to generate cac files

    run cac_gen -h for more help.
    '''
    parser = argparse.ArgumentParser(
        prog='cac_gen',
        description='''A program to generate a valid cache file from a .dat file and a valid cache file for this
        glider.

        For example, if you have a cache file for an sbd file, and the sbdlist.dat got modified, then this programs
        let's you build a new cache file using the old cache file and new sdblist.dat file as input.
        ''',
        epilog='')

    parser.add_argument('sdblist',  help="sdblist.dat file, specifying which parameters are present in the binary files")
    parser.add_argument('cachefile', help="A valid and exisiting cache file for this glider.")
    parser.add_argument('outputfile', nargs="?", default=None, help="Output filename (writes to stdout if not speficied.)")

    args = parser.parse_args()
    _generate_cac_file(args.sdblist, args.cachefile, args.outputfile)



                
