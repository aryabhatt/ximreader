## ximReader Python package for loading xim files

ximReader is an open-source tool for reading xim files as numpy arrays. It is based on XimReader (https://bitbucket.org/dmoderesearchtools/ximreader/src/master/). 

## Installation

ximReader can installed via pip

`` pip install git+https://github.com/aryabhatt/ximreader.git ``

Alternatively, it can be installed from the source. It is recommended that a virtual environment be used for the installation.


## Usage

    from ximreader import ximReader
    image = ximReader(<full path to xim>)
