import os
import struct

import numpy as np
import pytest

from ximreader import ximReader
from xim_writer import build_terminator, build_xim, write_xim


def rand_image(h, w, seed=0, lo=-5000, hi=60000):
    return np.random.default_rng(seed).integers(lo, hi, size=(h, w), dtype=np.int32)


def smooth_image(h, w):
    y, x = np.mgrid[0:h, 0:w]
    return (1000 + 3 * x + 2 * y).astype(np.int32)


@pytest.fixture
def xim_path(tmp_path):
    def make(data, name="a.xim"):
        p = tmp_path / name
        p.write_bytes(data)
        return str(p)

    return make


# --- round trips -----------------------------------------------------------


@pytest.mark.parametrize("maker", [rand_image, lambda h, w: smooth_image(h, w)])
def test_compressed_round_trip(xim_path, maker):
    img = maker(17, 23)
    got, hdr = ximReader(xim_path(build_xim(img, compressed=True)), return_header=True)
    np.testing.assert_array_equal(got, img)
    assert (hdr["width"], hdr["height"]) == (23, 17)
    assert hdr["compressed"] == 1


def test_compressed_forces_all_code_sizes(xim_path):
    img = np.zeros((6, 9), dtype=np.int32)
    img[2, 3] = 100000  # 4-byte diff
    img[3, 4] = -90000
    img[4, 1] = 20000  # 2-byte diff
    img[5, 5] = -100  # 1-byte diff
    np.testing.assert_array_equal(ximReader(xim_path(build_xim(img))), img)


@pytest.mark.parametrize("bpp", [1, 2, 4])
def test_uncompressed_round_trip(xim_path, bpp):
    hi = {1: 255, 2: 65535, 4: 2**31 - 1}[bpp]
    img = rand_image(11, 13, lo=0, hi=hi)
    got, hdr = ximReader(
        xim_path(build_xim(img, compressed=False, bytes_per_pixel=bpp)),
        return_header=True,
    )
    np.testing.assert_array_equal(got, img)
    assert hdr["compressed"] == 0
    assert hdr["bytes_per_pixel"] == bpp


@pytest.mark.parametrize("shape", [(2, 1), (7, 1), (2, 5), (3, 2), (2, 2)])
def test_odd_shapes_compressed(xim_path, shape):
    img = rand_image(*shape)
    np.testing.assert_array_equal(ximReader(xim_path(build_xim(img))), img)


@pytest.mark.parametrize("shape", [(1, 8), (8, 1), (1, 1)])
def test_odd_shapes_uncompressed(xim_path, shape):
    img = rand_image(*shape, lo=0, hi=1000)
    got = ximReader(xim_path(build_xim(img, compressed=False)))
    np.testing.assert_array_equal(got, img)


# --- return type -----------------------------------------------------------


def test_default_returns_array_only(xim_path):
    out = ximReader(xim_path(build_xim(rand_image(4, 6))))
    assert isinstance(out, np.ndarray)
    assert out.shape == (4, 6)
    assert out.dtype == np.int32


def test_return_header_tuple(xim_path):
    out = ximReader(xim_path(build_xim(rand_image(4, 6))), return_header=True)
    assert isinstance(out, tuple) and len(out) == 2
    assert set(out[1]) >= {
        "version", "width", "height", "bits_per_pixel",
        "bytes_per_pixel", "compressed", "properties",
    }  # fmt: skip


# --- properties ------------------------------------------------------------


def test_properties_all_types(xim_path):
    props = {
        "GantryRtn": (1, 180.956456086566),
        "KVNormChamber": (0, 1342685),
        "Label": (2, "hello"),
        "Doubles": (4, [1.5, -2.5, 3.25]),
        "Ints": (5, [1, -2, 3, 4]),
    }
    _, hdr = ximReader(xim_path(build_xim(rand_image(3, 3), props=props)), return_header=True)
    p = hdr["properties"]
    assert p["GantryRtn"] == pytest.approx(180.956456086566)
    assert p["KVNormChamber"] == 1342685
    assert p["Label"] == "hello"
    np.testing.assert_array_equal(p["Doubles"], [1.5, -2.5, 3.25])
    np.testing.assert_array_equal(p["Ints"], [1, -2, 3, 4])
    assert list(p) == list(props)


def test_properties_empty(xim_path):
    _, hdr = ximReader(xim_path(build_xim(rand_image(3, 3))), return_header=True)
    assert hdr["properties"] == {}


def test_properties_on_uncompressed(xim_path):
    data = build_xim(rand_image(3, 3, lo=0, hi=200), compressed=False,
                     bytes_per_pixel=2, props={"A": (0, 7)})  # fmt: skip
    _, hdr = ximReader(xim_path(data), return_header=True)
    assert hdr["properties"] == {"A": 7}


def test_properties_truncated_returns_parsed(xim_path):
    data = build_xim(rand_image(3, 3), props={"A": (0, 7), "B": (1, 2.0), "C": (2, "xyz")})
    for cut in range(1, 30):
        _, hdr = ximReader(xim_path(data[:-cut]), return_header=True)
        assert set(hdr["properties"]) <= {"A", "B", "C"}


def test_properties_unknown_type_stops(xim_path):
    data = bytearray(build_xim(rand_image(3, 3), props={"A": (0, 7)}))
    # patch the type field of the only property (last 4 + 4 bytes are type, value)
    data[-8:-4] = struct.pack("<i", 9)
    _, hdr = ximReader(xim_path(bytes(data)), return_header=True)
    assert hdr["properties"] == {}


# --- terminator frame ------------------------------------------------------


def test_terminator_frame(xim_path):
    img, hdr = ximReader(xim_path(build_terminator()), return_header=True)
    assert img.size == 0
    assert hdr["properties"] == {}


# --- failure modes (need the hardening in src/ximreader.cpp) ---------------


def test_missing_file(tmp_path):
    with pytest.raises(RuntimeError):
        ximReader(str(tmp_path / "nope.xim"))


def test_empty_file(xim_path):
    with pytest.raises(RuntimeError):
        ximReader(xim_path(b""))


def test_short_header(xim_path):
    with pytest.raises(RuntimeError):
        ximReader(xim_path(build_xim(rand_image(3, 3))[:20]))


@pytest.mark.parametrize("compressed", [True, False])
def test_truncated_pixel_data(xim_path, compressed):
    data = build_xim(rand_image(8, 8, lo=0, hi=60000), compressed=compressed, bytes_per_pixel=4)
    with pytest.raises(RuntimeError):
        ximReader(xim_path(data[:80]))


def test_unknown_lut_code(xim_path):
    data = bytearray(build_xim(smooth_image(4, 4)))
    lut_size = struct.unpack_from("<i", data, 32)[0]
    assert lut_size >= 1
    data[36] |= 0b11  # code 3 is invalid
    with pytest.raises(RuntimeError):
        ximReader(xim_path(bytes(data)))


@pytest.mark.parametrize("bpp", [0, 3, 5, 8, 1000, -4])
def test_bad_bytes_per_pixel(xim_path, bpp):
    data = bytearray(build_xim(rand_image(4, 4, lo=0, hi=200), compressed=False, bytes_per_pixel=1))
    struct.pack_into("<i", data, 24, bpp)
    with pytest.raises(RuntimeError):
        ximReader(xim_path(bytes(data)))


def test_huge_dimensions(xim_path):
    data = bytearray(build_xim(rand_image(4, 4, lo=0, hi=200), compressed=False, bytes_per_pixel=1))
    struct.pack_into("<ii", data, 12, 2**30, 2**30)
    with pytest.raises(RuntimeError):
        ximReader(xim_path(bytes(data)))


def test_height_one_compressed(xim_path):
    data = bytearray(build_xim(rand_image(2, 5)))
    struct.pack_into("<i", data, 16, 1)  # claim height 1
    with pytest.raises(RuntimeError):
        ximReader(xim_path(bytes(data)))


def test_short_lut(xim_path):
    data = bytearray(build_xim(rand_image(8, 8)))
    struct.pack_into("<i", data, 32, 1)  # LUT size far too small
    with pytest.raises(RuntimeError):
        ximReader(xim_path(bytes(data)))


def test_negative_lut_size(xim_path):
    data = bytearray(build_xim(rand_image(4, 4)))
    struct.pack_into("<i", data, 32, -1)
    with pytest.raises(RuntimeError):
        ximReader(xim_path(bytes(data)))


def test_huge_property_lengths_do_not_allocate(xim_path):
    data = bytearray(build_xim(rand_image(3, 3), props={"A": (2, "xyz")}))
    # string property: [..., nbytes(4), "xyz\0"] at the end
    struct.pack_into("<i", data, len(data) - 8, 2**31 - 1)
    _, hdr = ximReader(xim_path(bytes(data)), return_header=True)
    assert "A" not in hdr["properties"]


# --- optional real-data tests ---------------------------------------------

REAL = os.environ.get("XIM_TEST_DIR")


@pytest.mark.skipif(not REAL, reason="XIM_TEST_DIR not set")
def test_real_projection():
    img, hdr = ximReader(
        os.path.join(REAL, "Acquisitions/888145490/Proj_00450.xim"), return_header=True
    )
    assert hdr["properties"]["GantryRtn"] == pytest.approx(180.956456086566)
    assert hdr["properties"]["KVNormChamber"] == 1342685
    assert list(img[384, [10, 300, 700]]) == [23663, 2266, 210]


@pytest.mark.skipif(not REAL, reason="XIM_TEST_DIR not set")
def test_real_terminator_frame():
    acq = os.path.join(REAL, "Acquisitions/888145490")
    last = sorted(f for f in os.listdir(acq) if f.startswith("Proj_") and f.endswith(".xim"))[-1]
    img, hdr = ximReader(os.path.join(acq, last), return_header=True)
    assert img.shape == (0, 0)
    assert hdr["properties"] == {}


@pytest.mark.skipif(not REAL, reason="XIM_TEST_DIR not set")
def test_real_defect_map():
    img, hdr = ximReader(
        os.path.join(REAL, "Calibrations/DETECTOR/Current/DefectMap.xim"), return_header=True
    )
    assert hdr["compressed"] == 0
    assert np.count_nonzero(img) == 7857
    assert len(hdr["properties"]) == 143
