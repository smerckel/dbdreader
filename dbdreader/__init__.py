import os
from .dbdreader import *

__version__ = "0.5.8"
__all__ = ['dbdreader']

EXAMPLE_DATA_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__),
                                                 'data'))
