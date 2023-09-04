Selecting specific files
************************

Restricting the time frame
==========================

Not always it is desired to read and process all files that are
available. The class :class:`dbdreader.DBDPatternSelect` provides a way to retrieve
only those file names that are limited to a certain time frame.

You can use the class :class:`dbdreader.DBDPatternSelect` to select
just those files that match a specific time interval.

For example::

  import dbdreader

  ps = dbdreader.PatternSelect()

  # By default, dates are entered in "%d %m %Y"-format. Let's changed
  # that to be able to specify a specific time:
  ps.set_date_format("%d %m %Y %H:%M")

  filenames = ps.select(pattern="data/amadeus*.[st]bd", from_date="24 7 2014 18:00")

  # Feed those files into a MultiDBD object:
  
  data = dbdreader.MultiDBD(filenames)


Besides specifying the ``from_date`` we could also additionally
specify the ``until_date``, see also
:func:`dbdreader.PatternSelect.select`.

      
Binning files
=============

A other use of this class is to bin files in sections of a specific
duration. To that end we can use the :func:`dbdreader.PatternSelect.bins`,
for example ::
  
  import dbdreader
	
  ps = dbdreader.PatternSelect()

  binned_filenames = ps.bins(pattern="data/amadeus*.[st]bd", binsize=86400)

  # Feed those files into a MultiDBD object:
  for filenames in binned_filename:
      data = dbdreader.MultiDBD(filenames)
      ... process ...


