Installation
------------
This is a standard Python Distutil distribution. To install simply run:

for python2.7

    python setup.py install


for python3.3+

    python3 setup.py install
    
This installs dbdreader system-wide. You need root privileges to do this. If
you don't have root privileges, or you don't wish to install dbdreader system-wide
you can install into a custum directory by adding the option "--prefix=...".

For the extension module to compile you will also need to have gcc and python(3)
development headers installed.

