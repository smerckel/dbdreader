import warnings
import os
import struct
import time
import numpy
import glob
import re
import datetime
from calendar import timegm
import _dbdreader

def strptimeToEpoch(datestr, fmt):
    ''' Converts datestr into seconds

    Function to convert a date string into seconds since Epoch. 
    This function is not affected by the time zone used by the OS and
    interprets the date string in UTC.


    Args:
         datestr: datestr is an ascii string such as "2010 May 01"

         fmt:     date format such as %Y %b %d
    
    Returns:
         time since epoch in seconds
    '''
    ts = time.strptime(datestr , fmt)
    return timegm(ts)


def epochToDateTimeStr(seconds,dateformat="%Y%m%d",timeformat="%H:%M"):
    ''' Converts seconds since Epoch to date string
    
    This function converts seconds since Epoch to a datestr and timestr
    with user configurable formats.

    Args:
         seconds: seconds since Epoch

         dateformat: string defining how the date string should be formatted

         timeformat: string defining how the time string should be formatted

    Returns:
         tuple of datestring and timestring.
    '''
    d=datetime.datetime.utcfromtimestamp(seconds)
    datestr=d.strftime(dateformat)
    timestr=d.strftime(timeformat)
    return datestr,timestr


def __convertToDecimal(x):
    ''' Converts a latitiude or longitude in NMEA format to decimale degrees'''
    sign=numpy.sign(x)
    xAbs=numpy.abs(x)
    degrees=numpy.floor(xAbs/100.)
    minutes=xAbs-degrees*100
    decimalFormat=degrees+minutes/60.
    return decimalFormat*sign

def toDec(x,y=None):
    ''' NMEA style to decimal degree converter

    Args:
         x: latitiude or longitude in NMEA format

         y: optional latitiude or longitude in NMEA format

    Returns:
         decimal latitude (longitude) or tuple of decimal latitude and longitude
    '''
    if not y==None:
        X=__convertToDecimal(x)
        Y=__convertToDecimal(y)
        return X,Y
    return __convertToDecimal(x)


# required (and only tested) encoding version.
ENCODING_VER=5

HOME=os.environ['HOME']
CACHEDIR=os.path.join(HOME,'.dbdreader')

if not os.path.exists(CACHEDIR):
    os.makedirs(CACHEDIR)


DBD_ERROR_CACHE_NOT_FOUND=1
DBD_ERROR_NO_VALID_PARAMETERS=2
DBD_ERROR_NO_TIME_VARIABLE=3
DBD_ERROR_NO_FILE_CRITERIUM_SPECIFIED=4
DBD_ERROR_NO_FILES_FOUND=5
DBD_ERROR_NO_DATA_TO_INTERPOLATE_TO=6

class DbdError(Exception):
    def __init__(self,value=9,mesg=None):
        self.value=value
        self.mesg=mesg

    def __str__(self):
        if self.value==DBD_ERROR_NO_VALID_PARAMETERS:
            mesg='The requested parameter(s) was(were) not found.'
        elif self.value==DBD_ERROR_NO_TIME_VARIABLE:
            mesg='The time variable was not found.'
        elif self.value==DBD_ERROR_CACHE_NOT_FOUND:
            mesg='Cache file was not found.'
        elif self.value==DBD_ERROR_NO_FILE_CRITERIUM_SPECIFIED:
            mesg='No file specification supplied (list of filenames or pattern)'
        elif self.value==DBD_ERROR_NO_FILES_FOUND:
            mesg='No files were found.'
        elif self.value==DBD_ERROR_NO_DATA_TO_INTERPOLATE_TO:
            mesg='No data to interpolate to.'
        else:
            mesg='Undefined error.'
        if self.mesg:
            mesg+=self.mesg
        return mesg

    
'''

how the sbd files work (and presumably the other files as well)

header is acii, somewhere in here is specified how many lines the header
is.

then if, not factored, a list follows with the size of each variable and
whether or not it is in the list. If it is factored, this list should be
read from file.

Then the binary bit begins. the first n bytes are to be discarded, where n
is the number of parameters in the file. Don t know why this is though.

then, for each cycle there is a sequence of bytes, setting which parameters
are not updated (0), are updated, but have the same value as before (1) or
are completely new (2). Only when new, they appear in the file. The block
length between each state-sequence depends thus on the size of the parameters
that are actually newly updated.
When reading 4 or 8 bytes and convert them into a float or double, requires
the order to be reversed.


The proposed api

class DBD:
    methods:
        init (opens a file)
        close(closes a file)
        get(param)  (returns time and data for given variable)
        
    private methods:
        read_header
        read_sensor_list
        write_sensor_list

'''


class DBDList(list):
    ''' Object subclassed from list. The sort method defaults to sorting dbd 
        files and friends in the right order.

    '''
    def __init__(self,*p):
        list.__init__(self,*p)

    def __keyFilename(self,x):
        xx=re.sub("\.[demnst]bd","",os.path.basename(x))
        if "-" in xx:
            xxx=xx.split("-")
            n=sum([int(i)*10**j for i,j in zip(xxx[1:],[8,5,3,0])])
            return xxx[0]+"%d"%(n)
        else:
            return xx
                             
    def sort(self,cmp=None, key=None, reverse=False):
        ''' sorts filenames ensuring dbd files are in chronological order'''
        list.sort(self, key=self.__keyFilename, reverse=reverse)

class DBDPatternSelect(object):
    ''' A class for selecting dbd files based on a date condition.
        The class opens files and reads the headers only.

        Times are based on the opening time of the file only.

    '''
    cache = {}
    
    def __init__(self, date_format="%d %m %Y"):
        self.set_date_format(date_format)

        
    def set_date_format(self,date_format):
        ''' Set date format

        Sets the date format used to interpret the from_date and until_dates.

        Args:
            date_format: string
                example "%H %d %m %Y"
        
        Returns:
             None
        '''
        self.date_format=date_format

    def get_date_format(self):
        ''' Returns current date format string 

        Args:
    
        Returns:
            date_format string
        '''
        return self.date_format


    def select(self,pattern=None,filenames=[],from_date=None,until_date=None):
        ''' select the filenames

        This method selects the filenames given a filename list or search 
        pattern and given time limits.

        Args:
            pattern: string

            filenames: list of filenames

            from_date: None | string

            until_date: None | string

        Returns:
             list of filenames that match the criteria

        Raises:
             ValueError if nor pattern or filenames is given.
        '''

        all_filenames = self.get_filenames(pattern, filenames)
        
        if not from_date and not until_date:
            # just get all files.
            t0=t1=None
            return all_filenames
        else:
            if from_date:
                t0=strptimeToEpoch(from_date,self.date_format)
            else:
                t0=1
            if until_date:
                t1=strptimeToEpoch(until_date,self.date_format)
            else:
                t1=1e11
            return self.__select(all_filenames,t0,t1)

    def bins(self, pattern=None, filenames=None, width=86400, t_start=None, t_end=None):
        '''list filenames, binned in time

        The method makes a list of all filenames, matching either
        pattern or filenames and bins these in time windows of width. If
        t_start and t_end are not given, they are computed from the first and
        last timestamps of the files specified, respectively.


        This method returns a list of tuples, where each tuple
        contains the centred time of the bin, and a list of all
        filenames that fall within this bin.

        Args:
            pattern: string

            filenames: list of filenames
        
            width: width of time bin in seconds

            t_start: None | timestamp in seconds since 1/1/1970

            t-end: None | timestamp in seconds since 1/1/1970

        Returns:
             list of filenames that match the criteria

        Raises:
             ValueError if nor pattern or filenames is given.
        
        '''
        fns = self.get_filenames(pattern, filenames)
        if t_start is None:
            t_start = numpy.min(list(self.cache.keys()))
        if t_end is None:
            t_end = numpy.max(list(self.cache.keys()))
        bin_edges = numpy.arange(t_start, t_end+width, width)
        bins = [((left+right)/2, self.__select(fns, left, right))
                for left, right in zip(bin_edges[0:-1], bin_edges[1:])]
        return bins

        
    def get_filenames(self, pattern, filenames):
        if not pattern and not filenames:
            raise ValueError("Expected some pattern to search files for or file list.")
        if pattern:
            all_filenames=DBDList(glob.glob(pattern))
        elif filenames:
            all_filenames=DBDList(filenames)
        all_filenames.sort()
        self.__update_cache(all_filenames)
        return all_filenames
    
    def __update_cache(self, fns):
        cached_filenames = DBDList(self.cache.values())
        cached_filenames.sort()
        for fn in fns:
            if fn not in cached_filenames:
                dbd=DBD(fn)
                t_open=dbd.get_fileopen_time()
                dbd.close()
                self.cache[t_open]=fn
                
    def __select(self,fns,t0,t1):
        open_times = numpy.array(list(self.cache.keys()))
        open_times = numpy.sort(open_times)
        selected_times = open_times.compress(numpy.logical_and(open_times>=t0,
                                                          open_times<=t1))
        fns = DBDList([self.cache[t] for t in selected_times])
        fns.sort()
        return fns

            
                                                          
            
        
        
class DBDHeader(object):

    ''' Class to read the headers of DBD files. This file is typically used
        by DBD and MultiDBD and not directly.
    '''
    def __init__(self,cacheDir):
        self.keywords={'dbd_label':'string',
                       'total_num_sensors':'int',
                       'sensor_list_crc':'string',
                       'state_bytes_per_cycle':'int',
                       'sensors_per_cycle':'int',
                       'sensor_list_factored':'int',
                       'num_ascii_tags':'int',
                       'mission_name':'string',
                       'fileopen_time':'string',
                       'encoding_ver':'int',
                       'full_filename':'string',
                       'the8x3_filename':'string'}
        self.info={}
        self.cacheDir=cacheDir
        
    def read_header(self,fp):
        ''' read the header of the file, given by fp '''
        fp.seek(0)
        if not self.parse(fp.readline())=='dbd_label':
            raise ValueError("Seems not to be a valid DBD file")
        n_read=1
        while 1:
            self.parse(fp.readline())
            n_read+=1
            if 'num_ascii_tags' in self.info  and \
               self.info['num_ascii_tags']==n_read:
                break
        if self.info['encoding_ver']!=ENCODING_VER:
            raise ValueErro('Incompatible encoding version detected.')
        return self.info['sensor_list_factored']

    def read_cache(self,fp, fpcopy=None):
        ''' read cache file '''
        parameter=[]
        for i in range(self.info['total_num_sensors']):
            line=fp.readline().decode('ascii')
            if fpcopy!=None:
                fpcopy.write(line)
                parameters={}
            words=line.split()
            j=int(words[3]) # >=0? used : not used
            if j!=-1:
                name=words[5]
                unit=words[6]
                size=int(words[4])
                parameter.append((size,name,unit))
        return parameter

    # private methods
    def parse(self,line):
        # parses a binary datastream. So, first decode it to ascii.
        words=line.decode('ascii').rstrip().split(":")
        param=words[0]
        if param in self.keywords.keys():
            value=":".join(words[1:]).lstrip()
            if self.keywords[param]=='int':
                self.info[param]=int(value)
            else:
                self.info[param]=value
        return param

        
class DBD(object):
    ''' Class to read a single DBD type file 

        Args:
             filename: string

             cachedDir: string pointing to the cacheDir | None (default)
    
    '''
    def __init__(self,filename,cacheDir=None):

        self.filename=filename
        self.fp=open(filename,'br')
        if cacheDir==None:
            self.cacheDir=CACHEDIR
        else:
            self.cacheDir=cacheDir
        self.headerInfo,parameterInfo,self.cacheFound=self.__read_header()
        # number of bytes each states section consists of:
        self.n_state_bytes=self.headerInfo['state_bytes_per_cycle']
        # size of variables used
        self.byteSizes=tuple([i[0] for i in parameterInfo])
        # note: python <2.6 can't index tuples.
        self.parameterNames=[i[1] for i in parameterInfo]
        self.parameterUnits=dict((i[1],i[2]) for i in parameterInfo)
        self.timeVariable=self.__set_timeVariable()

    def get_mission_name(self):
        ''' Returns the mission name such as micro.mi '''
        return self.headerInfo['mission_name'].lower()

    def get_fileopen_time(self):
        ''' Returns the time stamp of opening the file in UTC '''
        return self.__get_fileopen_time()

    def close(self):
        ''' Closes a DBD file '''
        return self.fp.close()

    def get(self,parameter,decimalLatLon=True,discardBadLatLon=True):
        '''returns time and parameter data for requested parameter 
        
        This method reads the requested parameter, and convert it
        optionally to decimal format if the parameter is latitude-like
        or longitude-like

        Args:
             parameter: string of name of parameter

        Returns:
             tuple with time and value vectors

        Raises: 
             DbdError when the requested parameter cannot be read.
        '''
        return self.__get([parameter],decimalLatLon,discardBadLatLon)

    def get_list(self,parameter_list,decimalLatLon=True,discardBadLatLon=True):
        ''' Returns time and value tuples for a list of requested parameters
        

        This method returns time and values tuples for a list of parameters. It
        is basically a short-hand for a looped get() method.
        
        Note that each parameter comes with its own time base. No interpolation
        is done. Use get_sync() for that in stead.

        Args:
            parameter_list: list of strings of parameters

            decimalLatLon: bool. If True, NMEA lats and friends are converted
                           to decimal values.

            discardBadlatLon: bool. If True, unrealistic lat/lon values are 
                              discared
        Returns:
            list of tuples of time and value vectors
        '''
        return self.__get(parameter_list,decimalLatLon,discardBadLatLon)
        
    def get_xy(self,parameter_x,parameter_y,decimalLatLon=True):
        ''' Returns values of parameter_x and paramter_y

        For parameters parameter_x and parameter_y this method returns a tuple 
        with the values of both parameters. If necessary, the time base of 
        parameter_y is interpolated onto the one of parameter_x.

        Args:
            parameter_x: string. Name of 'x' parameter

            parameter_y: string. Name of 'y' parameter

            decimalLatLon: bool. If True, NMEA lats and friends are converted
                           to decimal values.

            discardBadlatLon: bool. If True, unrealistic lat/lon values are 
                              discared
        Returns:
            tuple of value vectors
        '''    
        return self.__get_xy(parameter_x,parameter_y,decimalLatLon)


    def get_sync(self,parameter,sync_parameters,decimalLatLon=True,discardBadLatLon=True):
        ''' returns a list of values from parameters, all interpolated to the 
            time base of the first paremeter

        This method is used if a number of parameters should be interpolated 
        onto the same time base.

        Args:
            parameter: string. Key parameter, the time base of which is used to
                       interpolate other parameters to.

            sync_parameters: list of strings. These are the names of the 
                       parameters that should be interpolated to the time base
                       of parameter
    
            decimalLatLon: bool. If True, NMEA lats and friends are converted
                           to decimal values.

            discardBadlatLon: bool. If True, unrealistic lat/lon values are 
                              discared
        
        Returns:
            a list with time, values of parameter, and values of all 
            sync_parameters.

        Example:
            
            get_sync('m_water_pressure',['m_water_cond','m_water_temp'])
        '''
        return self.__get_sync(parameter,sync_parameters,decimalLatLon,discardBadLatLon)

    def has_parameter(self,parameter):
        ''' Check wheter this file knows parameter
        
        Args:
            parameter: string

        Returns:
            True if parameter is in the list, or False if not '''
        return (parameter in self.parameterNames)
    
    # Private methods:

    def __get_fileopen_time(self):
        datestr=self.headerInfo['fileopen_time'].replace("_"," ")
        fmt="%a %b %d %H:%M:%S %Y"
        seconds=strptimeToEpoch(datestr, fmt)
        return seconds
    
    def __set_timeVariable(self):
        if 'm_present_time' in self.parameterNames:
            return 'm_present_time'
        else:
            return 'sci_m_present_time'


    def __get(self,parameters,decimalLatLon=True,discardBadLatLon=False):
        ''' returns time and parameter data for requested parameter '''
        if not self.cacheFound:
            cache_file=self.headerInfo['sensor_list_crc']
            raise DbdError(DBD_ERROR_CACHE_NOT_FOUND,\
                               ' Cache file %s for %s was not found in the cache directory (%s).'%(cache_file,self.filename,self.cacheDir))
        number_of_parameters=len(parameters)
        ValidParameters=self.__get_valid_parameters(parameters)
        if len(ValidParameters)==0:
            raise DbdError(DBD_ERROR_NO_VALID_PARAMETERS,
                           "\nRequested list: %s"%(parameters.__str__()))
        if not self.timeVariable in self.parameterNames:
            raise DbdError(DBD_ERROR_NO_TIME_VARIABLE)
        # OK, we have some parameters to return:
        ti=self.parameterNames.index(self.timeVariable)
        tmp=[self.parameterNames.index(parameter)
             for parameter in ValidParameters]
        idx_sorted=numpy.argsort(tmp)
        vi=tuple([tmp[i] for i in idx_sorted])
        self.n_sensors=self.headerInfo['sensors_per_cycle']
        r=_dbdreader.get(self.n_state_bytes,
                         self.n_sensors,
                         self.fp_binary_start,
                         self.byteSizes,
                         self.filename,
                         ti,
                         vi)
        nParameters=len(ValidParameters)
        # it seems that wrc version skips the initial line.
        s=[(numpy.array(t[1:]),numpy.array(v[1:])) for
           t,v in zip(r[:nParameters],r[nParameters:])]
        # convert to decimal lat lon if applicable:
        sortedParameters=[ValidParameters[i] for i in idx_sorted]
        if decimalLatLon:
            LatLonMask=map(self.__is_latlon_parameter,sortedParameters)
            for i,T in enumerate(LatLonMask):
                if T:
                    s[i]=(s[i][0],toDec(s[i][1]))
        if discardBadLatLon:
            LatLonMask=map(self.__is_latlon_parameter,sortedParameters)
            for i,T in enumerate(LatLonMask):
                if T:
                    idx=numpy.where(s[i][1]<696960)
                    s[i]=(s[i][0][idx],s[i][1][idx])
        if number_of_parameters>1:
            t=[None for i in range(number_of_parameters)]
            for i,j in enumerate(idx_sorted):
                paramName=ValidParameters[j]
                column=parameters.index(paramName)
                t[column]=s[i]
                parameters[column]=None # ensures that if there are
                                        # more parameters requested,
                                        # the next column is found
            return t
        else:
            return s[0]

    def __get_xy(self,parameterx,parametery,decimalLatLon=True,
                 discardBadLatLon=True):
        ''' returns data for x and y parameters. The y parameter is interpolated
            to the time stamps of parameter x
        '''    
        t,x,y=self.__get_sync(parameterx,[parametery],decimalLatLon,discardBadLatLon);
        if len(t)==0:
            return (x,x)
        else:
            return (x,y)

    def __get_sync(self,x,y,decimalLatLon=True,discardBadLatLon=True):
        '''
            x: dbdparameter name

            y: list of dbd parameter names

            returns a list of
            t, parameter x, parameter y0, parameter y1, ...
            where the y parameters are synchronized to x.

            if decimalLatLon, then all lat/lon type variables are converted
            to decimal values prior to interpolation.

            example:
            
            get_sync('m_water_pressure',['m_water_cond','m_water_temp'])
        '''
        params=[x]+list(y)
        r=self.__get(params,decimalLatLon,discardBadLatLon)
        # check whether all returned something.
        all_parameters_returned=True
        for i,p in zip(r,params):
            if i==None:
                raise DbdError(DBD_ERROR_NO_VALID_PARAMETERS,
                               " (%s)"%(p))
        t=r[0][0]
        if len(t)==0:
            raise DbdError(DBD_ERROR_NO_DATA_TO_INTERPOLATE_TO)

        s=[t,r[0][1]]
        for i in r[1:]:
            if len(i[0])==0:
                # no data for this parameter. Subs with nans
                s.append(t.copy()*numpy.nan)
            else:
                s.append(numpy.interp(t,i[0],i[1]))
        return s

    def __get_valid_parameters(self,parameters):
        validParameters=[i for i in parameters if i in self.parameterNames]
        return validParameters

    def __is_latlon_parameter(self,x):
        if 'lat' in x or 'lon' in x:
            return True
        else:
            return False

    def __read_header(self):
        dbdheader=DBDHeader(self.cacheDir)
        factored=dbdheader.read_header(self.fp)
        # determine cache file name
        tmp=dbdheader.info['sensor_list_crc'].lower()
        cacheFilename=os.path.join(self.cacheDir,tmp+".cac")
        cacheFound=True # unless proven otherwise...
        parameter=[]
        if factored==1:
            # read sensorlist from cache
            if os.path.exists(cacheFilename):
                fpCache=open(cacheFilename,'br')
                parameter=dbdheader.read_cache(fpCache)
                fpCache.close()
            else:
                cacheFound=False
        else:
            # read sensorlist from same file and copy
            if not os.path.exists(cacheFilename):
                # only write, when not existing.
                fpCache=open(cacheFilename,'w')
                parameter=dbdheader.read_cache(self.fp,fpCache)
                fpCache.close()
            else:
                # keep reading from same file
                parameter=dbdheader.read_cache(self.fp)
        self.fp_binary_start=self.fp.tell() # marks the start of the
                                            # binary part of the file
        return (dbdheader.info,parameter,cacheFound)

    def __get_by_read_per_byte(self,parameter):
        ''' method that reads the file byte by byte and processes
            accordingly. As opposed to read the whole file in memory and do the
            processing then.'''
        # first n bytes are not used?
        self.n_sensors=self.headerInfo['sensors_per_cycle']
        self.fp.seek(0,2) # move to end of file
        fp_end=self.fp.tell()
        self.fp.seek(self.fp_binary_start+17)# set file pointer to
                                             # start binary block (17
                                             # positions are used for
                                             # something else, which I
                                             # can't figure out
        paramidx=(self.ti,self.vi)
        R=dict((i,[]) for i in paramidx)
        while True:
            offsets,chunksize=self.__read_state_bytes(paramidx)
            fp=self.fp.tell()
            if offsets!=None:
                # we found at least one value we would like to read, otherwise skip directly to the
                # next state block.
                for offset,idx in zip(offsets,paramidx):
                    if offset!=-1:
                        self.fp.seek(fp+offset)
                        x=self.fp.read(self.byteSizes[idx])
                        xs=self.__convert_bytearray(x)
                        R[idx].append(xs)
                    else:
                        R[idx].append(R[idx][-1])
            # jump to the next state block
            if fp+chunksize+1>=fp_end:
                # jumped beyond the end.
                break
            self.fp.seek(fp+chunksize+1)
        return [R[i] for i in paramidx]

    def __get_by_read_per_chunk(self,parameter):
        ''' method that reads the file chunk by chunk.
        '''
        # first n bytes are not used?
        self.n_sensors=self.headerInfo['sensors_per_cycle']
        self.fp.seek(0,2) # move to end of file
        fp_end=self.fp.tell()
        self.fp.seek(self.fp_binary_start+17)# set file pointer to
                                             # start binary block (17
                                             # positions are used for
                                             # something else, which I
                                             # can't figure out
        paramidx=(self.ti,self.vi)
        R=dict((i,[]) for i in paramidx)
        while True:
            offsets,chunksize=self.__read_state_bytes(paramidx)
            fp=self.fp.tell()
            if offsets!=None:
                # we found at least one value we would like to read, otherwise skip directly to the
                # next state block.
                chunk=self.fp.read(chunksize+1)
                for offset,idx in zip(offsets,paramidx):
                    if offset!=-1:
                        s=self.byteSizes[idx]
                        xs=self.__convert_bytearray(chunk[offset:offset+s])
                        R[idx].append(xs)
                    else:
                        R[idx].append(R[idx][-1])
            else:
                self.fp.seek(fp+chunksize+1)
            
            if fp+chunksize+1>=fp_end:
                # jumped beyond the end.
                break
        return [R[i] for i in paramidx]


    def __read_state_bytes(self,reqd_variables):
        ''' reads state bytes and returns:
            offsets, chunksize
            offsets: list of offsets to read the variables
                     if 0: copy previous
            if None, chunksize is returned, not all required variables
                     were updated.
        '''
        bits_per_byte=8
        bits_per_field=2
        mask=3
        bitshift=bits_per_byte-bits_per_field
        fields_per_byte=bits_per_byte/bits_per_field
        offset=0
        n=0
        vi=0
        offsets=[0 for i in range(len(reqd_variables))]
        state_bytes=self.fp.read(self.n_state_bytes)
        for sb in bytearray(state_bytes):
            for fld in range(fields_per_byte):
                field=(sb>>bitshift) & mask
                sb<<=2
                if field==2:
                    # variable is updated
                    if vi in reqd_variables:
                        # this variable is asked for.
                        # so record its position.
                        offsets[n]=offset
                        n+=1
                    offset+=self.byteSizes[vi]
                if field==1 and (vi in reqd_variables):
                    # this variable is asked for, but has an old
                    # variable. So not being read
                    offsets[n]=-1
                    n+=1
                vi+=1 # next variable.
        if n==len(reqd_variables):
            return offsets,offset
        else:
            return None,offset

    def __convert_bytearray(self,bs):
        ''' converts a byte sequence of length 4 or 8 bytes
            to a floating point.'''
        # the byte sequence read should be reversed and then unpacked.
        # this may be a costly operation...
        bsr="".join([i for i in bs[::-1]])
        if len(bs)==4:
            return struct.unpack("f",bsr)[0]
        else:
            return struct.unpack("d",bsr)[0]


class MultiDBD(object):
    '''Opens multiple dbd files for reading

    
    This class is intended for reading multiple dbd files and treating
    them as one.
    
    Args:
        pattern: string. String which may contain wild cards to 
        select filenames

        filenames: list of strings with filenames.

        cacheDir: string pointing to dir with cache files | none (Default)

        ensure_paired: bool only tuples of dbd/edb files will be retained

        include_paired: bool automatically include match dbd files

        banned_missions: list. list of mission names that should be disregarded.
        missions: list list of missions names that should be considered only.
        maxfiles: int. maximum number of files to be read:
        >0: the first n files are read
        <0: the last n files are read.

    '''
    def __init__(self,filenames=None,pattern=None,cacheDir=None,ensure_paired=False,
                 include_paired=False,banned_missions=[],missions=[],
                 max_files=None):
        self.__ignore_cache=[]
        self.banned_missions=banned_missions
        self.missions=missions
        self.mission_list=[]
        if not filenames and not pattern:
            raise DbdError(DBD_ERROR_NO_FILE_CRITERIUM_SPECIFIED)
        fns=DBDList()
        if filenames:
            fns+=filenames
        if pattern:
            fns+=glob.glob(pattern)
        if len(fns)==0:
            raise DbdError(DBD_ERROR_NO_FILES_FOUND)
        fns.sort()
        if max_files and max_files>0:
            self.filenames=fns[:max_files]
        elif max_files and max_files<0:
            self.filenames=fns[max_files:]
        else:
            self.filenames=fns

        self.__update_dbd_inventory()

        if include_paired:
            #ensure_paired=True
            self.__add_paired_filenames()
            self.__update_dbd_inventory()

        if ensure_paired:
            self.pruned_files=self.__prune_unmatched()
        #
        self.parameterNames=dict((k,self.__getParameterList(v)) \
                                     for k,v in self.dbds.items())
        self.parameterUnits=self.__getParameterUnits()
        #
        self.time_limits_dataset=(None,None)
        self.time_limits=[None,None]
        self.set_time_limits()
    
##### public methods
    def get(self,parameter,decimalLatLon=True):
        '''Returns time and parameter data for requested parameter 
        
        This method reads the requested parameter, and convert it
        optionally to decimal format if the parameter is latitude-like
        or longitude-like

        Args:
             parameter: string of name of parameter

        Returns:
             tuple with time and value vectors

        Raises: 
             DbdError when the requested parameter cannot be read.
        '''

        if parameter in self.parameterNames['sci']:
            return self.__worker("get","sci",parameter,decimalLatLon)
        else:
            return self.__worker("get","eng",parameter,decimalLatLon)
        

    def get_xy(self,parameter_x,parameter_y,decimalLatLon=True):
        '''Returns values of parameter_x and paramter_y

        For parameters parameter_x and parameter_y this method returns a tuple 
        with the values of both parameters. If necessary, the time base of 
        parameter_y is interpolated onto the one of parameter_x.

        Args:
            parameter_x: string. Name of 'x' parameter

            parameter_y: string. Name of 'y' parameter

            decimalLatLon: bool. If True, NMEA lats and friends are converted
                           to decimal values.

            discardBadlatLon: bool. If True, unrealistic lat/lon values are 
                              discared

        Returns:
            tuple of value vectors
        '''    
        fts={True:'sci',False:'eng'}
        pxSci=parameter_x in self.parameterNames['sci']
        pySci=parameter_y in self.parameterNames['sci']
        if not (pxSci ^ pySci):
            # both px and py parameters or of the same type
            return self.__worker("get_xy",fts[pxSci],parameter_x,parameter_y,decimalLatLon)
        else:
            # both parameters are from differnent file types.
            x=self.__worker("get",fts[pxSci],parameter_x,decimalLatLon)
            y=self.__worker("get",fts[pySci],parameter_y,decimalLatLon)
            yi=numpy.interp(x[0],y[0],y[1])
            return x[1],yi

    def get_sync(self,parameter,sync_parameters,decimalLatLon=True):
        '''Returns a list of values from parameters, all interpolated to the 
            time base of the first paremeter

        This method is used if a number of parameters should be interpolated 
        onto the same time base.

        Args:
            parameter: string. Key parameter, the time base of which is used to
                       interpolate other parameters to.

            sync_parameters: list of strings. These are the names of the 
                       parameters that should be interpolated to the time base
                       of parameter
    
            decimalLatLon: bool. If True, NMEA lats and friends are converted
                           to decimal values.

            discardBadlatLon: bool. If True, unrealistic lat/lon values are 
                              discared
        
        Returns:
            a list with time, values of parameter, and values of all 
            sync_parameters.

        Example:
            
            get_sync('m_water_pressure',['m_water_cond','m_water_temp'])
        '''
        fts={True:'sci',False:'eng'}
        pxSci=parameter in self.parameterNames['sci']
        pySci=[i in self.parameterNames['sci'] for i in sync_parameters]
        allSamePySci=len(set(pySci))==1
        if allSamePySci and not (pxSci ^ pySci[0] ):
            # both px and all py parameters are of the same type
            return self.__worker("get_sync",fts[pxSci],\
                                     parameter,sync_parameters,decimalLatLon)
        else:
            # the parameters in y are of mixed type, we have to sieve them out...
            x=self.__worker("get",fts[pxSci],parameter,decimalLatLon)
            y=[self.__worker("get",fts[v],n,decimalLatLon) for n,v in 
               zip(sync_parameters,pySci)]
            yi=[numpy.interp(x[0],_y[0],_y[1]) for _y in y]
            return numpy.vstack((x,yi))
    
    def get_list(self,parameter_list,decimalLatLon=True):
        '''Returns time and value tuples for a list of requested parameters


        This method returns time and values tuples for a list of parameters. It
        is basically a short-hand for a looped get() method.
        
        Note that each parameter comes with its own time base. No interpolation
        is done. Use get_sync() for that in stead.

        Args:
            parameter_list: list of strings of parameters

            decimalLatLon: bool. If True, NMEA lats and friends are converted to decimal values.

            discardBadlatLon: bool. If True, unrealistic lat/lon values are discared

        Returns:
            list of tuples of time and value vectors
        '''
        fts={True:'sci',False:'eng'}
        pSci=[i in self.parameterNames['sci'] for i in parameter_list]
        r=[self.__worker("get",fts[v],n,decimalLatLon) for n,v in 
               zip(parameter_list,pSci)]
        return r

    def has_parameter(self,parameter):
        '''Returns True if this instance has found parameter '''
        return (parameter in self.parameterNames['sci'] or parameter in self.parameterNames['eng'])

    @classmethod
    def isScienceDataFile(cls,fn):
        ''' return True if file fn is a science file'''
        return fn.endswith("ebd") | fn.endswith("tbd") | fn.endswith("nbd")

    def get_time_range(self,fmt="%d %b %Y %H:%M"):
        '''Get start and end date of the time range selection set

        Args:
            fmt: string. Determines how the time string is formatter

        Returns
            tuple with formatted time strings
        '''
        return self.__get_time_range(self.time_limits,fmt)

    def get_global_time_range(self,fmt="%d %b %Y %H:%M"):
        ''' Returns start and end dates of data set (all files) 

        Args:
            fmt: string. Determines how the time string is formatter

        Returns
            tuple with formatted time strings
        '''
        return self.__get_time_range(self.time_limits_dataset,fmt)

    def set_time_limits(self,minTimeUTC=None,maxTimeUTC=None):
        ''' set time limits for data to be returned by get() and friends.

        Args:
             minTimeUTC: lower time limit

             maxTimeUTC: upper time limit

        {minTimeUTC, maxTimeUTC} are expected in one of these formats:

        "%d %b %Y"  3 Mar 2014

        or

        "%d %b %Y %H:%M" 4 Apr 2014 12:21

        Returns:
             None
        '''
        if minTimeUTC:
            self.time_limits[0]=self.__convert_seconds(minTimeUTC)
        if maxTimeUTC:
            self.time_limits[1]=self.__convert_seconds(maxTimeUTC)
        self.__refresh_cache()

    def close(self):
        ''' close all open files '''
        for i in self.dbds['eng']+self.dbds['sci']:
            i.close()


#### private methods

    def __get_matching_fn(self,fn,format="base"):
        fnbase = os.path.basename(fn)
        extension = fnbase.split(os.path.extsep)[-1]
        
        if fn in [i.filename for i in self.dbds['eng']]:
            searchSpace = 'sci'
            matchingExtension = '%c%s'%(ord(extension[0])+1,extension[1:])
        else:
            searchSpace = 'eng'
            matchingExtension = '%c%s'%(ord(extension[0])-1,extension[1:])
        if format=="base":
            matchingFn = fnbase.replace(extension,matchingExtension)
        else:
            matchingFn = fn.replace(extension,matchingExtension)
        return matchingFn, searchSpace

    def __add_paired_filenames(self):
        to_add=[]
        for fn in self.filenames:
            mfn,searchSpace=self.__get_matching_fn(fn,format="full_path")
            if os.path.exists(mfn):
                to_add.append(mfn)
        self.filenames+=to_add
            
    def __get_matching_dbd(self,fn):
        '''returns matching dbd object corresponding to fn. If fn is not in the current list
           of accepted dbds, then None is returned.'''

        if fn not in self.filenames:
            return None
        # ok, the file is in the cache, which implies it is in self.dbds too.
        matchingFn,searchSpace=self.__get_matching_fn(fn,format="base")
        r = None
        for i in self.dbds[searchSpace]:
            if os.path.basename(i.filename) == matchingFn:
                r = i
                break
        return r

    def __prune(self,filelist):
        ''' prune all files in filelist.'''
        for tbr in filelist:
            self.filenames.remove(tbr)
        self.__update_dbd_inventory()
    
    def __prune_unmatched(self):
        ''' prune all files which don't have a science/engineering partner 
            returns list of removed files.'''
        to_be_removed=[fn for fn in self.filenames if not self.__get_matching_dbd(fn)]
        self.__prune(to_be_removed)
        return tuple(to_be_removed)


    def __convert_seconds(self,timestring):
        t_epoch=None
        try:
            t_epoch=strptimeToEpoch(timestring,"%d %b %Y")
        except:
            pass
        try:
            t_epoch=strptimeToEpoch(timestring,"%d %b %Y %H:%M")
        except:
            pass
        if not t_epoch:
            raise ValueError('Could not convert time string. Expect a format like "3 Mar" or "3 Mar 12:30".')
        return t_epoch

    def __refresh_cache(self):
        ''' Internal. Sets global and selected time limits, and a cache with those files
            that matche the time selection criterion
        '''
        self.__ignore_cache=[]
        self.__accept_cache=[]
        # min and max times of whole data set
        time_limits_dataset = [1e10, 0]
        # min and max times of selected data set (can be None)
        time_limits = self.time_limits
        
        # if no time_limits set, use all data.
        if not time_limits[0]:
            time_limits[0]=0
        if not time_limits[1]:
            time_limits[1]=1e10

        for dbd in self.dbds['eng']+self.dbds['sci']:
            t=dbd.get_fileopen_time()
            # set global time limits
            if t<time_limits_dataset[0]:
                time_limits_dataset[0]=t
            if t>time_limits_dataset[1]:
                time_limits_dataset[1]=t
            #
            if t<time_limits[0] or t>time_limits[1]:
                self.__ignore_cache.append(dbd) 
            else:
                self.__accept_cache.append(dbd)
                # this is a file that matches the selection criterion.
                if t<time_limits[0]:
                    time_limits[0]=t
                if t>time_limits[1]:
                    time_limits[1]=t
        self.time_limits_dataset=tuple(time_limits_dataset)
        time_limits[0]=max(time_limits[0],time_limits_dataset[0])
        time_limits[1]=min(time_limits[1],time_limits_dataset[1])

    def __format_time(self,t,fmt):
        tmp=datetime.datetime.utcfromtimestamp(t)
        return tmp.strftime(fmt)

    def __get_time_range(self,time_limits,fmt):
        if fmt=="%s":
            return time_limits
        else :
            return list(map(lambda x: self.__format_time(x,fmt), time_limits))

    def __update_dbd_inventory(self):
        self.dbds={'eng':[],'sci':[]}
        filenames=list(self.filenames)
        for fn in self.filenames:
            dbd=DBD(fn)
            mission_name=dbd.get_mission_name()
            dbd.close()
            if mission_name in self.banned_missions:
                filenames.remove(fn)
                continue
            if self.missions and mission_name not in self.missions:
                filenames.remove(fn)
                continue
            if mission_name not in self.mission_list:
                self.mission_list.append(mission_name)
            if self.isScienceDataFile(fn):
                self.dbds['sci'].append(dbd)
            else:
                self.dbds['eng'].append(dbd)
        if len(self.dbds['sci'])+len(self.dbds['eng'])==0:
            raise ValueError("All selected data files were banned.")
        self.parameterNames=dict((k,self.__getParameterList(v)) \
                                     for k,v in self.dbds.items())
        self.parameterUnits=self.__getParameterUnits()
        self.filenames=filenames
    
    def __getParameterUnits(self):
        dbds=self.dbds['eng']
        units=[]
        for i in dbds:
            units+=[j for j in i.parameterUnits.items()]
        dbds=self.dbds['sci']
        for i in dbds:
            units+=[j for j in i.parameterUnits.items()]
        return dict(i for i in (set(units)))

    def __getParameterList(self,dbds):
        if len(dbds)==0: # no parameters in here.
            return []
        tmp=[]
        for dbd in dbds:
            for pn in dbd.parameterNames:
                if pn not in tmp:
                    tmp.append(pn)
        tmp.sort()
        return tmp

                         
    def __worker(self,method,ft,*p):
        # if i in __ignore_cache, the file is flagged as outside the time limits
        #tmp=[eval("i.%s(*p)"%(method)) for i in self.dbds[ft] 
        #     if i not in self.__ignore_cache]
        tmp=[]
        error_mesgs = []
        for i in self.dbds[ft]:
            if i in self.__ignore_cache:
                continue
            try:
                r=eval("i.%s(*p)"%(method)) 
            except DbdError as e:
                # ignore only the no_data_to_interpolate_to error
                # as the file is probably (close to) empty
                if e.value==DBD_ERROR_NO_DATA_TO_INTERPOLATE_TO:
                    continue
                elif e.value==DBD_ERROR_NO_VALID_PARAMETERS:
                    if e.mesg not in error_mesgs:
                        error_mesgs.append(e.mesg)
                    continue
                else:
                    # in all other cases reraise the error..
                    raise e
            else:
                tmp.append(r)

        if tmp==[]:
            # nothing has been added, so all files should have returned nothing:
            raise(DbdError(DBD_ERROR_NO_VALID_PARAMETERS,
                           "\n".join(error_mesgs)))
        return numpy.concatenate(tmp,axis=1)

