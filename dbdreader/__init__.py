import os
from .dbdreader import *

from importlib.metadata import version, PackageNotFoundError
try:
    __version__ = version("dbdreader")
except PackageNotFoundError:
    __version__ = "unknown"
__all__ = ['dbdreader']

EXAMPLE_DATA_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__),
                                                 'data'))
