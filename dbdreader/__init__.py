__version__="0.5.6"

__all__ = ['dbdreader']

import os

from .dbdreader import *

EXAMPLE_DATA_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__),
                                                 'data'))
