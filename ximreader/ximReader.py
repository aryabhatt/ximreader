import numpy as np
from .libxim import ximreader

def ximReader(ximfile):
    header, image = ximreader(ximfile)
    nrows = header['width']
    ncols = header['height']
    return header, image.reshape(nrows, ncols)

    
