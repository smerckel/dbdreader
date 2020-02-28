Reading CTD (and other data) synchronised
*****************************************


A reoccurring problem is it to read CTD and other science parameters,
and to ensure that they are all interpolated on the same time axis (that of
the CTD). To that end, the :class:`dbdreader.MultiDBD` provides a method to do
so with ease :func:`dbdreader.MultiDBD.get_CTD_sync`:

::

   import dbdreader
   dbd=dbdreader.MultiDBD(pattern='data/amadeus-2014-204-05-*.[de]bd')
   tctd, C, T, P, b, p = dbd.get_CTD_sync("m_ballast_pumped", "m_pitch")

 
In this example, the CTD parameters C, T, and P are read and returned
on the timestamp of the CTD measurements. Any additional parameters,
in this case "m_ballast_pumped" and "m_pitch", are additionally
interpolated and added.

.. note ::

    At the beginning of some data files, the CTD data can be set to
    default values. This method filters out those bogus values, but
    otherwise returns the parameters as is. That is, conductivity and
    pressure have units S/m and bar, respectively.
