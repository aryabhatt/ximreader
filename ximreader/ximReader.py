import numpy as np
from .libxim import ximreader

def ximReader(ximfile):
    """Reads an XIM image file and returns its image data as a NumPy array.

    Parameters:
    ximfile (str): The full path to the XIM image file.

    Returns:
    numpy.ndarray: The image data extracted from the XIM file.
    """
    header, image = ximreader(ximfile)
    ncols = header['width']
    nrows = header['height']
    return image.reshape(nrows, ncols)

