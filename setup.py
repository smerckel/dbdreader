import setuptools

with open("dbdreader/__init__.py", "r") as fh:
    VERSION = fh.readline().strip().split("=")[1].replace('"', '')

with open("README.rst", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="dbdreader",
    version=VERSION,
    author="Lucas Merckelbach",
    author_email="lucas.merckelbach@hzg.de",
    description="A python module to access binary data files generated by Teledyne WebbResearch gliders",
    long_description=long_description,
    long_description_content_type="text/x-rst",
    url='https://dbdreader.readthedocs.io/en/latest/',
    packages=['dbdreader'],
    py_modules=[],
    entry_points = {'console_scripts':[],
                    'gui_scripts':[]
    },
    scripts = ['dbdrename.py','cac_gen.py'],
    install_requires = 'numpy'.split(),
    ext_modules = [
           setuptools.Extension("_dbdreader",
                                ["extension/py_dbdreader.c",
                                 "extension/dbdreader.c",
                                 "extension/decompress.c"],
                                libraries = ['lz4'],
                                include_dirs=['extension/include'])
    ],
    classifiers=[
        "Programming Language :: Python :: 3",
        'Intended Audience :: Science/Research',
        'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
        "Operating System :: POSIX",
    ],
)
