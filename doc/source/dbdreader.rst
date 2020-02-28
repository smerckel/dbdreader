Dbdreader helper classes and functions
**************************************

API
===

Apart from implementing the DBD and MultiDBD classes, the dbdreader
module implements a number of helper classes and functions. They are
detailed below.

.. automodule:: dbdreader
   :members: DBDList, DBDPatternSelect,epochToDateTimeStr,strptimeToEpoch,toDec 


Examples
========


DBDList
-------

DBDList derives from list, but implements the sort() method such that
dbd files are sorted correctly.

These files have the following format, for example

amadeus-2014-63-1-3.dbd

Here:

- 63: is the Julian day when the mission was started
- 1:  second mission started this day
- 3:  fourth segment of current mission

If sorting these filenames, then  

amadeus-2014-63-1-10.dbd

would be ordered before

amadeus-2014-63-1-2.dbd,

which is obviously not what we want. DBDList fixes this.

::

   import glob.glob
   import dbdreader

   fns=glob.glob("some_glider*.sbd")
   # fns is now unsorted. Unfortunately, due to the inconvenient
   # naming convention, fns does not necessiraly sort correctly.

   fns_sortable=dbdreader.DBDList(fns)
   fns_sortable.sort()
   # fns_sortable is now sorted correctly. Guaranteed.


.. _sec_dbdpatternselect:

DBDPatternSelect
----------------

The DBDPatternSelect class allows you to select filenames the contain
data for a specific time window in an easy way.

::

   import dbdreader

   pattern_selector=dbdreader.DBDPatternSelect()

   #Select only those files later than 24 Jult 2014 18:00
   pattern_selector.set_date_format("%d %b %Y %H")
   selection=pattern_selector.select(pattern="../data/amadeus*.sbd",from_date="24 Jul 2014 18")

   # read only the selected sbd files and matching tbd files.
   dbd=dbdreader.MultiDBD(filenames=selection,include_paired=True)
