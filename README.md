## ximReader Python package for loading xim files

ximReader is an open-source tool for reading xim files as NumPy array. It is based on XimReader (https://bitbucket.org/dmoderesearchtools/ximreader/src/master/). 

## Installation

ximReader can be installed via pip

    pip install git+https://github.com/aryabhatt/ximreader.git

Alternatively, it can be installed from the source. It is recommended that a virtual environment be used for the source installation.


## Usage

    from ximreader import ximReader

    def awesone_function(..., ximfilename, ...)
        ...

        image = ximReader(ximfilename)

        ...
