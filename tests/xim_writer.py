"""Minimal pure-Python XIM writer used to build synthetic test files."""

import struct

import numpy as np

ID = b"VMAT-XIM"


def _header(width, height, bits, nbytes, compressed, version=100):
    return (
        ID
        + struct.pack("<iiiiii", version, width, height, bits, nbytes, int(compressed))
    )


def _encode_compressed(img):
    """Return (lut_bytes, data_bytes) for an int32 image, height >= 2.

    Diffs are int32 wraparound in the real format; tests keep values small enough
    that int64 arithmetic here and int32 arithmetic in the reader agree.
    """
    h, w = img.shape
    flat = img.astype(np.int64).ravel()
    raw = flat[: w + 1].tolist()
    data = b"".join(struct.pack("<i", v) for v in raw)

    # Predictor works on the flat buffer: for column 0 the "left" pixel is the
    # last pixel of the previous row.
    codes = []
    body = bytearray()
    for i in range(w + 1, h * w):
        pred = flat[i - 1] + flat[i - w] - flat[i - w - 1]
        diff = int(flat[i] - pred)
        if -128 <= diff <= 127:
            codes.append(0)
            body += struct.pack("<b", diff)
        elif -32768 <= diff <= 32767:
            codes.append(1)
            body += struct.pack("<h", diff)
        else:
            codes.append(2)
            body += struct.pack("<i", diff)

    lut = bytearray((len(codes) + 3) // 4)
    for i, code in enumerate(codes):
        lut[i // 4] |= code << (2 * (i % 4))
    return bytes(lut), data + bytes(body)


def _properties(props):
    """props: dict name -> (type, value); type in 0 int, 1 double, 2 str, 4 f64[], 5 i32[]."""
    out = struct.pack("<i", len(props))
    for name, (typ, value) in props.items():
        nm = name.encode("latin-1") + b"\0"
        out += struct.pack("<i", len(nm)) + nm + struct.pack("<i", typ)
        if typ == 0:
            out += struct.pack("<i", value)
        elif typ == 1:
            out += struct.pack("<d", value)
        elif typ == 2:
            s = value.encode("latin-1") + b"\0"
            out += struct.pack("<i", len(s)) + s
        elif typ == 4:
            a = np.asarray(value, dtype="<f8").tobytes()
            out += struct.pack("<i", len(a)) + a
        elif typ == 5:
            a = np.asarray(value, dtype="<i4").tobytes()
            out += struct.pack("<i", len(a)) + a
        else:
            raise ValueError(typ)
    return out


def build_xim(img, compressed=True, bytes_per_pixel=4, props=None, histogram=(1, 2, 3)):
    """Serialize `img` (2-D integer array) to XIM bytes."""
    img = np.asarray(img)
    h, w = img.shape
    if compressed:
        bytes_per_pixel = 4
        lut, body = _encode_compressed(img)
        pix = (
            struct.pack("<i", len(lut))
            + lut
            + struct.pack("<i", len(body))
            + body
            + struct.pack("<i", 0)
        )
    else:
        dt = {1: "<u1", 2: "<u2", 4: "<i4"}[bytes_per_pixel]
        body = img.astype(dt).tobytes()
        pix = struct.pack("<i", len(body)) + body
    hist = struct.pack("<i", len(histogram)) + np.asarray(histogram, "<i4").tobytes()
    return (
        _header(w, h, 8 * bytes_per_pixel, bytes_per_pixel, compressed)
        + pix
        + hist
        + _properties(props or {})
    )


def build_terminator():
    """Frame with no image: 0x0, 0 bytes per pixel, no data, no properties."""
    return _header(0, 0, 0, 0, False)


def write_xim(path, *args, **kwargs):
    with open(path, "wb") as f:
        f.write(build_xim(*args, **kwargs))
