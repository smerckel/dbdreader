#!/usr/bin/python

from collections import OrderedDict
import sys
    
def parse_line(line):
    fields=line.rstrip().split()
    s=dict(flag=fields[1],
           global_index=int(fields[2]),
           index=int(fields[3]),
           bytesize=int(fields[4]),
           name=fields[5],
           unit=fields[6])
    return s['name'],s

def read_cac_file(fn):
    sensors=OrderedDict()
    fd=open(fn,'r')
    while True:
        line=fd.readline()
        if not line:
            break
        n,s=parse_line(line)
        sensors[n]=s
    fd.close()
    return sensors

def read_mbdlist(fn):
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
        
def generate_cac(s,params):
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

def write_cac(s,fd):
    for k,v in s.items():
        fd.write("s: %s%5d%5d%2d %s %s\n"%(v['flag'],
                                           v['global_index'],
                                           v['index'],
                                           v['bytesize'],
                                           v['name'],
                                           v['unit']))


def main(mbdlist_filename,template,output):
    s=read_cac_file(template)
    params=read_mbdlist(mbdlist)
    s=generate_cac(s,params)
    if output:
        fd=open(output,'w')
        write_cac(s,fd)
        fd.close()
    else:
        write_cac(s,sys.stdout)


if __name__=="__main__":
    args=sys.argv[1:]
    if len(args)<=1 or len(args)>=4:
        sys.stderr.write("DBD cache file generator.\n")
        sys.stderr.write("Invocation:\n")
        sys.stderr.write("cac_gen.py <mbdlist.dat> <a_cac_file_for_this_glider.cac> [output.cac]:\n")
        sys.exit(1)
    if len(args)==2:
        output=None
    else:
        output=args[2].lower()
    mbdlist,template=args[:2]
    main(mbdlist,template,output)
