import locale
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
import logging

logger = logging.getLogger(os.path.basename(__file__))
logging.basicConfig(level=logging.INFO)

# make sure we interpret timestamps in the english language
try:
    locale.setlocale(locale.LC_ALL, 'en_US')
except:
    pass # building on read-the-docs fails because of this.

def strptimeToEpoch(datestr, fmt):
    ''' Converts datestr into seconds

    Function to convert a date string into seconds since Epoch. 
    This function is not affected by the time zone used by the OS and
    interprets the date string in UTC.


    Parameters
    ----------
    datestr: str
        A string presenting the date, such as "2010 May 01"

    fmt: str
        Format to interpret strings. Example: "%Y %b %d"
    
    Returns
    -------
    int
        time since epoch in seconds
    '''
    ts = time.strptime(datestr , fmt)
    return timegm(ts)


def epochToDateTimeStr(seconds,dateformat="%Y%m%d",timeformat="%H:%M"):
    ''' Converts seconds since Epoch to date string
    
    This function converts seconds since Epoch to a datestr and timestr
    with user configurable formats.

    Parameters
    ----------
    seconds: float or int
        seconds since Epoch
    dateformat: str
        string defining how the date string should be formatted
    timeformat: str
        string defining how the time string should be formatted

    Returns
    -------
    (str, str)
         datestring and timestring
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

    Parameters
    ----------
    x: float
        latitiude or longitude in NMEA format
    y: float, optional 
       latitiude or longitude in NMEA format

    Returns
    -------
    float or tuple of floats
         decimal latitude (longitude) or tuple of decimal latitude and longitude
    '''
    if not y==None:
        X=__convertToDecimal(x)
        Y=__convertToDecimal(y)
        return X,Y
    return __convertToDecimal(x)


# required (and only tested) encoding version.
ENCODING_VER=5


#HOME = os.environ['HOME'] # this works on Linux only it seems
HOME = os.path.expanduser("~") # <- multiplatform proof

CACHEDIR=os.path.join(HOME,'.dbdreader')

if not os.path.exists(CACHEDIR):
    os.makedirs(CACHEDIR)


DBD_ERROR_CACHE_NOT_FOUND=1
DBD_ERROR_NO_VALID_PARAMETERS=2
DBD_ERROR_NO_TIME_VARIABLE=3
DBD_ERROR_NO_FILE_CRITERIUM_SPECIFIED=4
DBD_ERROR_NO_FILES_FOUND=5
DBD_ERROR_NO_DATA_TO_INTERPOLATE_TO=6
DBD_ERROR_CACHEDIR_NOT_FOUND=7
DBD_ERROR_ALL_FILES_BANNED=8

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
        elif self.value==DBD_ERROR_CACHEDIR_NOT_FOUND:
            mesg='Cache file directory does not exist.'
        elif self.value==DBD_ERROR_ALL_FILES_BANNED:
            mesg='All data files were banned.'
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
    ''' List that properly sorts dbd files.
    
    Object subclassed from list. The sort method defaults to sorting dbd 
    files and friends in the right order.

    Parameters
    ----------
    *p : variable length list of str
        filenames
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
        ''' sorts filenames ensuring dbd files are in chronological order in place
        
        Parameters
        ----------
        cmp :
            ingored keyword (for compatibility reasons only)
        key :
            ignored keyword (for compatibility reasons only)
        reverse : bool
            If True, performs a reverse sort.
        '''
        list.sort(self, key=self.__keyFilename, reverse=reverse)

class DBDPatternSelect(object):
    ''' Selecting DBD files.

    A class for selecting dbd files based on a date condition.
    The class opens files and reads the headers only.

    Parameters
    ----------
    date_format : str, optional
         date format used to interpret date strings.
    
    Note
    ----
        Times are based on the opening time of the file only.

    '''
    cache = {}
    
    def __init__(self, date_format="%d %m %Y"):
        self.set_date_format(date_format)

        
    def set_date_format(self,date_format):
        ''' Set date format

        Sets the date format used to interpret the from_date and until_dates.

        Parameters
        ----------
        date_format: str
            format to interpret date strings. Example "%H %d %m %Y"
        
        '''
        self.date_format=date_format

    def get_date_format(self):
        ''' Returns date format string.
        
        Returns
        -------
        str:
            date format string
        '''
        return self.date_format


    def select(self,pattern=None,filenames=[],from_date=None,until_date=None):
        '''Select file names from pattern or list.

        This method selects the filenames given a filename list or search 
        pattern and given time limits.

        Parameters
        ----------
        pattern: str
            search pattern (passed to glob) to find filenames
        
        filenames: list of str
            filename list
        
        from_date: None or str, optional
            date used as start date criterion. If None, all files are
            included until the until_date.

        until_date: None or str, optional
            date used aas end date criterion. If None, all files after 
            from_date are included.
        
        Returns:
             list of filenames that match the criteria

        Raises:
             ValueError if nor pattern or filenames is given.

        Note
        ----
        Either pattern or filenames should be supplied, and at least one of 
        from_date and until_date.

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

    def bins(self, pattern=None, filenames=None, binsize=86400, t_start=None, t_end=None):
        '''Return a list of filenames, in time bins

        The method makes a list of all filenames, matching either
        pattern or filenames and bins these in time windows of width. If
        t_start and t_end are not given, they are computed from the first and
        last timestamps of the files specified, respectively.


        This method returns a list of tuples, where each tuple
        contains the centred time of the bin, and a list of all
        filenames that fall within this bin.

        Parameters
        ----------
        pattern: str
            search pattern (as used in glob)
        
        filenames: list of str
            filename list
        
        binsize: float
            binsize of in seconds

        t_start: None or float
            Timestamp in seconds since 1/1/1970

        t_end: None or float
            Timestamp in seconds since 1/1/1970

        Returns
        -------
        list of list of str
            list of filenames, grouped per bin

        Raises
        ------
        ValueError if nor pattern or filenames is given.
        '''
        fns = self.get_filenames(pattern, filenames)
        if t_start is None:
            t_start = numpy.min(list(self.cache.keys()))
        if t_end is None:
            t_end = numpy.max(list(self.cache.keys()))
        bin_edges = numpy.arange(t_start, t_end+binsize, binsize)
        bins = [((left+right)/2, self.__select(fns, left, right))
                for left, right in zip(bin_edges[0:-1], bin_edges[1:])]
        return bins

        
    def get_filenames(self, pattern, filenames, cacheDir=None):
        ''' Get filenames (sorted) and update CAC cache directory.
        
        Parameters
        ----------
        pattern : str
            search pattern (as used in glob)
        filenames : list of str
            list of filenames
        
        Returns
        -------
        list of str
            sorted list of filenames.
        '''
        if not pattern and not filenames:
            raise ValueError("Expected some pattern to search files for or file list.")
        if pattern:
            all_filenames=DBDList(glob.glob(pattern))
        elif filenames:
            all_filenames=DBDList(filenames)
        else:
            raise ValueError('Supply either pattern or filenames argument.')
        all_filenames.sort()
        self.__update_cache(all_filenames, cacheDir)
        return all_filenames
    
    def __update_cache(self, fns, cacheDir):
        cached_filenames = DBDList(self.cache.values())
        cached_filenames.sort()
        for fn in fns:
            if fn not in cached_filenames:
                dbd=DBD(fn, cacheDir)
                t_open=dbd.get_fileopen_time()
                dbd.close()
                self.cache[t_open]=fn
                
    def __select(self,all_fns,t0,t1):
        open_times = numpy.array(list(self.cache.keys()))
        open_times = numpy.sort(open_times)
        selected_times = open_times.compress(numpy.logical_and(open_times>=t0,
                                                               open_times<=t1))
        fns = set([self.cache[t] for t in selected_times]).intersection(all_fns)
        fns = DBDList(fns)
        fns.sort()
        return fns

            
                                                          
            
        
        
class DBDHeader(object):

    ''' Class to read the headers of DBD files. This file is typically used
        by DBD and MultiDBD and not directly.
    '''
    def __init__(self):
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

    Parameters
    ----------
    
    filename: str
        dbd filename

    cachedDir: str or None, optional
        path to CAC file cache directory. If None, the default path is used.
    '''
    def __init__(self,filename,cacheDir=None):

        self.filename=filename
        self.fp=open(filename,'br')
        if cacheDir==None:
            self.cacheDir=CACHEDIR
        else:
            self.cacheDir=cacheDir
        self.headerInfo,parameterInfo,self.cacheFound, self.cacheID = self.__read_header(self.cacheDir)
        # number of bytes each states section consists of:
        self.n_state_bytes=self.headerInfo['state_bytes_per_cycle']
        # size of variables used
        self.byteSizes=tuple([i[0] for i in parameterInfo])
        # note: python <2.6 can't index tuples.
        self.parameterNames=[i[1] for i in parameterInfo]
        self.parameterUnits=dict((i[1],i[2]) for i in parameterInfo)
        self.timeVariable=self.__set_timeVariable()

    # def getpy(self, parameter):
    #     ti = self.parameterNames.index(self.timeVariable)
    #     vi = self.parameterNames.index(parameter)
    #     self.ti = ti
    #     self.vi =vi
    #     return self.__get_by_read_per_byte(parameter)
    
    def get_mission_name(self):
        ''' Returns the mission name such as micro.mi '''
        return self.headerInfo['mission_name'].lower()

    def get_fileopen_time(self):
        ''' Returns the time stamp of opening the file in UTC '''
        return self.__get_fileopen_time()

    def close(self):
        ''' Closes a DBD file '''
        return self.fp.close()

    def get(self,*parameters,decimalLatLon=True,discardBadLatLon=True, return_nans=False):
        '''Returns time and parameter data for requested parameter 
        
        This method reads the requested parameter, and convert it
        optionally to decimal format if the parameter is latitude-like
        or longitude-like

        Parameters
        ----------
        *parameters: variable length list of str
            parameter name

        decimalLatLon : bool, optional
            If True (default), latitiude and longitude related parameters are converted to 
            decimal format, as opposed to nmea format.

        discardBadLatLon : bool, optional
            If True (default), bogus latitiude and longitude values are ignored.
        
        return_nans : bool, optional
            if True, nans are returned for timestamps the variable was not updated or changed.

        Returns
        -------
        tuple of (ndarray, ndarray) for each parameter requested.
            time vector (in seconds) and value vector

        Raises
        ------
             DbdError when the requested parameter(s) cannot be read.

        .. versionchanged:: 0.4.0 Multi parameters can be passed, giving a time,value tuple for each parameter.

        '''
        timestamps, values =  self._get(*parameters, decimalLatLon=decimalLatLon,
                                        discardBadLatLon=discardBadLatLon, return_nans=return_nans)
        r = [(t,v) for t, v in zip(timestamps, values)]
        
        if len(parameters)==1:
            return r[0]
        else:
            return r

    def get_list(self,*parameters,decimalLatLon=True,discardBadLatLon=True,
                 return_nans=False):
        ''' Returns time and value tuples for a list of requested parameters
        

        This method returns time and values tuples for a list of parameters. It
        is basically a short-hand for a looped get() method.
        
        Note that each parameter comes with its own time base. No interpolation
        is done. Use get_sync() for that in stead.

        Parameters
        ----------
        *parameters: list of str
            list of parameter names

        decimalLatLon : bool, optional
            If True (default), latitiude and longitude related parameters are converted to 
            decimal format, as opposed to nmea format.

        discardBadLatLon : bool, optional
            If True (default), bogus latitiude and longitude values are ignored.
        
        return_nans : bool
            If True, nan's are returned for those timestamps where no new value is available.
            Default value: False

        Returns
        -------
        list of (ndarray, ndarray) 
            list of tuples of time and value vectors for each parameter requested.

        .. deprecated:: 0.4.0
            
        .. note::
            This function will be removed in a future version. Use .get() instead.
        '''
        logger.info("get_list has been deprecated in version 0.4.0 and may be removed in the future. Use get instead.")
        return self.get(*parameters,decimalLatLon=decimalLatLon ,discardBadLatLon=discardBadLatLon , return_nans=return_nans)
        
    def get_xy(self,parameter_x,parameter_y,decimalLatLon=True, discardBadLatLon=True):
        ''' Returns values of parameter_x and paramter_y

        For parameters parameter_x and parameter_y this method returns a tuple 
        with the values of both parameters. If necessary, the time base of 
        parameter_y is interpolated onto the one of parameter_x.

        Parameters
        ----------
        parameter_x: str
            parameter name of x-parameter

        parameter_y: str
            parameter name of y-parameter

        decimalLatLon : bool, optional
            If True (default), latitiude and longitude related parameters are converted to 
            decimal format, as opposed to nmea format.

        discardBadLatLon : bool, optional
            If True (default), bogus latitiude and longitude values are ignored.
        
        Returns
        -------
        (ndarray, ndarray)
            tuple of value vectors
        '''
        _, x, y = self._get_sync(parameter_x, parameter_y,
                                 decimalLatLon=decimalLatLon, discardBadLatLon=discardBadLatLon)
        return x, y


    def get_sync(self, *sync_parameters, decimalLatLon=True, discardBadLatLon=True):
        '''Returns a list of values from parameters, all interpolated to the 
            time base of the first paremeter

        This method is used if a number of parameters should be interpolated 
        onto the same time base.

        Parameters
        ----------
        *sync_parameters: variable length list of str
            parameter names. Minimal length is 2. The time base of the first parameter is
            used to interpolate all other parameters onto.

        decimalLatLon : bool, optional
            If True (default), latitiude and longitude related parameters are converted to 
            decimal format, as opposed to nmea format.

        discardBadLatLon : bool, optional
            If True (default), bogus latitiude and longitude values are ignored.
        
        Returns
        -------
        (ndarray, ndarray, ...)
            Time vector (of first parameter), values of first parmaeter, and 
            interpolated values of subsequent parameters.

        Example:
            
            get_sync('m_water_pressure','m_water_cond','m_water_temp')

        Notes
        -----
        .. versionchanged:: 0.4.0
            Calling signature has changed from the sync parameters 
            passed on as a list, to passed on as parameters.
        '''

        if len(sync_parameters)<2:
            raise ValueError('Expect at least two parameters.')
        if len(sync_parameters)==2 and (isinstance(sync_parameters[1], list) or isinstance(sync_parameters[1], tuple)):
            # obsolete calling signature.
            logger.info("Calling signature of get_sync() has changed in version 0.4.0.")
            sync_parameters = [sync_parameters[0]] + sync_parameters[1]
        return self._get_sync(*sync_parameters, decimalLatLon=decimalLatLon, discardBadLatLon=discardBadLatLon)

    def has_parameter(self,parameter):
        ''' Check wheter this file contains parameter
        
        Parameters
        ----------
        parameter: str
            parameter to check
        
        Returns
        -------
        bool
            True if parameter is in the list, or False if not 
        '''
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


    def _get(self,*parameters,decimalLatLon=True,discardBadLatLon=False, return_nans=False):
        ''' returns time and parameter data for requested parameter '''
        if not self.cacheFound:
            cache_file=self.headerInfo['sensor_list_crc']
            raise DbdError(DBD_ERROR_CACHE_NOT_FOUND,\
                               ' Cache file %s for %s was not found in the cache directory (%s).'%(cache_file,self.filename,self.cacheDir))
        number_of_parameters=len(parameters)
        valid_parameters = self.__get_valid_parameters(parameters)
        if len(valid_parameters)!=len(parameters):
            invalid_parameters = [p for p in parameters if p not in valid_parameters]
            raise DbdError(DBD_ERROR_NO_VALID_PARAMETERS,
                           "\nMissing parameter(s): %s"%(", ".join(invalid_parameters)))
        if not self.timeVariable in self.parameterNames:
            raise DbdError(DBD_ERROR_NO_TIME_VARIABLE)
        # OK, we have some parameters to return:
        ti=self.parameterNames.index(self.timeVariable)
        idx = [self.parameterNames.index(p) for p in parameters]
        idx_sorted=numpy.sort(idx)
        vi = tuple(idx_sorted)
        self.n_sensors=self.headerInfo['sensors_per_cycle']
        r=_dbdreader.get(self.n_state_bytes,
                         self.n_sensors,
                         self.fp_binary_start,
                         self.byteSizes,
                         self.filename,
                         ti,
                         vi,
                         int(return_nans))
        # map the contents of vi on timestamps and values, preserving the original order:
        idx_reorderd = [vi.index(i) for i in idx]
        timestamps = [numpy.array(r[i]) for i in idx_reorderd]
        values = [numpy.array(r[number_of_parameters+i]) for i in idx_reorderd]
        # convert to decimal lat lon if applicable:
        for i, p in enumerate(parameters):
            if return_nans:
                idx = numpy.where(numpy.isclose(values[i],1e9))[0]
                values[i][idx] = numpy.nan
            if self.__is_latlon_parameter(p):
                if decimalLatLon:
                    values[i] = toDec(values[i])
                if discardBadLatLon and not return_nans: #discards and return nans is not compatible.
                    condition = values[i]<696960
                    timestamps[i], values[i] = numpy.compress(condition, (timestamps[i], values[i]), axis=1)
        return timestamps, values


    def _get_sync(self,*params, decimalLatLon=True,discardBadLatLon=True):
        '''
            x: dbdparameter name

            y: list of dbd parameter names

            returns a list of
            t, parameter x, parameter y0, parameter y1, ...
            where the y parameters are synchronized to x.

            if decimalLatLon, then all lat/lon type variables are converted
            to decimal values prior to interpolation.

            example:
            
            get_sync('m_water_pressure','m_water_cond','m_water_temp')
        '''
        timestamps, values = self._get(*params,decimalLatLon=decimalLatLon,discardBadLatLon=discardBadLatLon)
        t = timestamps[0]
        if t.shape[0] == 0:
            raise DbdError(DBD_ERROR_NO_DATA_TO_INTERPOLATE_TO)

        r = []
        for i, (_t, _v) in enumerate(zip(timestamps, values)):
            if i==0:
                r.append(_t)
                r.append(_v)
            else:
                r.append(numpy.interp(t, _t, _v, left=numpy.nan, right=numpy.nan))
        return r
    
    def __get_valid_parameters(self,parameters):
        validParameters=[i for i in parameters if i in self.parameterNames]
        return validParameters

    def __is_latlon_parameter(self,x):
        if 'lat' in x or 'lon' in x:
            return True
        else:
            return False

    def __read_header(self, cacheDir):
        if not os.path.exists(cacheDir):
            raise DbdError(DBD_ERROR_CACHEDIR_NOT_FOUND, " (%s)"%(cacheDir))
        dbdheader=DBDHeader()
        factored=dbdheader.read_header(self.fp)
        # determine cache file name
        cacheID = dbdheader.info['sensor_list_crc'].lower()
        cacheFilename=os.path.join(cacheDir,cacheID+".cac")
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
        return (dbdheader.info,parameter,cacheFound, cacheID)

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
        fields_per_byte=bits_per_byte//bits_per_field
        offset=0
        n=0
        vi=0
        offsets=[0 for i in range(len(reqd_variables))]
        state_bytes=self.fp.read(self.n_state_bytes)
        for sb in state_bytes:
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
        if len(bs)==4:
            return struct.unpack("f",bs[::-1])[0]
        else:
            return struct.unpack("d",bs[::-1])[0]


class MultiDBD(object):
    '''Opens multiple dbd files for reading

    
    This class is intended for reading multiple dbd files and treating
    them as one.
    
    Parameters
    ----------
    filenames : list of str or None
        list of filenames to open
    pattern : str or None
        search pattern as passed to glob
    
    cacheDir: str or None
        path to directory with CAC cache files (None: the default directory is used)

    complemented_files_only : bool
        if True, only those files are retained for which both engineering and science
        data files are available.

    complement_files : bool
        If True automatically include matching [de]bd files

    banned_missions: list of str
        List of mission names that should be disregarded.

    missions: list of str
        List of missions names that should be considered only.

    maxfiles: int
       maximum number of files to be read, where
        >0: the first n files are read
        <0: the last n files are read.

    ensure_paired : bool
        (DEPRECATED) if True, only those files are retained for which both engineering and science
        data files are available.

    include_paired : bool
        (DEPRECATED) If True automatically include matching [de]bd files


    Notes
    -----
    .. versionchanged:: 0.4.0
        ensure_paired and included_paired keywords have been replaced by complemented_files_only 
        and complement_files, respectively.
    '''
    def __init__(self,filenames=None,pattern=None,cacheDir=None,complemented_files_only=False,
                 complement_files=False,banned_missions=[],missions=[],
                 max_files=None, **kwds):
        if kwds.get('ensure_paired', None):
            complemented_files_only = kwds['ensure_paired']
            logger.info("ensure_paired keyword is obsolete as of version 0.4.0")
        if kwds.get('include_paired', None):
            complement_files = kwds['include_paired']
            logger.info("include_paired keyword is obsolete as of version 0.4.0")
            
        self.__ignore_cache=[]
        if cacheDir is None:
            cacheDir=CACHEDIR
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

        if complement_files:
            self.__add_paired_filenames()

        if complemented_files_only:
            self.pruned_files=self.__prune_unmatched(cacheDir)

        self.__update_dbd_inventory(cacheDir)
        self.parameterNames=dict((k,self.__getParameterList(v)) \
                                     for k,v in self.dbds.items())
        self.parameterUnits=self.__getParameterUnits()
        #
        self.time_limits_dataset=(None,None)
        self.time_limits=[None,None]
        self.set_time_limits()
    
##### public methods
    def get(self, *parameters, decimalLatLon=True, discardBadLatLon=True, return_nans=False):
        ''' Returns time and value tuple(s) for requested parameter(s)
        
        This method returns time and values tuples for a list of parameters.
        
        Note that each parameter comes with its own time base. No interpolation
        is done. Use get_sync() for that in stead.

        Parameters
        ----------
        parameter_list: list of str
            list of parameter names

        decimalLatLon : bool, optional
            If True (default), latitiude and longitude related parameters are converted to 
            decimal format, as opposed to nmea format.

        discardBadLatLon : bool, optional
            If True (default), bogus latitiude and longitude values are ignored.
        
        return_nans : bool
            If True, nan's are returned for those timestamps where no new value is available.
            Default value: False

        Returns
        -------
        (ndarray, ndarray) or list of (ndarray, ndarray)
            list of tuples of time and value vectors for each parameter requested.
        '''
        eng_variables = []
        sci_variables = []
        positions = []
        for p in parameters:
            if p in self.parameterNames['sci']:
                positions.append(("sci", len(sci_variables)))
                sci_variables.append(p)
            else:
                positions.append(("eng", len(eng_variables)))
                eng_variables.append(p)
        kwds=dict(decimalLatLon=decimalLatLon, discardBadLatLon=discardBadLatLon, return_nans=return_nans)

        if len(sci_variables)>=1: 
            r_sci = self.__worker("get", "sci", *sci_variables, **kwds)
        if len(eng_variables)>=1:
            r_eng = self.__worker("get", "eng", *eng_variables, **kwds)
        r = []
        for target, idx in positions:
            if target=='sci':
                r.append(r_sci[idx])
            else:
                r.append(r_eng[idx])
        if len(parameters)==1:
            return r[0]
        else:
            return r

    def get_xy(self,parameter_x,parameter_y,decimalLatLon=True, discardBadLatLon=True):
        ''' Returns values of parameter_x and paramter_y

        For parameters parameter_x and parameter_y this method returns a tuple 
        with the values of both parameters. If necessary, the time base of 
        parameter_y is interpolated onto the one of parameter_x.

        Parameters
        ----------
        parameter_x: str
            parameter name of x-parameter

        parameter_y: str
            parameter name of y-parameter

        decimalLatLon : bool, optional
            If True (default), latitiude and longitude related parameters are converted to 
            decimal format, as opposed to nmea format.

        discardBadLatLon : bool, optional
            If True (default), bogus latitiude and longitude values are ignored.
        
        Returns
        -------
        (ndarray, ndarray)
            tuple of value vectors
        '''    
        _, x, y = self.get_sync(parameter_x, parameter_y, decimalLatLon=decimalLatLon, discardBadLatLon=discardBadLatLon)
        return x, y
    
    def get_sync(self,*parameters,decimalLatLon=True, discardBadLatLon=True):
        ''' Returns a list of values from parameters, all interpolated to the 
            time base of the first paremeter

        This method is used if a number of parameters should be interpolated 
        onto the same time base.

        Parameters
        ----------
        *parameters: variable length list of str
            parameter names. Minimal length is 2. The time base of the first parameter is
            used to interpolate all other parameters onto.

        decimalLatLon : bool, optional
            If True (default), latitiude and longitude related parameters are converted to 
            decimal format, as opposed to nmea format.

        discardBadLatLon : bool, optional
            If True (default), bogus latitiude and longitude values are ignored.
        
        Returns
        -------
        (ndarray, ndarray, ...)
            Time vector (of first parameter), values of first parmaeter, and 
            interpolated values of subsequent parameters.

        Example:
            
            get_sync('m_water_pressure','m_water_cond','m_water_temp')

        Notes
        -----
        .. versionchanged:: 0.4.0
            Calling signature has changed from the sync parameters 
            passed on as a list, to passed on as parameters.
        '''
        if len(parameters)<2:
            raise ValueError('Expect at least two parameters.')
        if len(parameters)==2 and (isinstance(parameters[1], list) or isinstance(parameters[1], tuple)):
            # obsolete calling signature.
            logger.info("Calling signature of get_sync() has changed in version 0.4.0.")
            parameters = [parameters[0]] + parameters[1]

        tv = self.get(*parameters, decimalLatLon=decimalLatLon, discardBadLatLon=discardBadLatLon, return_nans=False)
        t = tv[0][0]
        r = []
        for i, (_t, _v) in enumerate(tv):
            if i==0:
                r.append(_t)
                r.append(_v)
            else:
                r.append(numpy.interp(t, _t, _v, left=numpy.nan, right=numpy.nan))
        return r
    
    def get_list(self,*parameters,decimalLatLon=True, discardBadLatLon=True, return_nans=False):
        ''' Returns time and value tuples for a list of requested parameters
        

        This method returns time and values tuples for a list of parameters. It
        is basically a short-hand for a looped get() method.
        
        Note that each parameter comes with its own time base. No interpolation
        is done. Use get_sync() for that in stead.

        Parameters
        ----------
        parameter_list: list of str
            list of parameter names

        decimalLatLon : bool, optional
            If True (default), latitiude and longitude related parameters are converted to 
            decimal format, as opposed to nmea format.

        discardBadLatLon : bool, optional
            If True (default), bogus latitiude and longitude values are ignored.
        
        return_nans : bool
            If True, nan's are returned for those timestamps where no new value is available.
            Default value: False

        Returns
        -------
        list of (ndarray, ndarray) 
            list of tuples of time and value vectors for each parameter requested.

        .. deprecated:: 0.4.0

        .. note::
            get_list() is deprecated, and will be removed in a future version. Use .get() instead.
        '''
        logger.info("get_list has been deprecated in version 0.4.0 and may be removed in the future. Use get instead.")
        return self.get(*parameters, decimalLatLon=decimalLatLon, discardBadLatLon=discardBadLatLon, return_nans=return_nans)


    def get_CTD_sync(self, *parameters, decimalLatLon=True, discardBadLatLon=True):
        '''Returns a list of values from CTD and optionally other parameters, 
        all interpolated to the time base of the CTD timestamp.

        Parameters
        ----------
        *parameters: variable length list of str
            names of parameters to be read additionally

        decimalLatLon : bool, optional
            If True (default), latitiude and longitude related parameters are converted to 
            decimal format, as opposed to nmea format.

        discardBadLatLon : bool, optional
            If True (default), bogus latitiude and longitude values are ignored.
        
        Returns
        -------
        (ndarray, ndarray, ...)
            Time vector (of first parameter), C, T and P values, and 
            interpolated values of subsequent parameters.


        Notes
        -----
        .. versionadded:: 0.4.0

        '''
        CTDparameters = ["sci_ctd41cp_timestamp", "sci_water_cond",
                         "sci_water_temp", "sci_water_pressure"]
        offset = len(CTDparameters) + 1 # because of m_present_time is
                                        # also returned.
        tmp = self.get_sync(*CTDparameters, *parameters, decimalLatLon=decimalLatLon, discardBadLatLon=discardBadLatLon)

        # remove all time<=1 timestamps, as there can be nans here too.
        tmp = numpy.compress(tmp[0]>1, tmp, axis=1)
        condition = tmp[2]>0
        if len(parameters):
            # check for any leading or trailing nans in v, caused by
            # interpolation:
            #
            # collapse v on one vector, and make a condition where the collapsed
            # vector is nan
            a = numpy.prod(tmp[offset:], axis=0)
            condition &= numpy.isfinite(a)
        # ensure monotonicity in time
        dt = numpy.hstack( ([1], numpy.diff(tmp[1])) )
        condition &= dt>0
        _, tctd, C, T, P, *v = numpy.compress(condition, tmp, axis=1)
        return [tctd, C, T, P] + v

    def has_parameter(self,parameter):
        '''Has this file parameter?
        Returns
        -------
        bool
            True if this instance has found parameter 
        '''
        return (parameter in self.parameterNames['sci'] or parameter in self.parameterNames['eng'])

    @classmethod
    def isScienceDataFile(cls,fn):
        ''' Is file a science file?
        
        Parameters
        ----------
        fn : str
            filename
        
        Returns
        -------
        bool
            True if file fn is a science file
        '''
        return fn.endswith("ebd") | fn.endswith("tbd") | fn.endswith("nbd")

    def get_time_range(self,fmt="%d %b %Y %H:%M"):
        '''Get start and end date of the time range selection set

        Parameters
        ----------
        fmt: str
            String that determines how the time string is formatted

        Returns
        -------
        (str, str)
            Tuple with formatted time strings
        '''
        return self.__get_time_range(self.time_limits,fmt)

    def get_global_time_range(self,fmt="%d %b %Y %H:%M"):
        ''' Returns start and end dates of data set (all files) 

        Parameters
        ----------
        fmt: str
            String that determines how the time string is formatted.

        Returns
        -------
        (str, str)
            tuple with formatted time strings
        '''
        return self.__get_time_range(self.time_limits_dataset,fmt)

    def set_time_limits(self,minTimeUTC=None,maxTimeUTC=None):
        '''Set time limits for data to be returned by get() and friends.

        Parameters
        ----------
        minTimeUTC: str
            start time in UTC

        maxTimeUTC: str
            end time in UTC

        Notes
        -----
        {minTimeUTC, maxTimeUTC} are expected in one of these formats:

        "%d %b %Y"  3 Mar 2014

        or

        "%d %b %Y %H:%M" 4 Apr 2014 12:21
        '''
        if minTimeUTC:
            self.time_limits[0]=self.__convert_seconds(minTimeUTC)
        if maxTimeUTC:
            self.time_limits[1]=self.__convert_seconds(maxTimeUTC)
        self.__refresh_cache()

    def close(self):
        ''' Close all open files '''
        for i in self.dbds['eng']+self.dbds['sci']:
            i.close()


    #### private methods

    def __get_matching_fn(self, fn):
        sci_extensions = ".ebd .tbd .nmd".split()
        _, extension = os.path.splitext(fn)
        matchingExtension = list(extension) # make the string mutable.
        if extension not in sci_extensions:
            matchingExtension[1] = chr(ord(extension[1])+1)
        else:
            matchingExtension[1] = chr(ord(extension[1])-1)
        matchingExtension = "".join(matchingExtension)    
        matchingFn = fn.replace(extension,matchingExtension)
        return matchingFn

    def __add_paired_filenames(self):
        to_add=[]
        for fn in self.filenames:
            mfn = self.__get_matching_fn(fn)
            if os.path.exists(mfn):
                to_add.append(mfn)
        self.filenames+=to_add
            
    def __get_matching_dbd(self,fn):
        '''returns matching dbd object corresponding to fn. If fn is not in the current list
           of accepted dbds, then None is returned.'''

        if fn not in self.filenames:
            return None
        # ok, the file is in the cache, which implies it is in self.dbds too.
        matchingFn=self.__get_matching_fn(fn)
        if matchingFn in self.filenames:
            return matchingFn
        else:
            return None

    def __prune(self,filelist, cacheDir=None):
        ''' prune all files in filelist.'''
        for tbr in filelist:
            self.filenames.remove(tbr)
    
    def __prune_unmatched(self, cacheDir=None):
        ''' prune all files which don't have a science/engineering partner 
            returns list of removed files.'''
        to_be_removed=[fn for fn in self.filenames if not self.__get_matching_dbd(fn)]
        self.__prune(to_be_removed, cacheDir)
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

    def __update_dbd_inventory(self, cacheDir):
        self.dbds={'eng':[],'sci':[]}
        filenames=list(self.filenames)
        for fn in self.filenames:
            dbd=DBD(fn, cacheDir)
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
            raise DbdError(DBD_ERROR_ALL_FILES_BANNED, " (Read %d files.)"%(len(self.filenames)))
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
        cacheIDs = []
        for i, dbd in enumerate(dbds):
            if i==0:
                parameter_names = dbd.parameterNames.copy()
                cacheIDs.append(dbd.cacheID)
            elif not dbd.cacheID in cacheIDs:
                for pn in dbd.parameterNames:
                    if pn not in parameter_names:
                        parameter_names.append(pn)
                    cacheIDs.append(dbd.cacheID)
        parameter_names.sort()
        return parameter_names

                         
    def __worker(self,method,ft,*p,**kwds):
        # if i in __ignore_cache, the file is flagged as outside the time limits
        #tmp=[eval("i.%s(*p)"%(method)) for i in self.dbds[ft] 
        #     if i not in self.__ignore_cache]
        data = dict([(k,[]) for k in p])
        error_mesgs = []
        for i in self.dbds[ft]:
            if i in self.__ignore_cache:
                continue
            m = dict(get=i._get, get_sync=i.get_sync, get_xy=i.get_xy)
            if method in "get_sync get_xy".split(): # these methods don't support the return nans option.
                kwds.pop("return_nans")
            try:
                t, v = m[method](*p, **kwds)
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
                for _p, _t, _v in zip(p, t, v):
                    data[_p].append((_t, _v))
        if not all(data.values()):
            # nothing has been added, so all files should have returned nothing:
            raise(DbdError(DBD_ERROR_NO_VALID_PARAMETERS,
                           "\n".join(error_mesgs)))
        return [numpy.hstack(data[_p]) for _p in p]

