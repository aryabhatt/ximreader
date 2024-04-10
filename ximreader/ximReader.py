import numpy as np
from .libxim import ximreader

def ximReader(ximfile):
    """ Read xim image file.

    Parameters:
    ximfile (str) -- full path to xim image file


    Returns:
        numpy.ndarray: Image data
    """
    header, image = ximreader(ximfile)
    nrows = header['width']
    ncols = header['height']
    return image.reshape(nrows, ncols)

