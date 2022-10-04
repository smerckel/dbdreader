Selecting data for a specific time range
****************************************

Not always it is desired to read and process all files that are
available. The class :class:`dbdreader.DBDPatternSelect` provides a way to retrieve
only those file names that are limited to a certain time frame, see :ref:`sec_dbdpatternselect`.

Alternatively, we can also use the :class:`dbdreader.MultiDBD` API to
get information on time spans and select data just for a specific time
window::

  import dbdreader
  
  dbd=dbdreader.MultiDBD(pattern="data/amadeus*.[st]bd")

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
 


See also the methods :func:`dbdreader.MultiDBD.get_global_time_range` and :func:`dbdreader.MultiDBD.set_time_limits`.
