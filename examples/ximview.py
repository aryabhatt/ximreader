import sys
import pathlib
import glob
import os
import numpy as np
import pyqtgraph as pg
from pyqtgraph.Qt import QtGui  

from ximreader import ximReader


def loadXimStack(pth, token=None):
    """Load a stack of XIM files from a directory.

    Args:
        pth (pathlib.Path): Path to the directory containing the XIM files.
        token (str): Token to search for in the XIM file names.

    Returns:
        np.ndarray: A 3D numpy array containing the stack of images.
    """
    ximfiles = glob.glob(pth.joinpath(f"*{token}*.xim").as_posix())
    stack = []
    for ximfile in ximfiles:
        try:
            img = ximReader(ximfile)
            if img.size > 0:
                stack.append(img)
        except Exception as e:
            print("Error reading {ximfile}: {e}")
    return np.array(stack)


def main(pth):

    # Create a Qt application
    app = pg.mkQApp()

    # Load XIM stack
    data = loadXimStack(pth, token="Proj")

    # Reorder the data so that axis or rotation is along z-axis
    data = data.transpose(0, 2, 1)

    # Create an image view widget
    pg.setConfigOptions(antialias=True)
    imv = pg.ImageView()

    # Set the image data
    imv.setImage(data)

    # Show the image view widget
    imv.show()
    app.exec()


if __name__ == '__main__':

    # Check if the path is provided
    if len(sys.argv) < 2:
        print("Usage: python ximviewer.py <path>")
        sys.exit(1)

    # Get the path from the command line
    p = sys.argv[1]
    pth = pathlib.Path(p)
    # check if the path exists
    if not pth.exists():
        print(f"Path {pth} does not exist")
        sys.exit(1)
    main(pth)
