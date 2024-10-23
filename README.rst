|PyPI version| |Docs badge| |License|

DBDREADER
=========

Synopsis
--------
Slocum ocean gliders are autonomous underwater vehicles, used for
making oceanographic measurements. The data that these devices and
their sensors collect, are stored in binary data files. The python
module *dbdreader* provides the utilities to extract the data from the
binary files, so that they can be further analysed.

Change log
----------

version 0.5.8

* Changes default location for cache files on linux from
  $HOME/.dbdreader to $HOME/.local/share/dbdreader

* Introduces new class DBDCache to manage the location where cache
  files are looked up. Constructing an object with an arguments (re-)sets a
  default path, avoiding the need to use the keyword cacheDir when
  creating objects of DBD and MultiDBD classes.

* Fixes an issue with MultiDBD when a parameter is requested that is
  not present in all files, but in at least one. The get() method
  returns just those data that are present. In case of get_sync and
  friends, data are interpolated if possible, or padded with nans.

Version 0.5.7

* Drops dependency on python 3.10+, introduced in 0.5.6, and should
  work still with python 3.9.

Version 0.5.6

* Moves data directory under dbdreader, making these files accessible
  after an pip install

Version 0.5.5

* Makes MultiDBD's get_CTD_sync method compatible with RBR CTD data.

Version 0.5.4

* Adds support for reading compressed data files for windows platform.
* Improved building environment

Version 0.5.1

* Adds support for reading compressed data files
* dbdrename.py now accepts -x and -X options to rename compressed data files as uncompressed data files

Version 0.4.15

* Modifies sorting key algorithm to the DBDList class. This fixes a 
  bug when glider data filenames are composed of a glider name that 
  contains a dash. For example, filenames such as hereon-amadeus-2019-3-1.sbd
  would fail, but are valid now.

Version 0.4.14

* Adds a new option to the get() method of the MultiDBD class, where
  if the keyword include_sources=True, for each parameter an
  additional list is returned that has for each data point a reference
  to the DBD instance that produced the data point. This allows to
  query the source of a specific data point.

  This merges the (modified) pull request #14 by MCazaly.

Version 0.4.13

* Modifies behaviour when the user requests a parameter that has no
  data. If the requested parameter is not a valid glider sensor name,
  assume a user-error and raise an exception, otherwise return an
  empty array.

  This behaviour fixes a bug for MultiDBD:
  each file opened with MultiDBD would fail to produce any data if one or
  more parameters that are asked for, are not present in the file.
   
  New behaviour returns data for the exisiting parameters (only); empty
  array for the missing parameters (or nans if return_nans=True)

  Concludes pull request #16 by jklymak.

Version 0.4.12

* PatternSelect now accepts the option of a non-standard cache
  directory.
  Thanks to hawesie.

* MultiDBD's get_sync() now returns nan's for those parameters for
  which no data exist, provided that at least one of the requested
  parameters contains data. 
  
Version 0.4.11

* Version 0.4.9 introduced a bug that in some rare circumstances caused
  segmentation faults. This has been fixed.

* Merged pull request by roje-bodc with improved error handling in
  case of missing cache files. If a DbdError occurs due to a missing
  cache file, detailed information can be obtained from the .data
  property of the exception instance.


Version 0.4.10

* Includes pull request by jklymak, which allows dbdreader to deal
  with empty files, and files capitalised file extensions, as well as
  a check on the encoding version.

* Includes a bug fix when raising an exception when handling a prior
  exception in case of reading problematic files.

* Assumes that if the first parameter given to MultiDBD is a string,
  the user did not mean to provide a list of filename strings, but a
  pattern. An error is raised if pattern is specified explicitly when
  filenames is given as a string.

Version 0.4.9

* Bug fix for handling inf values correctly (issue #8). Thanks to jr3cermak for spotting this bug.
* Bug fix for incorrect behaviour when reading the time parameter explicitly for example xxx.get("m_present_time").

Version 0.4.8

* Support for reading {demnst}bd files from G3S gliders (issue #6). (Thanks to Owain Jones)

* Bug fix for correctly throwing an exception when cache file is missing(issue #5)

Version 0.4.7

* Bug fix for reading dbd files on Windows.

* a wheel provided for CPython 3.9 on Windows 64 bit.  

Version 0.4.6

* Added  get_CTD_sync, a convenience method to retrieve CTD data, and other parameters mapped on the CTD time stamps. Also ensures time stamps are monotonically increasing.

* Adds bounds to what values of latitude and longitude are considered valid.

Version 0.4.5

* dbdreader now ignores the first line of data in each binary file
  
* dbdreader checks whether the value of the parameters read are finite, ignoring them if they are not.



Installation (linux)
--------------------

The python module *dbdreader* can be installed from source, using the
standard method to install python code. Note that this method requires
an C-extension to be build. (The actual reading from files is done in
C for speed.) In order to build the extension successfully, you would
need a C-compiler. On Linux, this can be gcc, with supporting
development/header files for python. On Fedora you would do ``sudo dnf
install python3-devel``, or ``sudo apt-get install python3-dev`` on
Ubuntu.

Furthermore, as of version 0.5, which adds support for reading
compressed files, a dependency on the lz4 library is introduced. If
available, the system-wide library will be used (recommended
approach). Alternatively, the lz4.[ch] files from the original source
(https://github.com/lz4/lz4), and included in this package, will be
compiled into the C-extension. To install the system-wide lz4 library
on Fedora you would do ``sudo dnf install lz4-devel lz4-libs``. On
Ubuntu this can be achieved by ``sudo apt-get install liblz4-dev
liblz4-1``.

Alternatively, dbdreader can also be installed from PyPi, using ``pip3
install dbdreader``.


Installation on Windows
-----------------------
If you want to install dbdreader from source, you will need a C
compiler as well to compile the C-extension. Besides the Python
environment you will need to install the Microsoft Visual Studio
Compiler. The community edition will do. When installing MVSC, make sure
you tick the box *python development* during the setup. Once installed
dbdreader can be installed, and the C-extension should be compiled
automatically.


Installiation using pip, for example as in ``py -m pip install
dbdreader`` also requires the C compiler. For Python version 3.9,
however, a wheel is provided, which can be installed adding the option
``--only-binary :all:`` to the pip command: ::

  $ pip install --only-binary :all: dbdreader


Documentation
-------------
Comprehensive documentation is provided at https://dbdreader.readthedocs.io/en/latest/

Quick-start
-----------
For the impatient...

The dbdreader module implements a class DBD() which provides the
machinery to read a single dbd file. The most commonly used methods
are:

* get(parametername)
* get_sync(parametername, \*other_parameternames)

The first method returs a tuple with time and values for requested
parameter. The second method, returns a tuple with time and values of
the first parameter requested, and of all further listed parameters,
all interpolated on the time base of the first parameter.

Mostly, it is not one file that is required to be processed, but a
number of them. This interface is implemented by the MultiDBD
class. Files can either be specified as a list of filenames, or as a
pattern using wildcards.

Examples
^^^^^^^^

To read a single file::

  >>> dbd = DBD("00010010.dbd")
  >>> t, pitch = dbd.get("m_pitch")
  >>> t, hdg, ptch, roll = dbd.get_sync("m_heading", "m_pitch", "m_roll)

Or, doing the same, but using both dbd and ebd files::
  
  >>> dbd = DBD(pattern="00010010.[de]bd")
  >>> t, pitch = dbd.get("m_pitch")
  >>> t, hdg, ptch, roll = dbd.get_sync("m_heading", "m_pitch", "m_roll")
  >>> t, p_ctd, p_nav = dbd.get_sync("sci_water_pressure", "m_water_pressure")

  

Python 2
--------
Python 2.7 is not supported anymore. However, you should be able to
make the code able to run on python2.7 using the *future* package.

* pip install future
* pasteurize dbdreader.

For details see http://python-future.org/pasteurize.html.


.. |PyPI version| image:: https://badgen.net/pypi/v/dbdreader
   :target: https://pypi.org/project/dbdreader
.. |Docs badge| image:: https://readthedocs.org/projects/dbdreader/badge/?version=latest
   :target: https://dbdreader.readthedocs.io/en/latest/
.. |License| image:: https://img.shields.io/badge/License-GPLv3-blue.svg
   :target: https://www.gnu.org/licenses/gpl-3.0

	 
