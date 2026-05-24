from os import path
from setuptools import setup, Extension
from setuptools.command.build_ext import build_ext
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


class BuildExt(build_ext):
    """A custom build extension for adding pybind11 include dirs."""
    def build_extensions(self):
        import pybind11
        # Get version info - handle both tuple and Version object
        version_info = pybind11.version_info
        if hasattr(version_info, '__getitem__'):
            major, minor = version_info[0], version_info[1]
        else:
            # Version object with major, minor attributes
            major = getattr(version_info, 'major', 0)
            minor = getattr(version_info, 'minor', 0)
        
        if (major, minor) < min_pybind11_version:
            raise Exception(
                "ximReader requires pybind11 "
                "{0}.{1} or higher, found {2}.{3}".format(
                    *min_pybind11_version, major, minor))
        
        # Add pybind11 include directory to all extensions
        for ext in self.extensions:
            ext.include_dirs.append(pybind11.get_include())
        
        build_ext.build_extensions(self)


extensions = []
ext = Extension(
    "ximreader.libxim",
    sources = ['src/ximreader.cpp'],
    include_dirs=[],
    extra_compile_args = ['-std=c++17']
)
extensions.append(ext)

setup(
    name='ximreader',
    version= "1.0.2",
    description="Python Extension for reading XIM files",
    long_description=readme,
    long_description_content_type='text/markdown',
    author="Dinesh Kumar",
    author_email="dkumar@lbl.gov",
    packages=[ "ximreader" ],
    setup_requires=['pybind11>=2.3'],
    install_requires=requirements,
    license="BSD (2-clause)",
    classifiers=[
        'Development Status :: 4 - Beta',
        'Natural Language :: English',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Programming Language :: Python :: 3.12',
        'License :: OSI Approved :: BSD License',
        'Operating System :: OS Independent',
    ],
    ext_modules=extensions,
    cmdclass={'build_ext': BuildExt}
)
