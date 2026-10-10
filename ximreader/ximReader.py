import numpy as np
from .libxim import ximreader

def ximReader(ximfile, return_header=False):
    """Reads an XIM image file and returns its image data as a NumPy array.

    Parameters:
    ximfile (str): The full path to the XIM image file.
    return_header (bool): If True, also return the header dict (version, width,
        height, bits_per_pixel, bytes_per_pixel, compressed, and 'properties', a
        dict of the image properties such as GantryRtn and KVNormChamber).

    Returns:
    numpy.ndarray: The image data extracted from the XIM file, or
    (numpy.ndarray, dict) if return_header is True.
    """
    header, image = ximreader(ximfile)
    ncols = header['width']
    nrows = header['height']
    image = image.reshape(max(nrows, 0), max(ncols, 0))
    if return_header:
        return image, header
    return image
