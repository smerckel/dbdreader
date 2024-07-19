Class MultiDBD : reading multiple files
***************************************

MultiDBD API
============

The MultiDBD class is designed to be used with multiple files, either dbd's
(sbd's) or ebd's (tbd's), or a mixture.

As for single dbd files, using the class::dbdreader.DBD, the behaviour
of the binary reader can be modified using the ``skip_initial_line``
keyword to the constructor. See also :ref:`Class DBD : reading single files`.


.. autoclass:: dbdreader.MultiDBD
   :members:

      
MultiDBD Example
================
::

        import numpy as np
        import dbdreader


        # This examples shows how to deal with multiple dbd files. This can be
        # a sdb and tbd file for a single segment, or a number of sbd files
        # only, or a combionation of both. 
        #
        # This example uses the MultiDBD class. You can require that each sbd
        # file must have its accompanying tbd file, or that you specify sbd
        # files only and MultiBDB looks for the accompanying tbd files. You
        # can limit the number of files processed to the first n or last n
        # files, mainly for developing purposes. See the doc string for pointers.
        #
        # You can specify the files to be opened as a list of filenames, or as
        # a pattern using wild cards, using either the filenames=[...] keyword
        # or patterns='....' keyword.
        #
        # All files that match are used. You can narrow down your selecting by
        # setting the start and/or end times. This reflects to the opening
        # times of the files. (The reason for this is that the header only
        # needs to be read, and not every possible variable to find start and
        # end times of each file.
        #
        # There are basically two ways of narrowing down the number of files
        # processed. You can use the set_time_limits() method of the MultiDBD
        # class or you can use DBDPatternSelect. The latter selects files
        # according to a pattern, or as a list of files. The select() method
        # returns a list of files that match from and until dates, which can
        # be used to create a MultiDBD instance using the filenames=[]
        # keyword.

        # Below this is put to the test.


        # open some files, using a pattern

        dbd=dbdreader.MultiDBD(pattern="data/amadeus*.[st]bd")

        # print what parameters are available:
        print("we the following science parameters:")
        for i,p in enumerate(dbd.parameterNames['sci']):
            print("%2d: %s"%(i,p))
        print("\n and engineering paramters:")
        for i,p in enumerate(dbd.parameterNames['eng']):
            print("%2d: %s"%(i,p))

        # get the measured depth

        tm,depth=dbd.get("m_depth")

        max_depth=depth.max()
        print("\nmax depth found is %f m"%(max_depth))

        # get lat lon
        lat,lon=dbd.get_xy("m_lat","m_lon")

        # interpolate roll speed on depth time
        tm,depth,roll,speed=dbd.get_sync("m_depth","m_roll","m_speed")

        print("\nmax speed %f m/s"%(speed.compress(np.isfinite(speed)).max()))


        # print the time range of the files
        tr=dbd.get_global_time_range()
        # these are the opening times of the first and last files.
        print("We have data from %s until %s"%tuple(tr))

        # limit our data
        print("we limit our data to include only files opened after 24 Jul 2014 18:00")
        # use only data files that are opened after 6 pm on 24 Jul 2014
        dbd.set_time_limits(minTimeUTC="24 Jul 2014 18:00")

        tm1,depth1=dbd.get("m_depth")
        print("start time full time range:")
        print(dbdreader.epochToDateTimeStr(tm[0]))
        print("start time reduced time range:")
        print(dbdreader.epochToDateTimeStr(tm1[0]))

      
        # time selection, we can achieve in a different way too.

        pattern_selector=dbdreader.DBDPatternSelect()
        pattern_selector.set_date_format("%d %b %Y %H")
        selection=pattern_selector.select(pattern="data/amadeus*.[st]bd",from_date="24 Jul 2014 18")

        print("full list of sbd files:")
        for i,n in enumerate(dbd.filenames):
            if n.endswith("sbd"):
                print("%d: %s"%(int(i/2),n))
        print("and...")
        print("reduced list of sbd files:")
        for i,n in enumerate(selection):
            if n.endswith("sbd"):
                print("%d: %s"%(int(i/2),n))

		
Custom interpolating function factories
=======================================
The methods :func:`dbdreader.MultiDBD.get_sync`,
:func:`dbdreader.MultiDBD.get_CTD_sync` and
:func:`dbdreader.MultiDBD.get_xy`
apply an interpolation algorithm to the second and any following
parameter requrested. The keyword `interpolating_function_factor` can
be used to specify the interpolating function to be used for this. If
the keyword is not set (default value `None`), then
:func:`numpy.interp` is used with keywords `left=numpy.nan` and
`right=numpy.nan`.

For a parameter such as `m_heading` this is not entirely correct when
the glider changes course passing the direction North. For this
purpose an adapted interpolation function can be used :func:`dbdreader.heading_interpolating_function_factory`, which
interpolates according this algorithm:

::
   
  input ti, t and v
  
  x = cos(v)
  y = sin(v)
  xi = interp(ti, t, x)
  yi = interp(ti, t, y)
  vi = numpy.arctan2(yi, xi)

The actual implementation looks like:

::

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
    return  lambda _t: numpy.arctan2(yi(_t), xi(_t))%(2*numpy.pi)


This implementation can be used as a template for user interpolating
schemes. The implementation might appear unnecessarily complicated. It
is important to notice that the function does *do* the interpolation,
but it is an interpolation function factory, that is, it creates a
function that can perform the interpolation. The reason for this is
that the function can only be created from the moment the input data are know. 
