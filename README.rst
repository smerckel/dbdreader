|PyPI version| |Docs badge| |License|

DBDREADER
=========

Change log
----------
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


Synopsis
--------
Slocum ocean gliders are autonomous underwater vehicles, used for
making oceanographic measurements. The data that these devices and
their sensors collect, are stored in binary data files. The python
module *dbdreader* provides the utilities to extract the data from the
binary files, so that they can be further analysed.

Installation
------------
The python module *dbdreader* can be installed from source, using the
standard method to install python code. Note that this method requires
an C-extension to be build. (The actual reading from files is done in
C for speed.) In order to build the extension successfully, you would
need a C-compiler. On Linux, this can be gcc, with supporting
development/header files for python. On Fedora you would do ``sudo dnf
install python3-devel``.

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

	 
