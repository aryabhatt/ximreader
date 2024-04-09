#include <iostream>
#include <fstream>
#include <algorithm>
#include <tuple>

#include <pybind11/pybind11.h>
#include <pybind11/numpy.h>


namespace py = pybind11;
typedef py::array_t<int, py::array::c_style> np_array_t;

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

    // allocate numpy array 
    np_array_t Image(Width*Height);
    py::buffer_info buf = Image.request();
    int * buffer = (int *) buf.ptr; 

    int LUTsize;
    xim.read((char *) &LUTsize, 4);
    char * LUT = new char[LUTsize];
    xim.read(LUT, LUTsize); 

    // uncompresssed buffer size
    int BufferSize;
    xim.read((char *) &BufferSize, 4);
 
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

    xim.close();
    delete [] LUT;
    return py::make_tuple(header, Image);
}

PYBIND11_MODULE(libxim, m) {
    m.def("ximreader", &ximread);

}
