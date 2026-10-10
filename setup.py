from pybind11.setup_helpers import Pybind11Extension, build_ext
from setuptools import setup
 
ext_modules = [
    Pybind11Extension(
        "ximreader.libxim",
        ["src/ximreader.cpp"],
        cxx_std=17,  # emits -std=c++17 on GCC/Clang and /std:c++17 on MSVC
    ),
]
 
setup(
    ext_modules=ext_modules,
    cmdclass={"build_ext": build_ext},
)
