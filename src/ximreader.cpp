#include <algorithm>
#include <fstream>
#include <iostream>
#include <string>
#include <tuple>
#include <vector>

#include <pybind11/pybind11.h>
#include <pybind11/numpy.h>


namespace py = pybind11;
typedef py::array_t<int, py::array::c_style> np_array_t;

// Parse the histogram + property block that follows the pixel data.
// Returns a dict {name: int | float | str | ndarray}; stops quietly on truncated or unknown data.
static py::dict read_properties(std::ifstream &xim) {
    py::dict props;
    int nbins = 0;
    if (!xim.read((char *)&nbins, 4))
        return props;
    xim.seekg(static_cast<std::streamoff>(nbins) * 4, std::ios::cur);

    int nprops = 0;
    if (!xim.read((char *)&nprops, 4))
        return props;

    for (int p = 0; p < nprops; p++) {
        int nameLen = 0, type = 0;
        if (!xim.read((char *)&nameLen, 4) || nameLen < 0)
            break;
        std::string name(nameLen, '\0');
        xim.read(&name[0], nameLen);
        name.erase(std::find(name.begin(), name.end(), '\0'), name.end());
        if (!xim.read((char *)&type, 4))
            break;

        py::object value;
        if (type == 0) {
            int v = 0;
            xim.read((char *)&v, 4);
            value = py::int_(v);
        } else if (type == 1) {
            double v = 0.0;
            xim.read((char *)&v, 8);
            value = py::float_(v);
        } else if (type == 2) {
            int nbytes = 0;
            xim.read((char *)&nbytes, 4);
            std::string str(nbytes > 0 ? nbytes : 0, '\0');
            xim.read(&str[0], str.size());
            str.erase(std::find(str.begin(), str.end(), '\0'), str.end());
            value = py::reinterpret_steal<py::object>(
                PyUnicode_DecodeLatin1(str.data(), str.size(), "replace"));
        } else if (type == 4) {
            int nbytes = 0;
            xim.read((char *)&nbytes, 4);
            std::vector<double> v(nbytes > 0 ? nbytes / 8 : 0);
            xim.read((char *)v.data(), v.size() * 8);
            value = py::array_t<double>(v.size(), v.data());
        } else if (type == 5) {
            int nbytes = 0;
            xim.read((char *)&nbytes, 4);
            std::vector<int> v(nbytes > 0 ? nbytes / 4 : 0);
            xim.read((char *)v.data(), v.size() * 4);
            value = py::array_t<int>(v.size(), v.data());
        } else {
            break; // unknown type: cannot continue parsing
        }
        if (!xim)
            break;
        props[py::str(name)] = value;
    }
    return props;
}

py::tuple ximread(const char * filename) {
    
    int unused[2];
    int FormatVersion;
    int Width;
    int Height;
    int BitsPerPixel;
    int BytesPerPixel;
    int CompressionFlag;

    std::ifstream xim;
    xim.open(filename, std::ios::binary | std::ios::in);
    
    // discard first 8 chars 
    xim.read((char *) unused, 8);
    xim.read((char *) &FormatVersion, 4);
    xim.read((char *) &Width, 4);
    xim.read((char *) &Height, 4);
    xim.read((char *) &BitsPerPixel, 4);
    xim.read((char *) &BytesPerPixel, 4);
    xim.read((char *) &CompressionFlag, 4);


    py::dict header;
    header[py::str("version")] = FormatVersion;
    header[py::str("width")] = Width;
    header[py::str("height")] = Height;
    header[py::str("bits_per_pixel")] = BitsPerPixel,
    header[py::str("bytes_per_pixel")] = BytesPerPixel,
    header[py::str("compressed")] = CompressionFlag;

    // terminator frames (no image) would divide by zero below
    if (Width <= 0 || Height <= 0 || BytesPerPixel <= 0) {
        header[py::str("properties")] = py::dict();
        return py::make_tuple(header, np_array_t(0));
    }

    // allocate numpy array 
    np_array_t Image(Width*Height);
    py::buffer_info buf = Image.request();
    int * buffer = (int *) buf.ptr;

    // compressed: LUT size, LUT, buffer size; uncompressed: buffer size only
    std::vector<char> LUT;
    if (CompressionFlag != 0) {
        int LUTsize;
        xim.read((char *)&LUTsize, 4);
        LUT.resize(LUTsize);
        xim.read(LUT.data(), LUTsize);
    }
    int BufferSize;
    xim.read((char *) &BufferSize, 4);

    if (CompressionFlag == 0) {
        for (int i = 0; i < Width * Height; i++) {
            int pixel = 0;
            xim.read((char *) &pixel, BytesPerPixel);
            buffer[i] = pixel;
        }
    } else {
        // read first row + 1, (strored uncompressed)
        int word;
        for (int i = 0; i < Width; i++) {
            xim.read((char *) &word, 4);
            buffer[i] = word;
        }
        xim.read((char *) &word, 4);
        buffer[Width] = word;

        // uncompress
        auto compressedPixels = Width * (Height - 1) - 1;
        auto completeBytes = compressedPixels / BytesPerPixel;
        auto partialByte = compressedPixels % BytesPerPixel;

        // start uncompressing one pixel at a time
        char chval;
        short int shint;
        int diff;
        int index = Width + 1;
        unsigned bitflags;
        for (int i = 0; i < completeBytes; i++) {
            bitflags = LUT[i];
            for (int j = 0; j < 4; j++) {

                unsigned mask = (bitflags >> 2) << 2;
                unsigned val = mask ^ bitflags;
                switch (val) {
                    case 0:
                        xim.read(&chval, 1);
                        diff = static_cast<int>(chval);
                        break;
                    case 1:
                        xim.read((char *) &shint, 2);
                        diff = static_cast<int>(shint);
                        break;
                    case 2:
                        xim.read((char *) &diff, 4);
                        break;
                    default:
                        std::cerr << "unrecogonized LUT value" << std::endl;
                        std::exit(1);
                }

                buffer[index] = diff + buffer[index-1] + buffer[index-Width] - buffer[index - Width - 1];
                index += 1;
                bitflags = bitflags >> 2;
            }
        }

        // read the partial byte
        bitflags = LUT[completeBytes];
        for (int i = 0; i < partialByte; i++) {
            unsigned mask = (bitflags >> 2) << 2;
            unsigned val = mask ^ bitflags;
            switch (val) {
                case 0:
                    xim.read(&chval, 1);
                    diff = static_cast<int>(chval);
                    break;
                case 1:
                    xim.read((char *) &shint, 2);
                    diff = static_cast<int>(shint);
                    break;
                case 2:
                    xim.read((char *) &diff, 4);
                    break;
                default:
                    std::cerr << "unrecogonized LUT value" << std::endl;
                    std::exit(1);
            }

            buffer[index] = diff + buffer[index-1] + buffer[index-Width] - buffer[index - Width - 1];
            index += 1;
            bitflags = bitflags >> 2;
        }
    }

    // compressed pixel data is followed by one more int before the histogram
    if (CompressionFlag != 0) {
        int trailing;
        xim.read((char *)&trailing, 4);
    }
    header[py::str("properties")] = read_properties(xim);

    xim.close();
    return py::make_tuple(header, Image);
}

PYBIND11_MODULE(libxim, m) {
    m.def("ximreader", &ximread);

}
