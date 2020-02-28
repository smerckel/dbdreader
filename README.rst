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
* get_sync(parametername, list_of_other_parameternames)

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

	 
