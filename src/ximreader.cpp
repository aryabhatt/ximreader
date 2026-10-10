#include <algorithm>
#include <cstdint>
#include <fstream>
#include <stdexcept>
#include <string>
#include <tuple>
#include <vector>

#include <pybind11/numpy.h>
#include <pybind11/pybind11.h>

namespace py = pybind11;
typedef py::array_t<int, py::array::c_style> np_array_t;

// Bytes left between the current read position and the end of the file.
static std::int64_t bytes_left(std::ifstream &xim, std::int64_t fileSize) {
    std::streamoff pos = xim.tellg();
    return pos < 0 ? 0 : fileSize - pos;
}

// Parse the histogram + property block that follows the pixel data.
// Returns a dict {name: int | float | str | ndarray}; stops quietly on truncated or
// unknown data.
static py::dict read_properties(std::ifstream &xim, std::int64_t fileSize) {
    py::dict props;
    int nbins = 0;
    if (!xim.read((char *)&nbins, 4)) return props;
    if (nbins < 0 ||
        static_cast<std::int64_t>(nbins) * 4 > bytes_left(xim, fileSize))
        return props;
    xim.seekg(static_cast<std::streamoff>(nbins) * 4, std::ios::cur);

    int nprops = 0;
    if (!xim.read((char *)&nprops, 4)) return props;

    for (int p = 0; p < nprops; p++) {
        int nameLen = 0, type = 0;
        if (!xim.read((char *)&nameLen, 4) || nameLen < 0 ||
            nameLen > bytes_left(xim, fileSize))
            break;
        std::string name(nameLen, '\0');
        xim.read(&name[0], nameLen);
        name.erase(std::find(name.begin(), name.end(), '\0'), name.end());
        if (!xim.read((char *)&type, 4)) break;

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
            if (nbytes < 0 || nbytes > bytes_left(xim, fileSize)) break;
            std::string str(nbytes > 0 ? nbytes : 0, '\0');
            xim.read(&str[0], str.size());
            str.erase(std::find(str.begin(), str.end(), '\0'), str.end());
            value = py::reinterpret_steal<py::object>(
                PyUnicode_DecodeLatin1(str.data(), str.size(), "replace"));
        } else if (type == 4) {
            int nbytes = 0;
            xim.read((char *)&nbytes, 4);
            if (nbytes < 0 || nbytes > bytes_left(xim, fileSize)) break;
            std::vector<double> v(nbytes > 0 ? nbytes / 8 : 0);
            xim.read((char *)v.data(), v.size() * 8);
            value = py::array_t<double>(v.size(), v.data());
        } else if (type == 5) {
            int nbytes = 0;
            xim.read((char *)&nbytes, 4);
            if (nbytes < 0 || nbytes > bytes_left(xim, fileSize)) break;
            std::vector<int> v(nbytes > 0 ? nbytes / 4 : 0);
            xim.read((char *)v.data(), v.size() * 4);
            value = py::array_t<int>(v.size(), v.data());
        } else {
            break; // unknown type: cannot continue parsing
        }
        if (!xim) break;
        props[py::str(name)] = value;
    }
    return props;
}

// Decode one LUT code (0: int8, 1: int16, 2: int32) into a signed difference.
static int read_diff(std::ifstream &xim, unsigned code) {
    switch (code) {
        case 0: {
            signed char v = 0;
            xim.read((char *)&v, 1);
            return v;
        }
        case 1: {
            short v = 0;
            xim.read((char *)&v, 2);
            return v;
        }
        case 2: {
            int v = 0;
            xim.read((char *)&v, 4);
            return v;
        }
        default: throw std::runtime_error("xim: unrecognized LUT code");
    }
}

py::tuple ximread(const char *filename) {
    std::ifstream xim(filename, std::ios::binary | std::ios::in);
    if (!xim)
        throw std::runtime_error(std::string("xim: cannot open file: ") + filename);

    xim.seekg(0, std::ios::end);
    const std::int64_t fileSize = xim.tellg();
    xim.seekg(0, std::ios::beg);

    int unused[2] = {0, 0};
    int FormatVersion = 0, Width = 0, Height = 0;
    int BitsPerPixel = 0, BytesPerPixel = 0, CompressionFlag = 0;

    // discard first 8 chars
    xim.read((char *)unused, 8);
    xim.read((char *)&FormatVersion, 4);
    xim.read((char *)&Width, 4);
    xim.read((char *)&Height, 4);
    xim.read((char *)&BitsPerPixel, 4);
    xim.read((char *)&BytesPerPixel, 4);
    xim.read((char *)&CompressionFlag, 4);
    if (!xim) throw std::runtime_error("xim: truncated header");

    py::dict header;
    header[py::str("version")] = FormatVersion;
    header[py::str("width")] = Width;
    header[py::str("height")] = Height;
    header[py::str("bits_per_pixel")] = BitsPerPixel;
    header[py::str("bytes_per_pixel")] = BytesPerPixel;
    header[py::str("compressed")] = CompressionFlag;

    // terminator frames (no image) carry no pixel data
    if (Width <= 0 || Height <= 0) {
        header[py::str("properties")] = py::dict();
        return py::make_tuple(header, np_array_t(0));
    }
    if (BytesPerPixel != 1 && BytesPerPixel != 2 && BytesPerPixel != 4)
        throw std::runtime_error("xim: unsupported bytes per pixel");

    const std::int64_t nPixels = static_cast<std::int64_t>(Width) * Height;
    if (nPixels > INT32_MAX || nPixels * 4 > std::int64_t(1) << 33)
        throw std::runtime_error("xim: image dimensions too large");
    // every pixel costs at least 1 byte in the file
    if (nPixels > bytes_left(xim, fileSize) * 4)
        throw std::runtime_error("xim: file too small for declared image size");

    np_array_t Image(static_cast<py::ssize_t>(nPixels));
    int *buffer = Image.mutable_data();
    std::fill(buffer, buffer + nPixels, 0);

    // compressed: LUT size, LUT, buffer size; uncompressed: buffer size only
    std::vector<unsigned char> LUT;
    if (CompressionFlag != 0) {
        if (Height < 2)
            throw std::runtime_error("xim: compressed images need at least 2 rows");
        const std::int64_t compressedPixels = nPixels - Width - 1;
        int LUTsize = 0;
        xim.read((char *)&LUTsize, 4);
        if (!xim || LUTsize < 0 || LUTsize > bytes_left(xim, fileSize) ||
            LUTsize < (compressedPixels + 3) / 4)
            throw std::runtime_error("xim: invalid LUT size");
        LUT.resize(LUTsize);
        xim.read((char *)LUT.data(), LUTsize);
    }
    int BufferSize = 0;
    xim.read((char *)&BufferSize, 4);
    if (!xim) throw std::runtime_error("xim: truncated file");

    if (CompressionFlag == 0) {
        for (std::int64_t i = 0; i < nPixels; i++) {
            int pixel = 0;
            xim.read((char *)&pixel, BytesPerPixel);
            buffer[i] = pixel;
        }
    } else {
        // first row + 1 pixel are stored uncompressed
        xim.read((char *)buffer, static_cast<std::streamsize>(Width + 1) * 4);

        // remaining pixels: 2-bit LUT code each, 4 codes per LUT byte, low bits
        // first
        for (std::int64_t k = 0, index = Width + 1; index < nPixels; k++, index++) {
            unsigned code = (LUT[k / 4] >> (2 * (k % 4))) & 3u;
            int diff = read_diff(xim, code);
            buffer[index] = diff + buffer[index - 1] + buffer[index - Width] -
                            buffer[index - Width - 1];
            if (!xim) break;
        }
    }
    if (!xim) throw std::runtime_error("xim: truncated pixel data");

    // compressed pixel data is followed by one more int before the histogram
    if (CompressionFlag != 0) {
        int trailing = 0;
        xim.read((char *)&trailing, 4);
    }
    header[py::str("properties")] = read_properties(xim, fileSize);

    return py::make_tuple(header, Image);
}

PYBIND11_MODULE(libxim, m) { m.def("ximreader", &ximread); }
