from functools import partial
from itertools import chain
import os
import struct
import time
import numpy
from scipy.interpolate import interp1d as si_interp1d
import glob
import sys
import re
import datetime
from calendar import timegm
from collections import defaultdict, namedtuple
import _dbdreader
import dbdreader.decompress
import logging

# make sure we interpret timestamps in the english language but don't
# bother if it cannot be import as happens on building doc on readthe
# docs
try:
    import locale
    locale.setlocale(locale.LC_ALL, 'en_US.UTF-8')
except:
    pass

logger = logging.getLogger(os.path.basename(__file__))

# Parameters that a compatible with transforming from nmea to decimal format:
LATLON_PARAMS = ["m_lat",
                 "m_lon",
                 "c_wpt_lat",
                 "c_wpt_lon",
                 "x_last_wpt_lat",
                 "x_last_wpt_lon",
                 "m_gps_lat",
                 "m_gps_lon",
                 "u_lat_goto_l99",
                 "u_lon_goto_l99",
                 "m_last_gps_lat_1",
                 "m_last_gps_lon_1",
                 "m_last_gps_lat_2",
                 "m_last_gps_lon_2",
                 "m_last_gps_lat_3",
                 "m_last_gps_lon_3",
                 "m_last_gps_lat_4",
                 "m_last_gps_lon_4",
                 "m_gps_ignored_lat",
                 "m_gps_ignored_lon",
                 "m_gps_invalid_lat",
                 "m_gps_invalid_lon",
                 "m_gps_toofar_lat",
                 "m_gps_toofar_lon",
                 "xs_lat",
                 "xs_lon",
                 "s_ini_lat",
                 "s_ini_lon"]


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
    ts = time.strptime(datestr, fmt)
    return timegm(ts)


def epochToDateTimeStr(seconds, dateformat="%Y%m%d", timeformat="%H:%M"):
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
    d = datetime.datetime.utcfromtimestamp(seconds)
    datestr = d.strftime(dateformat)
    timestr = d.strftime(timeformat)
    return datestr, timestr


def _convertToDecimal(x):
    ''' Converts a latitiude or longitude in NMEA format to decimale degrees'''
    sign = numpy.sign(x)
    xAbs = numpy.abs(x)
    degrees = numpy.floor(xAbs/100.)
    minutes = xAbs-degrees*100
    decimalFormat = degrees+minutes/60.
    return decimalFormat*sign


def toDec(x, y=None):
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
    if not y == None:
        X = _convertToDecimal(x)
        Y = _convertToDecimal(y)
        return X, Y
    return _convertToDecimal(x)


# required (and only tested) encoding version.
ENCODING_VER = 5


DBD_ERROR_CACHE_NOT_FOUND = 1
DBD_ERROR_NO_VALID_PARAMETERS = 2
DBD_ERROR_NO_TIME_VARIABLE = 3
DBD_ERROR_NO_FILE_CRITERIUM_SPECIFIED = 4
DBD_ERROR_NO_FILES_FOUND = 5
DBD_ERROR_NO_DATA_TO_INTERPOLATE_TO = 6
DBD_ERROR_CACHEDIR_NOT_FOUND = 7
DBD_ERROR_ALL_FILES_BANNED = 8
DBD_ERROR_INVALID_DBD_FILE = 9
DBD_ERROR_INVALID_ENCODING = 10
DBD_ERROR_INVALID_FILE_CRITERION_SPECIFIED = 11
DBD_ERROR_NO_DATA_TO_INTERPOLATE = 12
DBD_ERROR_NO_DATA = 13


class DbdError(Exception):
    MissingCacheFileData = namedtuple('MissingCacheFileData',
                                      'missing_cache_files cache_dir')

    def __init__(self, value=9, mesg=None, data=None):
        self.value = value
        self.mesg = mesg
        self.data = data

    def __str__(self):
        if self.value == DBD_ERROR_NO_VALID_PARAMETERS:
            mesg = 'The requested parameter(s) was(were) not found.'
        elif self.value == DBD_ERROR_NO_TIME_VARIABLE:
            mesg = 'The time variable was not found.'
        elif self.value == DBD_ERROR_CACHE_NOT_FOUND:
            mesg = 'Cache file was not found.'
        elif self.value == DBD_ERROR_NO_FILE_CRITERIUM_SPECIFIED:
            mesg = 'No file specification supplied (list of filenames or pattern)'
        elif self.value == DBD_ERROR_NO_FILES_FOUND:
            mesg = 'No files were found.'
        elif self.value == DBD_ERROR_NO_DATA_TO_INTERPOLATE_TO:
            mesg = 'No data to interpolate to.'
        elif self.value == DBD_ERROR_CACHEDIR_NOT_FOUND:
            mesg = 'Cache file directory does not exist.'
        elif self.value == DBD_ERROR_ALL_FILES_BANNED:
            mesg = 'All data files were banned.'
        elif self.value == DBD_ERROR_INVALID_DBD_FILE:
            mesg = 'Invalid DBD file.'
        elif self.value == DBD_ERROR_INVALID_ENCODING:
            mesg = 'Invalid encoding version encountered.'
        elif self.value == DBD_ERROR_INVALID_FILE_CRITERION_SPECIFIED:
            mesg = 'Invalid or conflicting file selection criterion/criteria specified.'
        elif self.value == DBD_ERROR_NO_DATA_TO_INTERPOLATE:
            mesg = 'One or more parameters that are to be interpolated, does/do not have any data.'
        elif self.value == DBD_ERROR_NO_DATA:
            mesg = 'One or more parameters do not have any data.'
        else:
            mesg = f'Undefined error. ({self.value})'
        if self.mesg:
            mesg = " ".join((mesg, self.mesg))
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

def heading_interpolating_function_factory(t, v):
    '''Interpolating function factory for heading

    This function returns a function that is to be called with one
    argument, time, (float or array of floats) and returns the
    interpolated heading, taking into account proper cross-overs from
    0 to 2π.

    Parameters
    ----------
    t : array-like of float
        base time vector
    v : array-like of float
        base value vector

    Returns
    -------
        interpolating function of time

    '''
    x = numpy.cos(v)
    y = numpy.sin(v)
    xi = partial(numpy.interp, xp=t, fp=x, left=numpy.nan, right=numpy.nan)
    yi = partial(numpy.interp, xp=t, fp=y, left=numpy.nan, right=numpy.nan)
    return lambda _t: numpy.arctan2(yi(_t), xi(_t)) % (2*numpy.pi)


class DBDCache(object):

    '''DBDCache manager

    This class provides a convenient way to set the default path to the cache file
    directory.

    On linux   : $HOME/.local/share/dbdreader
    On windows : $HOME/.dbdreader

    The class method set_cachedir() can be used to change the path during the script.

    The purpose is to remove the need to specify a non-default path
    for every DBD or MultiDBD object construction.

    Examples
    --------

    >>> DBDCache() # sets default. This is typically called at the end of the dbdreader module file.

    >>> DBDCache.set_cachedir("/tmp") # overrides the default.

    Note
    ----

    DBDCache can be called with an argument, and it sets the default
    path to this string. The difference between DBDCache("/tmp") and
    DBDCache.set_cachedir("/tmp") is that when set_cachedir() is
    called and the target directory does not exist, an error is
    raised, whereas a call using the class constructor will create the
    directory if necessary.

    '''
    CACHEDIR = None

    def __init__(self, cachedir=None):
        if cachedir is None:
            if DBDCache.CACHEDIR is None:
                HOME = os.path.expanduser("~")  # <- multiplatform proof
                if sys.platform == 'linux':
                    cachedir = os.path.join(HOME, '.local/share/dbdreader')
                else:
                    cachedir = os.path.join(HOME, '.dbdreader')
                DBDCache.set_cachedir(cachedir, force_makedirs=True)
            # else default value is set and used.
        else:
            # user path set. Let it fail if it does not exists.
            DBDCache.set_cachedir(cachedir, force_makedirs=False)


    @classmethod
    def set_cachedir(cls, path, force_makedirs=False):
        '''Set the cache directory path

        Parameters
        ----------
        path : string
            path to cache directory

        force_makedirs : bool
            if True, forces the creation of subdirectories if needed.
            if False, an Exception will be thrown if the directory does not exist.
        '''
        if not os.path.exists(path):
            if force_makedirs:
                os.makedirs(path)
            else:
                raise DbdError(DBD_ERROR_CACHEDIR_NOT_FOUND)
        DBDCache.CACHEDIR = path
        
        
    


class DBDList(list):

    ''' List that properly sorts dbd files.

    Object subclassed from list. The sort method defaults to sorting dbd
    files and friends in the right order.

    Parameters
    ----------
    *p : variable length list of str
        filenames
    '''
    REGEX = re.compile(r"-[0-9]+-[0-9]+-[0-9]+-[0-9]+\.[demnstDEMNST][bB][dD]")
    
    def __init__(self,*p):
        list.__init__(self,*p)

    def _keyFilename(self, key):
        match = DBDList.REGEX.search(key)
        if match:
            s, extension = os.path.splitext(match.group())
            number_fields = s.split("-")
            n=sum([int(i)*10**j for i,j in zip(number_fields[1:],[8,5,3,0])]) # first field is '', so skip over
            r = f"{key[:match.span()[0]]}-{n}{extension.lower()}"
        else:
            r = key.lower()
        return r
    
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
        list.sort(self, key=self._keyFilename, reverse=reverse)

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

    def __init__(self, date_format="%d %m %Y", cacheDir=None):
        self.set_date_format(date_format)
        self.cacheDir = cacheDir
        
    def set_date_format(self,date_format):
        ''' Set date format

        Sets the date format used to interpret the from_date and until_dates.

        Parameters
        ----------
        date_format: str
            format to interpret date strings. Example "%H %d %m %Y"

        cachedDir: str or None, optional
            path to CAC file cache directory. If None, the default path is used.

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

        all_filenames = self.get_filenames(pattern, filenames, self.cacheDir)

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
            return self._select(all_filenames,t0,t1)

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
        if not fns:
            raise DbdError(DBD_ERROR_NO_FILES_FOUND,
                           f"No files matched search pattern {pattern}.")
        if t_start is None:
            t_start = numpy.min(list(self.cache.keys()))
        if t_end is None:
            t_end = numpy.max(list(self.cache.keys()))
        bin_edges = numpy.arange(t_start, t_end+binsize, binsize)
        bins = [((left+right)/2, self._select(fns, left, right))
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
        self._update_cache(all_filenames, cacheDir)
        return all_filenames

    def _update_cache(self, fns, cacheDir):
        cached_filenames = DBDList(self.cache.values())
        cached_filenames.sort()
        for fn in fns:
            if fn not in cached_filenames:
                dbd=DBD(fn, cacheDir)
                t_open=dbd.get_fileopen_time()
                self.cache[t_open]=fn

    def _select(self,all_fns,t0,t1):
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

    @property
    def factored(self):
        try:
            r = self.info['sensor_list_factored']
        except KeyError:
            r = None
        return r

    def read_header(self, fp, filename=''):
        ''' read the header of the file, given by fp '''
        fp.seek(0)
        if not self.parse(fp.readline())=='dbd_label':
            return DBD_ERROR_INVALID_DBD_FILE
        n_read=1
        while True:
            self.parse(fp.readline())
            n_read+=1
            if 'num_ascii_tags' in self.info  and \
               self.info['num_ascii_tags']==n_read:
                break
        if self.info['encoding_ver']!=ENCODING_VER:
            return DBD_ERROR_INVALID_ENCODING
        return 0

    def read_cache(self,fp, fpcopy=None):
        ''' read cache file '''
        parameter=[]
        all_parameter_names = []
        for i in range(self.info['total_num_sensors']):
            line=fp.readline().decode('ascii')
            if fpcopy!=None:
                fpcopy.write(line)
                parameters={}
            words=line.split()
            j=int(words[3]) # >=0? used : not used
            name=words[5]
            if j!=-1:
                unit=words[6]
                size=int(words[4])
                parameter.append((size,name,unit))
            all_parameter_names.append(name)
        self.info['parameter_list'] = all_parameter_names
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
    '''Class to read a single DBD type file

    Parameters
    ----------

    filename: str
        dbd filename

    cachedDir: str or None, optional
        path to CAC file cache directory. If None, the default path is used.

    skip_initial_line : bool, default: True
        controls the behaviour of the binary reader: if set to True,
        all first lines of data in the binary files are skipped
        otherwise they are read. Default value is True, as the data in
        the initial file have usually no scienitific merit (random
        value or arbitrarily old); only for debugging purposes one may
        want to have the initial data line read.

    '''
    
    SKIP_INITIAL_LINE = True
    
    def __init__(self,filename, cacheDir=None, skip_initial_line=True):
        
        self.filename=filename
        self.skip_initial_line = skip_initial_line
        logger.debug('Opening %s', filename)
        if cacheDir==None:
            self.cacheDir=DBDCache.CACHEDIR
        else:
            self.cacheDir=cacheDir
        if dbdreader.decompress.is_compressed(filename):
            with dbdreader.decompress.CompressedFile(filename) as self.fp:
                self.headerInfo,parameterInfo,self.cacheFound, self.cacheID = self._read_header(self.cacheDir)
        else:
            with open(filename,'br') as self.fp:
                self.headerInfo,parameterInfo,self.cacheFound, self.cacheID = self._read_header(self.cacheDir)
        # number of bytes each states section consists of:
        self.n_state_bytes=self.headerInfo['state_bytes_per_cycle']
        # size of variables used
        self.byteSizes=tuple([i[0] for i in parameterInfo])
        # note: python <2.6 can't index tuples.
        self.parameterNames=[i[1] for i in parameterInfo]
        self.parameterUnits=dict((i[1],i[2]) for i in parameterInfo)
        self.timeVariable=self._set_timeVariable()
        if not self.cacheFound:
            mesg = f"\nCache file {self.cacheID} for {self.filename} was not found in the cache directory ({self.cacheDir})."
            data = DbdError.MissingCacheFileData({self.cacheID:[self.filename]}, self.cacheDir)
            raise DbdError(DBD_ERROR_CACHE_NOT_FOUND, mesg=mesg, data=data)

    def get_mission_name(self):
        ''' Returns the mission name such as micro.mi '''
        return self.headerInfo['mission_name'].lower()

    def get_fileopen_time(self):
        ''' Returns the time stamp of opening the file in UTC '''
        return self._get_fileopen_time()

    def close(self):
        ''' Closes a DBD file '''
        return self.fp.close()

    def get(self,*parameters,decimalLatLon=True,discardBadLatLon=True, return_nans=False, max_values_to_read=-1,
            check_for_invalid_parameters=True):
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

        max_values_to_read : int, optional
            if > 0, reading is stopped after this many values have been read.

        check_for_invalid_parameters : bool, optional
            if True returns empty arrays for parameters that are marked as invalid, instead of triggering an exception.

        Returns
        -------
        tuple of (ndarray, ndarray) for each parameter requested.
            time vector (in seconds) and value vector

        Raises
        ------
             DbdError when the requested parameter(s) cannot be read.

        .. versionchanged:: 0.4.0 Multi parameters can be passed, giving a time,value tuple for each parameter.
        .. versionchanged:: 0.5.5 For a single parameter request, the number of values to be read can be limited.

        '''
        # It only makes sense to limit the number of parameters read when a single parameter is requested. Check for this.
        if max_values_to_read>0 and len(parameters)!=1:
            raise ValueError("Limiting the values to be read for multiple parameters potentially yields undefined behaviour.\n")
        
        timestamps, values =  self._get(*parameters, decimalLatLon=decimalLatLon,
                                        discardBadLatLon=discardBadLatLon, return_nans=return_nans,
                                        max_values_to_read=max_values_to_read,
                                        check_for_invalid_parameters=check_for_invalid_parameters)
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

    def _get_fileopen_time(self):
        datestr=self.headerInfo['fileopen_time'].replace("_"," ")
        fmt="%a %b %d %H:%M:%S %Y"
        seconds=strptimeToEpoch(datestr, fmt)
        return seconds

    def _set_timeVariable(self):
        if 'm_present_time' in self.parameterNames:
            return 'm_present_time'
        else:
            return 'sci_m_present_time'


    def _get(self,*parameters,decimalLatLon=True,discardBadLatLon=False, return_nans=False,
             max_values_to_read=-1, check_for_invalid_parameters=True):
        ''' returns time and parameter data for requested parameter '''
        invalid_parameters = self._get_valid_parameters(parameters, invert=True, global_scope=True)
        if invalid_parameters and check_for_invalid_parameters:
            # Do not trigger an exception if we allow parameters without data to return empty arrays.
            if len(invalid_parameters)==1:
                mesg = f"Parameter {invalid_parameters[0]} is an unknown glider sensor name. ({self.filename})"
            else:
                mesg = f"Parameters {{{','.join(invalid_parameters)}}} are unknown glider sensor names. ({self.filename})"
            raise DbdError(value=DBD_ERROR_NO_VALID_PARAMETERS, mesg=mesg, data=invalid_parameters)

        valid_parameters = self._get_valid_parameters(parameters)
        missing_parameters = self._get_valid_parameters(parameters, invert=True)
        number_valid_parameters = len(valid_parameters)
        if not self.timeVariable in self.parameterNames:
            raise DbdError(DBD_ERROR_NO_TIME_VARIABLE)
        
        # OK, we have some parameters to return:        
        if missing_parameters:
            logger.warning(f"Requested parameters not found: {','.join(missing_parameters)}.")
            
        ti=self.parameterNames.index(self.timeVariable)
        idx = [self.parameterNames.index(p) for p in valid_parameters]
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
                         int(return_nans),
                         int(self.skip_initial_line),
                         max_values_to_read)
        # map the contents of vi on timestamps and values, preserving the original order:
        idx_reorderd = [vi.index(i) for i in idx]
        # these are for good_parameters:
        timestamps = [numpy.array(r[i]) for i in idx_reorderd]
        values = [numpy.array(r[number_valid_parameters+i]) for i in idx_reorderd]
        # convert to decimal lat lon if applicable:
        for i, p in enumerate(valid_parameters):
            if return_nans:
                idx = numpy.where(numpy.isclose(values[i],1e9))[0]
                values[i][idx] = numpy.nan
            if self._is_latlon_parameter(p):
                if discardBadLatLon and not return_nans: #discards and return nans is not compatible.
                    # p is either a latitude or longitude parameter. Check now which one it is.
                    if "lat" in p:
                        value_limit = 9000 # nmea style
                    else:
                        value_limit = 18000 # nmea style
                    condition = numpy.logical_and(values[i]>=-value_limit, values[i]<=value_limit)
                    timestamps[i], values[i] = numpy.compress(condition, (timestamps[i], values[i]), axis=1)
                if decimalLatLon:
                    values[i] = toDec(values[i])
        # if we have any invalid parameters, insert empty arrays in the right places, or full length nan vectors if return_nans is True
        if return_nans:
            n_timestamps = timestamps[0].shape[0]
            def get_empty_array():
                return numpy.ones(n_timestamps)*numpy.nan
        else:
            def get_empty_array():
                return numpy.array([])
        for missing_parameter in missing_parameters:
            idx = parameters.index(missing_parameter)
            timestamps.insert(idx, get_empty_array())
            values.insert(idx, get_empty_array())
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
                try:
                    r.append(numpy.interp(t, _t, _v, left=numpy.nan, right=numpy.nan))
                except ValueError:
                    r.append(t * numpy.nan)
                    logger.info(f"No valid data to interpolate for '{params[i]}'.")

        return tuple(r)

        
    def _get_valid_parameters(self,parameters, invert=False, global_scope=False):
        if global_scope:
            p = self.headerInfo['parameter_list']
        else:
            p = self.parameterNames
        if not invert:
            validParameters=[i for i in parameters if i in p]
        else:
            validParameters=[i for i in parameters if not i in p]
        return validParameters

    def _is_latlon_parameter(self,x):
        return x in LATLON_PARAMS

    def _read_header(self, cacheDir):
        if not os.path.exists(cacheDir):
            raise DbdError(DBD_ERROR_CACHEDIR_NOT_FOUND, " (%s)"%(cacheDir))
        dbdheader = DBDHeader()
        result = dbdheader.read_header(self.fp)
        if result == DBD_ERROR_INVALID_DBD_FILE:
            raise DbdError(DBD_ERROR_INVALID_DBD_FILE,
                           f"{self.filename} seems not to be a valid DBD file.")
        elif result == DBD_ERROR_INVALID_ENCODING:
            raise DbdError(DBD_ERROR_INVALID_ENCODING,
                           f'{self.filename} has an invalid encoding.')
        # determine cache file name
        cacheID = dbdheader.info['sensor_list_crc'].lower()
        cacheFilename=os.path.join(cacheDir,cacheID+".cac")
        cacheFound=True # unless proven otherwise...
        parameter=[]
        if dbdheader.factored==1:
            # read sensorlist from cache
            if os.path.exists(cacheFilename):
                fpCache=open(cacheFilename,'br')
                parameter=dbdheader.read_cache(fpCache)
                fpCache.close()
            else:
                cacheFound=False
        else: # no need to check for factored==None; the value has been set for sure.
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

    def _get_by_read_per_byte(self,parameter):
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
            offsets,chunksize=self._read_state_bytes(paramidx)
            fp=self.fp.tell()
            if offsets!=None:
                # we found at least one value we would like to read, otherwise skip directly to the
                # next state block.
                for offset,idx in zip(offsets,paramidx):
                    if offset!=-1:
                        self.fp.seek(fp+offset)
                        x=self.fp.read(self.byteSizes[idx])
                        xs=self._convert_bytearray(x)
                        R[idx].append(xs)
                    else:
                        R[idx].append(R[idx][-1])
            # jump to the next state block
            if fp+chunksize+1>=fp_end:
                # jumped beyond the end.
                break
            self.fp.seek(fp+chunksize+1)
        return [R[i] for i in paramidx]

    def _get_by_read_per_chunk(self,parameter):
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
            offsets,chunksize=self._read_state_bytes(paramidx)
            fp=self.fp.tell()
            if offsets!=None:
                # we found at least one value we would like to read, otherwise skip directly to the
                # next state block.
                chunk=self.fp.read(chunksize+1)
                for offset,idx in zip(offsets,paramidx):
                    if offset!=-1:
                        s=self.byteSizes[idx]
                        xs=self._convert_bytearray(chunk[offset:offset+s])
                        R[idx].append(xs)
                    else:
                        R[idx].append(R[idx][-1])
            else:
                self.fp.seek(fp+chunksize+1)

            if fp+chunksize+1>=fp_end:
                # jumped beyond the end.
                break
        return [R[i] for i in paramidx]


    def _read_state_bytes(self,reqd_variables):
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

    def _convert_bytearray(self,bs):
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

    skip_initial_line: bool (default: True)
        If True, the first data line in each dbd file (and friends) is not read.


    
    Notes
    -----

    Upon creating the dbd file, when starting a new mission or dive segment, all parameters
    are written and marked as updated. In reality, most parameters are NOT update, and the
    value written is the value in memory, which may be several minutes old, or even longer. It
    has been pointed out to me that a handful parameters, are set only once, before creating the
    dbd file. Since these parameters are not of interest for normal data processing, the first
    line of data is skipped by default, but can be read if required.


    
    .. versionchanged:: 0.4.0
        ensure_paired and included_paired keywords have been replaced by complemented_files_only
        and complement_files, respectively.
    '''
    def __init__(self,filenames=None,pattern=None,cacheDir=None,complemented_files_only=False,
                 complement_files=False,banned_missions=[],missions=[],
                 max_files=None, skip_initial_line=True):

        self._ignore_cache=[] # list of files that should be ignored because out of set time limits
        self._accept_cache=[] # list of files that have data within set time limits
        self._parameter_names=dict(globally=set(), locally=set())
        if cacheDir is None:
            cacheDir=DBDCache.CACHEDIR
        self.banned_missions=banned_missions
        self.missions=missions
        self.mission_list=[]
        if not filenames and not pattern:
            raise DbdError(DBD_ERROR_NO_FILE_CRITERIUM_SPECIFIED)
        fns=DBDList()
        # A common mistake is to just supply a string for filenames (first argument)
        # Assume that it was meant as a pattern IF pattern is None.
        if isinstance(filenames, str):
            if pattern is None:
                pattern = filenames # assume filenames should have been pattern and hope for the best.
                filenames = None
            else:
                raise DbdError(DBD_ERROR_INVALID_FILE_CRITERION_SPECIFIED, "I got a string for <filenames> (no list), and a string for <pattern>.")
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
            self._add_paired_filenames()

        if complemented_files_only:
            self.pruned_files=self._prune_unmatched(cacheDir)

        self._update_dbd_inventory(cacheDir, skip_initial_line)
        self.parameterNames=dict((k,self._getParameterList(v)) \
                                     for k,v in self.dbds.items())
        self.parameterUnits=self._getParameterUnits()
        #
        self.time_limits_dataset=(None,None)
        self.time_limits=[None,None]
        self.set_time_limits()

##### public methods
    def get(self, *parameters, decimalLatLon=True, discardBadLatLon=True, return_nans=False, include_source=False,
            max_values_to_read=-1):
        '''Returns time and value tuple(s) for requested parameter(s)

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

        include_source : bool, optional
            If True, a list with a reference for each data point to the DBD object, where the datapoint originated from.
            If called with a single parameter, a tuple of a Nx2 array with data and a list of N elements with refrences to a DBD object.
            If called for more parameters, a list of such tuples is returned.
        
            Default value: False

        max_values_to_read : int, optional
            if > 1, then reading is stopped after this many values have been read.
            Default value : -1

        Returns
        -------
        (ndarray, ndarray) or
        ((ndarray, ndarray), list) or
        [(ndarray, ndarray), (ndarray, ndarray), ...]
        [((ndarray, ndarray), list), ((ndarray, ndarray), list), ...]
            for a single parameter, for a single parameter, including source file list, for multiple parameters,
            for multiple parameters, including source file list, respectively.

        .. versionchanged:: 0.5.5 For a single parameter request, the number of values to be read can be limited.

        '''
        # It only makes sense to limit the number of parameters read when a single parameter is requested. Check for this.
        if max_values_to_read>0 and len(parameters)!=1:
            raise ValueError("Limiting the values to be read for multiple parameters potentially yields undefined behaviour.\n")

        eng_variables = []
        sci_variables = []
        positions = []
        invalid_parameters = self._get_valid_parameters(parameters, invert=True, global_scope=True)
        unavailable_parameters = self._get_valid_parameters(parameters, invert=True, global_scope=False)
        # invalid parameters are parameters that don't exist in any cache file used by the opened files
        # unavailable_parameters are parameters that are not stored in any of these files. They are marked F in the cache file.
        
        if invalid_parameters:
            if len(invalid_parameters)==1:
                mesg = f"Parameter {invalid_parameters[0]} is an unknown glider sensor name."
            else:
                mesg = f"Parameters {{{','.join(invalid_parameters)}}} are unknown glider sensor names."
            raise DbdError(value=DBD_ERROR_NO_VALID_PARAMETERS, mesg=mesg, data=invalid_parameters)

        # We don't want to trigger an abort if we ask for a parameter which has no data. Just return empty
        # arrays. If not desired, uncomment block below:
        #
        # if unavailable_parameters:
        #     if len(unavailable_parameters)==1:
        #         mesg = f"Parameter {unavailable_parameters[0]} has no data."
        #     else:
        #         mesg = f"Parameters {{{','.join(unavailable_parameters)}}} hava no data."
        #     raise DbdError(value=DBD_ERROR_NO_DATA, mesg=mesg, data=unavailable_parameters)

        for p in parameters:
            if p in self.parameterNames['sci']:
                positions.append(("sci", len(sci_variables)))
                sci_variables.append(p)
            elif p in self.parameterNames['eng']:
                positions.append(("eng", len(eng_variables)))
                eng_variables.append(p)

        kwds=dict(decimalLatLon=decimalLatLon, discardBadLatLon=discardBadLatLon,
                  return_nans=return_nans, include_source=include_source,
                  max_values_to_read=max_values_to_read)

        if len(sci_variables)>=1:
            r_sci = self._worker("sci", *sci_variables, **kwds)
        if len(eng_variables)>=1:
            r_eng = self._worker("eng", *eng_variables, **kwds)
        r = []
        for target, idx in positions:
            if target=='sci':
                r.append(r_sci[idx])
            else:
                r.append(r_eng[idx])
        for i,p in enumerate(parameters):
            if p in unavailable_parameters:
                r.insert(i, (numpy.array([]), numpy.array([])))
        if len(parameters)==1:
            return r[0]
        else:
            return r


    def _get_valid_parameters(self,parameters, invert=False, global_scope=False):
        parameters = set(parameters)
        if global_scope:
            p = self._parameter_names['globally']
        else:
            p = self._parameter_names['locally']
        validParameters=p.intersection(parameters)
        if invert:
            validParameters=parameters.difference(p.intersection(parameters))
        return list(validParameters)

        
    def get_xy(self,parameter_x,parameter_y,decimalLatLon=True, discardBadLatLon=True,
               interpolating_function_factory=None):
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

        interpolating_function_factory : function factory, dictionary of function factories, None, optional
            Specification of a function factory to interpolate data. A dictionary of interpolating_function_factories
            allows the specification of specific functions for specific parameters. If none is defined, linear interpolation
            is used.


        Returns
        -------
        (ndarray, ndarray)
            tuple of value vectors


        .. versionadded:: 0.5.8
           keyword option interpolating_function_factory
     

        '''
        _, x, y = self.get_sync(parameter_x, parameter_y, decimalLatLon=decimalLatLon,
                                discardBadLatLon=discardBadLatLon, interpolating_function_factory=interpolating_function_factory)
        return x, y

    def get_sync(self,*parameters,decimalLatLon=True, discardBadLatLon=True, interpolating_function_factory=None):
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

        interpolating_function_factory : function factory, dictionary of function factories, None, optional
            Specification of a function factory to interpolate data. A dictionary of interpolating_function_factories
            allows the specification of specific functions for specific parameters. If none is defined, linear interpolation
            is used.

        
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

        .. versionadded:: 0.5.8
           keyword option interpolating_function_factory
     
        '''
        if len(parameters)<2:
            raise ValueError('Expect at least two parameters.')
        if len(parameters)==2 and (isinstance(parameters[1], list) or isinstance(parameters[1], tuple)):
            # obsolete calling signature.
            logger.info("Calling signature of get_sync() has changed in version 0.4.0.")
            parameters = [parameters[0]] + parameters[1]
        tv = self.get(*parameters, decimalLatLon=decimalLatLon, discardBadLatLon=discardBadLatLon,
                      return_nans=False)
        
        default_interpolating_function_factory = partial(si_interp1d, bounds_error=False, fill_value=numpy.nan)
        
        t = tv[0][0]
        r = []
        for i, (p,(_t, _v)) in enumerate(zip(parameters, tv)):
            if i==0:
                r.append(_t)
                r.append(_v)
            else:
                # Create an interpolation function factory
                logger.debug(f"Checking for ifun factory parameter {i}: {p}")
                if interpolating_function_factory is None:
                    ifun_factory = default_interpolating_function_factory
                    logger.debug("using default")
                else:
                    try:
                        ifun_factory = interpolating_function_factory[p]
                        logger.debug(f"Using specific for parameter {p}")
                    except KeyError:
                        ifun_factory = default_interpolating_function_factory
                        logger.debug(f"Using default")
                    except TypeError:
                        ifun_factory = interpolating_function_factory
                        logger.debug(f"custom for all")
                try:
                    ifun = ifun_factory(_t, _v)
                except ValueError:
                    r.append(t * numpy.nan)
                    logger.info(f"No valid data to interpolate for '{parameters[i]}'.")
                else:
                    r.append(ifun(t))
        return tuple(r)



    def get_CTD_sync(self, *parameters, decimalLatLon=True, discardBadLatLon=True,
                     interpolating_function_factory=None):
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

        interpolating_function_factory : function factory, dictionary of function factories, None, optional
            Specification of a function factory to interpolate data. A dictionary of interpolating_function_factories
            allows the specification of specific functions for specific parameters. If none is defined, linear interpolation
            is used.


        Returns
        -------
        (ndarray, ndarray, ...)
            Time vector (of first parameter), C, T and P values, and
            interpolated values of subsequent parameters.


        Notes
        -----
        .. versionadded:: 0.4.0

        .. versionadded:: 0.5.8
            keyword interpolating_function_factory

        '''
        CTD_type = self.determine_ctd_type()
        CTDparameters = [f"sci_{CTD_type}_timestamp", "sci_water_cond",
                         "sci_water_temp", "sci_water_pressure"]
        offset = len(CTDparameters) + 1 # because of m_present_time is
                                        # also returned.
        tmp = self.get_sync(*CTDparameters, *parameters, decimalLatLon=decimalLatLon, discardBadLatLon=discardBadLatLon,
                            interpolating_function_factory=interpolating_function_factory)
        # remove all time<=1 timestamps, as there can be nans here too.
        tmp = numpy.compress(tmp[1]>1, tmp, axis=1)
        condition = tmp[2]>0 # conductivity > 0
        if len(parameters):
            # check for any leading or trailing nans in v, caused by
            # interpolation:
            #
            # collapse v on one vector, and make a condition where the collapsed
            # vector is nan
            a = numpy.prod(tmp[offset:], axis=0)
            condition &= numpy.isfinite(a)
        if numpy.all(condition==False):
            raise DbdError(DBD_ERROR_NO_DATA_TO_INTERPOLATE)
        # ensure monotonicity in time
        dt = numpy.hstack( ([1], numpy.diff(tmp[1])) )
        condition &= dt>0
        _, tctd, C, T, P, *v = numpy.compress(condition, tmp, axis=1)
        return tuple([tctd, C, T, P] + v)

    def determine_ctd_type(self):
        '''
        Determines CTD type installed from the presence of CTD specific name for the time stamp.

        Returns
        -------
        string
            {"ctd41cp", "rbrctd"}

        If unable to get a positive CTD identification, it is assumed the CTD installed is a Seabird
        CTD, returning "ctd41cp".
        
        Notes
        -----
        .. versionadded:: 0.5.5
        '''
        # Gliders can be equipped with a Seabird CTD or an RBR
        # CTD. The sensor sci_ctd_is_installed or
        # sci_rbrctd_is_installed is set accordingly. However, we may
        # read a file for which either parameter is not updated, so it
        # is not available. Therefore we look at whether the ctd's timestamp is available.
        ctd_types = ["ctd41cp", "rbrctd"]
        for ctd_type in ctd_types:
            is_installed = self._has_ctd_installed(ctd_type)
            if is_installed:
                break
        if is_installed:
            return ctd_type
        # Fallback in case neither could be determined, assume seabird
        # ctd. An exception will be thrown elsewhere.
        return ctd_types[0]
            
    def _has_ctd_installed(self, ctd_type):
        '''
        Parameters
        ----------
        ctd_type: string
            identifier for ctd make.

        Current possible options: "ctd41cp" for Seabird CTD and "ctdrbr" for RBR CTD"

        Returns
        -------
        bool
            Boolean value indicating the ctd type is installed.
        '''
        MAX_VALUES_TO_READ=15
        
        loggerLevel=logger.getEffectiveLevel()
        if loggerLevel < logging.ERROR:
            logger.setLevel(logging.ERROR)
        try:
            t, tctd = self.get(f"sci_{ctd_type}_timestamp", max_values_to_read=MAX_VALUES_TO_READ)
        except DbdError as e:
            logger.setLevel(loggerLevel)
            if e.value == DBD_ERROR_NO_VALID_PARAMETERS: # If an error is raised, we expect this one
                result = False
            else: # else reraise the error.
                raise(e)
        else:
            logger.setLevel(loggerLevel)
            number_of_timestamps = len(tctd)
            if number_of_timestamps>=MAX_VALUES_TO_READ:
                result = True
            else:
                result = False
        return result
        
        
    def set_skip_initial_line(self, skip_initial_line):
        '''Sets the reading mode of the binary reader to skip the initial data entry or not.

        Parameters
        ----------
        skip_initial_line : bool
            Sets the attribute `skip_initial_line` of each DBD
            instance, controlling the reading of the first data entry
            of each binary file.
        '''
        for i in chain(*self.dbds.values()):
            i.skip_initial_line = skip_initial_line

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
        fn = fn.lower()
        return fn.endswith("ebd") | fn.endswith("tbd") | fn.endswith("nbd") | fn.endswith("ecd") | fn.endswith("tcd") | fn.endswith("ncd")

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
        return self._get_time_range(self.time_limits,fmt)

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
        return self._get_time_range(self.time_limits_dataset,fmt)

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
            self.time_limits[0]=self._convert_seconds(minTimeUTC)
        if maxTimeUTC:
            self.time_limits[1]=self._convert_seconds(maxTimeUTC)
        self._refresh_cache()

    def close(self):
        ''' Close all open files '''
        for i in self.dbds['eng']+self.dbds['sci']:
            i.close()


    #### private methods

    def _get_matching_fn(self, fn):
        sci_extensions = ".ebd .tbd .nbd .ecd .tcd .ncd".split()
        _, extension = os.path.splitext(fn)
        matchingExtension = list(extension) # make the string mutable.
        if extension not in sci_extensions:
            matchingExtension[1] = chr(ord(extension[1])+1)
        else:
            matchingExtension[1] = chr(ord(extension[1])-1)
        matchingExtension = "".join(matchingExtension)
        matchingFn = fn.replace(extension,matchingExtension)
        return matchingFn

    def _add_paired_filenames(self):
        to_add=[]
        for fn in self.filenames:
            mfn = self._get_matching_fn(fn)
            if os.path.exists(mfn):
                to_add.append(mfn)
        self.filenames+=to_add

    def _get_matching_dbd(self,fn):
        '''returns matching dbd object corresponding to fn. If fn is not in the current list
           of accepted dbds, then None is returned.'''

        if fn not in self.filenames:
            return None
        # ok, the file is in the cache, which implies it is in self.dbds too.
        matchingFn=self._get_matching_fn(fn)
        if matchingFn in self.filenames:
            return matchingFn
        else:
            return None

    def _prune(self,filelist, cacheDir=None):
        ''' prune all files in filelist.'''
        for tbr in filelist:
            self.filenames.remove(tbr)

    def _prune_unmatched(self, cacheDir=None):
        ''' prune all files which don't have a science/engineering partner
            returns list of removed files.'''
        to_be_removed=[fn for fn in self.filenames if not self._get_matching_dbd(fn)]
        self._prune(to_be_removed, cacheDir)
        return tuple(to_be_removed)


    def _convert_seconds(self,timestring):
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

    def _refresh_cache(self):
        ''' Internal. Sets global and selected time limits, and a cache with those files
            that matche the time selection criterion
        '''
        self._ignore_cache.clear()
        self._accept_cache.clear()
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
                self._ignore_cache.append(dbd)
            else:
                self._accept_cache.append(dbd)
                # this is a file that matches the selection criterion.
                if t<time_limits[0]:
                    time_limits[0]=t
                if t>time_limits[1]:
                    time_limits[1]=t
        self.time_limits_dataset=tuple(time_limits_dataset)
        time_limits[0]=max(time_limits[0],time_limits_dataset[0])
        time_limits[1]=min(time_limits[1],time_limits_dataset[1])

    def _format_time(self,t,fmt):
        tmp = datetime.datetime.fromtimestamp(t, datetime.UTC)
        return tmp.strftime(fmt)

    def _get_time_range(self,time_limits,fmt):
        if fmt=="%s":
            return time_limits
        else :
            return list(map(lambda x: self._format_time(x,fmt), time_limits))

    def _safely_open_dbd_file(self, fn, cacheDir, skip_initial_lines, missing_cacheIDs, check_for_compressed_cac=True):
        dbd = None
        try:
            dbd=DBD(fn, cacheDir, skip_initial_lines)
        except DbdError as e:
            #Typically the call in the try block may fail if the
            # cache file cannot be found because it is not in the
            # specfied directory or the cache directory cannot be
            # found.  Flesh out these cases and keep a log of
            # them, we can raise an error later with all the
            # information on missing cache files and problems
            # later, so the caller can handle the error
            # meaningfully.
            if e.value == DBD_ERROR_CACHEDIR_NOT_FOUND:
                # if this happens, this will happen for all subsequent files to load.
                raise DbdError(DBD_ERROR_CACHEDIR_NOT_FOUND,
                               mesg=f"\nCache directory {cacheDir} could not be accessed.",
                               data=DbdError.MissingCacheFileData(None, cacheDir))
            elif e.value == DBD_ERROR_CACHE_NOT_FOUND:
                # The cache file could not be found. Let's try if there is a compressed cache file.
                # if yes, then decompress it and try again.
                _cacheID = list(e.data.missing_cache_files.keys())[0] # we open a single file, so only one cache file can be missing.
                missing_cache_filename = os.path.join(cacheDir, _cacheID+'.ccc')
                if check_for_compressed_cac and os.path.exists(missing_cache_filename):
                    dbdreader.decompress.decompress_file(missing_cache_filename)
                    result = "try_again"
                else:
                    for k in e.data.missing_cache_files.keys():
                        missing_cacheIDs[k].append(fn)
                    result = "failed"
            else: # some other problem. Just ignore the file but produce a warning.
                logger.warning('File %s could not be loaded', fn)
                logger.debug('Exception was %s', e)
                logger.debug('Exception value was %d', e.value)
                result = "ignore"
        else:
            result = "ok"
            dbd.close()
        return dbd, result
        
    def _update_dbd_inventory(self, cacheDir, skip_initial_lines):
        self.dbds={'eng':[],'sci':[]}
        filenames=list(self.filenames)
        missing_cacheIDs = defaultdict(list)
        for fn in self.filenames:
            dbd, result = self._safely_open_dbd_file(fn, cacheDir, skip_initial_lines, missing_cacheIDs)
            if result == "ignore" or result == "failed":
                filenames.remove(fn)
            elif result == "try_again":
                dbd, result = self._safely_open_dbd_file(fn, cacheDir, skip_initial_lines, missing_cacheIDs, check_for_compressed_cac=False)
                if result == "ignore" or result == "failed":
                    filenames.remove(fn)
            if result!="ok":
                continue
            mission_name=dbd.get_mission_name()
            if mission_name in self.banned_missions:
                filenames.remove(fn)
                continue
            if self.missions and mission_name not in self.missions:
                filenames.remove(fn)
                continue
            # so we decided to keep the file.
            if mission_name not in self.mission_list:
                self.mission_list.append(mission_name)
            if self.isScienceDataFile(fn):
                ft = 'sci'
            else:
                ft = 'eng'
            self.dbds[ft].append(dbd)
            self._parameter_names['globally'].update(dbd.headerInfo['parameter_list'])
            self._parameter_names['locally'].update(dbd.parameterNames)

        self.filenames=filenames
        # At this stage we may have zero or more files, and some could have been removed.
        # We will raise an error when cache files are missing and when there are no files at all.
        if missing_cacheIDs:
            # craft some useful error message
            mesg = f"\nOne or more cache files could not be found in {cacheDir}:\n"
            for k, v in missing_cacheIDs.items():
                mesg+=f"{k} reqd by {v[0]}"
                if len(v)>1:
                    mesg += f" + {len(v)-1} more files."
                mesg+="\n"
            data = DbdError.MissingCacheFileData(dict([(k,v) for k,v in missing_cacheIDs.items()]), cacheDir)
            raise DbdError(DBD_ERROR_CACHE_NOT_FOUND, mesg=mesg, data=data)
        if len(self.dbds['sci'])+len(self.dbds['eng'])==0:
            raise DbdError(DBD_ERROR_ALL_FILES_BANNED, " (Read %d files.)"%(len(self.filenames)))


    def _getParameterUnits(self):
        dbds=self.dbds['eng']
        units=[]
        for i in dbds:
            units+=[j for j in i.parameterUnits.items()]
        dbds=self.dbds['sci']
        for i in dbds:
            units+=[j for j in i.parameterUnits.items()]
        return dict(i for i in (set(units)))

    def _getParameterList(self,dbds):
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

    def _worker(self, ft, *p, **kwds):
        try:
            include_source = kwds.pop("include_source")
        except KeyError:
            include_source = False
        data = dict([(k,[]) for k in p])
        srcs = dict([(k,[]) for k in p])
        error_mesgs = []
        time_values_read_sofar=0
        for i in self.dbds[ft]:
            if i in self._ignore_cache:
                continue
            try:
                t, v = i._get(*p, **kwds)
            except DbdError as e:
                # ignore only the no_data_to_interpolate_to error
                # as the file is probably (close to) empty
                if e.value==DBD_ERROR_NO_DATA_TO_INTERPOLATE_TO:
                    continue
                elif e.value==DBD_ERROR_NO_VALID_PARAMETERS:
                    logger.debug("get() call returned an error on invalid parameters.")
                    # set1 is all known parameters:
                    set1 = set([i for i in chain(*self.parameterNames.values())]) 
                    set2 = set(e.data) # missing parmaeters
                    if set2.intersection(set1) == set2:
                        # all missing parameters in *this* file are
                        # known from at least on other file read.
                        kwds['check_for_invalid_parameters']=False
                        t, v = i._get(*p, **kwds)
                    else:
                        # at least one unknown parameter was aksed for. Reraise the error.    
                        raise e
                else:
                    # in all other cases reraise the error..
                    raise e
                
            # add the data read to the data dictionary.    
            for _p, _t, _v in zip(p, t, v):
                data[_p].append( (_t, _v) )
                if include_source:
                    srcs[_p] += [i] * len(_t)
            # Check if we request only a limited number of
            # values. Note that the sanity check for not
            # requesting more than one parameter is made in DBD's
            # get() method.
            if kwds["max_values_to_read"]>0:
                time_values_read_sofar+=len(t[0])
                if time_values_read_sofar>=kwds["max_values_to_read"]:
                    break
                    
        if not all(data.values()):
            # nothing has been added, so all files should have returned nothing:
            raise(DbdError(DBD_ERROR_NO_VALID_PARAMETERS,
                           "\n".join(error_mesgs)))
        if not include_source:
            data_arrays = [(numpy.hstack([_d[0] for _d in data[_p]]), numpy.hstack([_d[1] for _d in data[_p]])) for _p in p]
        else:
            data_arrays = [((numpy.hstack([_d[0] for _d in data[_p]]), numpy.hstack([_d[1] for _d in data[_p]])), srcs[_p]) for _p in p]
        return data_arrays

# Initialises the class
DBDCache()
    
