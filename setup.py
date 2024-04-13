from os import path
from setuptools import setup, Extension
import sys


min_pybind11_version = (2, 3)
min_version = (3, 10)
if sys.version_info < min_version:
    error = """
    Python {2}.{3} and above is required. Check your Python version like so:

    python3 --version

    This may be due to an out-of-date pip. Make sure you have pip >= 9.0.1.
    Upgrade pip like so:

    pip install --upgrade pip
    """.format(*(sys.version_info[:2] + min_version))
    sys.exit(error)

root = path.abspath(path.dirname(__file__))
with open(path.join(root, "README.md"), encoding='utf-8') as fp:
    readme = fp.read()

with open(path.join(root, 'requirements.txt')) as requirements_file:
    # Parse requirements.txt, ignoring any commented-out lines.
    requirements = [line for line in requirements_file.read().splitlines()
                    if not line.startswith('#')]

def get_pybind11_headers():
    import pybind11
    major, minor, _ = pybind11.version_info
    if major < 2 or minor < 3:
        raise Exception(
            "ximReader requires pybind11 "
            "{0}.{1} or higher".format(*min_pybind11_version))
    return pybind11.get_include()

extensions = []
ext = Extension(
    "ximreader.libxim",
    sources = ['src/ximreader.cpp'],
    include_dirs=[get_pybind11_headers()],
    extra_compile_args = ['-std=c++17']
)
extensions.append(ext)

setup(
    name='ximreader',
    version= "1.0.1",
    description="Python Extension for reading XIM files",
    long_description=readme,
    author="Dinesh Kumar",
    author_email="dkumar@lbl.gov",
    packages=[ "ximreader" ],
    install_requires=requirements,
    license="BSD (2-clause)",
    classifiers=[
        'Development Status :: beta',
        'Natural Language :: English',
        'Programming Language :: Python :: 3',
    ],
    ext_modules=extensions
)
