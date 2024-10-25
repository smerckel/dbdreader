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
is important to notice that the function does not *do* the
interpolation itself,
but it creates an interpolation function (interpolation function
factory).
The reason for this is
that the function can only be created from the moment the input data are known. 

How to use it?
--------------
A custom interpolating function factory can be used by specifying the
keyword `interpolating_function_factory`. If set to a specific
function factory, this function will be used for *all* parameters that are
listed to interpolated. For example:

::

   dbd = dbdreader.MultiDBD(<some files>)

   tm, depth, heading = dbd.get_sync("m_depth", "m_heading", interpolating_function_factory=dbdreader.heading_interpolating_function_factory)   

In this example only one parameter is set for interpolation
(m_heading) and this one will be interpolated using the specified
function.

Now, consider this call:

::

   tm, depth, heading, m_de_oil_vol = dbd.get_sync("m_depth", "m_heading", interpolating_function_factory=dbdreader.heading_interpolating_function_factory)   


In this case the custom interpolation would be applied to the heading
data and the buoyancy engine data. The latter would return values only
between 0 and 2π, which is not desired. To specify that the custom
function is only applied to the parameter name `m_heading`, we supply
a dictionary, like this:

::
   
   iff = dict(m_heading=dbdreader.heading_interpolating_function_factory)
   
   tm, depth, heading, m_de_oil_vol = dbd.get_sync("m_depth", "m_heading", "m_de_oil_vol", interpolating_function_factory=iff)   


In this case, the interpolating function factory is only used for
those parameters for which is a dictionary key. All missing keys are
interpolated using the default function.
