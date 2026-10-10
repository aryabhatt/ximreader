# ximreader plan: tests, then use GantryRtn / KVNormChamber in cbct

Status: `ximReader(path, return_header=True)` returns `(image, header)`; `header["properties"]`
holds all XIM properties (GantryRtn, KVNormChamber, ...). The uncompressed-read bug and the
terminator-frame crash are fixed. None of this has automated tests yet; it was checked by hand
against TIGRE's XIM reader on a TrueBeam scan (7 files, images and properties identical).

## Part A: tests in this repo

### A1. Test layout
- `tests/` with pytest. Remove or replace the stale `test/test.py` (expects `h, a = ximReader(...)`).
- `tests/xim_writer.py`: small pure-Python XIM *writer* used by the tests, so no real (possibly
  patient) data is committed.
  - header: 8-byte id, version, width, height, bits/pixel, bytes/pixel, compression flag
  - uncompressed: `int buffer_size`, raw pixels (1/2/4 bytes per pixel)
  - compressed: `int lut_size`, LUT (2 bits per pixel: 0 -> 1 byte, 1 -> 2 bytes, 2 -> 4 bytes),
    `int buffer_size`, first row + first pixel of row 2 stored raw as int32, remaining pixels as
    diffs vs `left + up - upleft`, then one trailing int
  - tail: histogram (`int nbins`, ints), `int nprops`, properties of type 0 int, 1 double,
    2 string, 4 double array, 5 int array
- Optional real-data tests, skipped unless `XIM_TEST_DIR` is set (e.g. the Data03 scan): compare
  to known values:
  - `Acquisitions/888145490/Proj_00450.xim`: `GantryRtn = 180.956456086566`,
    `KVNormChamber = 1342685`, `img[384, [10, 300, 700]] == [23663, 2266, 210]`
  - `Calibrations/DETECTOR/Current/DefectMap.xim`: uncompressed, 7857 nonzero pixels, 143 properties
  - last `Proj_*.xim` of an acquisition: terminator frame, returns `(0, 0)` image

### A2. Test cases
1. Round trip, compressed: random int32 image (incl. negative diffs, large jumps forcing 4-byte
   codes), image equals input, header fields correct.
2. Round trip, uncompressed, bytes_per_pixel in {1, 2, 4}.
3. Properties: one of each type 0/1/2/4/5, names with trailing NULs, empty property block.
4. `return_header=False` (default) returns only an ndarray, shape `(height, width)`, dtype int32.
5. Terminator frame (0x0, 0 bytes/pixel): empty image, `properties == {}`, no crash.
6. Odd shapes: 1xN, Nx1, width == 1, so the compressed branch bounds are exercised.
7. Failure modes (currently undefined, see A3): missing file, truncated pixel data, truncated
   property block (must return what was parsed, not hang), unknown LUT code, header with
   `bytes_per_pixel` outside {1, 2, 4}, `LUTsize` too short, corrupt `nameLen` / `nbytes` /
   `nbins` requesting huge allocations.
8. Height == 1 compressed image: must raise or return a defined result, never write past the buffer.
9. Sign handling: uncompressed 1/2-byte pixels are zero-extended (unsigned detector data) while
   compressed diffs are sign-extended; the writer and the reader must agree on this on purpose.

These failure-mode tests (7, 8) fail until A3 lands. Develop them on the same feature branch as A3
(see A6), not on `devel` beforehand.

### A3. Code changes the tests will force
- Missing/unreadable file: `std::ifstream` failure is not checked, so a bad path reads garbage.
  Throw `std::runtime_error` (surfaces as Python `RuntimeError`).
- Header validation, directly after the header reads and before the terminator check at
  `ximreader.cpp:109` (Width/Height/etc. are uninitialised if the file is missing or short):
  check stream state; require `BytesPerPixel` in {1, 2, 4} (larger values overflow the 4-byte
  `pixel` in the uncompressed read); compute `Width * Height` in 64 bits and reject overflow.
- Unknown LUT code calls `std::exit(1)`, which kills the interpreter. Throw instead.
- Truncated input: check stream state after pixel reads and raise.
- Compressed branch:
  - `Height == 1` writes `buffer[Width]` one past the end and makes `compressedPixels` -1; reject
    or special-case it.
  - 4 pixels per LUT byte is hard-coded (`>> 2` loop) but `completeBytes`/`partialByte` divide by
    `BytesPerPixel`; only correct when it is 4. Either enforce 4 for compressed files or divide
    by 4, and test with a header claiming 1 or 2.
  - `LUTsize` must be >= `ceil(compressedPixels / 4)` (and non-negative) or `LUT[i]` reads out of
    bounds / `resize` throws `length_error`.
- Properties block: `nbins`, `nameLen`, `nbytes` come straight from the file and size allocations
  or seeks. Cap them against the remaining file size and stop parsing (return what was parsed).
- Cosmetic: lines 104-105 end in `,` instead of `;` (comma operator); fix while editing.
- pybind11 compatibility: the original code returned an all-zero image when built against
  system pybind11 2.11.1 (fine with 3.1.0). Find the cause (suspect `np_array_t(Width*Height)` +
  `request()`; build an explicit `py::array_t<int>({Height, Width})` and write through
  `mutable_data()`), then either fix it or raise the `pybind11>=` floor in `pyproject.toml`
  (currently `>=2.6`). Independent of the outcome, 2.6 cannot build on Python >= 3.10
  (`requires-python`), so raise the floor anyway.

### A4. CI
- `.github/workflows/test.yml`: install `pytest`, run `pytest tests/` after `pip install -e .`
  (currently it only imports the package).
- Triggers currently list only `main`/`master`; add `devel` so the devel-then-master procedure
  gets CI before the merge to master.
- Add one matrix entry with the oldest supported pybind11 to catch the zero-image problem. Pinning
  via `pip install pybind11==X` is not enough: build isolation installs whatever `pyproject.toml`
  requests. Install the pin, then `pip install --no-build-isolation -e .` (with setuptools,
  setuptools-scm and wheel preinstalled).

### A5. Housekeeping
- `test/Proj_00007.xim` (1 MB, untracked) is real data: do not commit; use the synthetic writer.
- Add a `.gitignore` (`build/`, `*.egg-info/`, `__pycache__/`, `test/*.xim`, `*.xim`) so a broad
  `git add` cannot pick up real data or build output.
- `setup.cfg` is untracked and appears empty: delete it, or document what it is for.
- Document `return_header` and the properties dict in `README.md` (it currently shows only
  `image = ximReader(...)`).
- Tag a release (setuptools-scm takes the version from the tag) once A1-A4 pass.

### A6. Procedure (per CLAUDE.md)
Work on `devel` for small steps (A5 housekeeping, `.gitignore`, README). Use one feature branch
for A1-A3 together: the writer, the round-trip tests and the failure-mode tests need the A3 code
changes to pass, so they land as one unit. Run pytest; merge to `devel`, run again, then merge to
`master` and delete the feature branch. A4 (CI) goes in after A1-A3 are merged to `devel`.

## Part B: return to GantryRtn / KVNormChamber in cbct (/home/dkumar/astra)

Why: the native pipeline saturates because it subtracts the dark offset from frames that are
already offset-corrected, and it estimates the dose scale from edge columns that are not air for
this patient. TIGRE instead divides each frame by its own `KVNormChamber` and uses the frame's
`GantryRtn`. Reference output (no saturation, matches ASTRA FDK after the half-fan fix):
`tigre_sino.npy` / `tigre_ang.npy` in the session scratchpad.

1. Install the updated ximreader into the environment `cbct` imports (needs pybind11 available to
   the build). Do a clean reinstall (remove stale `build/` and `*.egg-info/` first), then print
   `ximreader.__file__` to confirm which copy is imported. Confirm
   `ximReader(..., return_header=True)` works there.
2. `cbct/calibration.py`: for each flat `FilterBowtie_{CC,CW}_*.xim` read `GantryRtn` and
   `KVNormChamber`; store sorted by angle (mod 360), image divided by its `KVNormChamber`.
   Drop the dark/gain correction of flats (no offset subtraction or gain scaling; the only
   normalisation is the per-frame `KVNormChamber` division, applied to flats here and to each
   projection in step 3, so the ratio is consistent).
   Rebuild `bad_coords` from the corrected `DefectMap` (was 2836 wrong pixels, now 7857).
3. `cbct/projections.py`:
   - per frame read `GantryRtn`, `KVNormChamber`; interpolate the flat linearly in angle
     (periodic, as TIGRE `interp_proj`) instead of picking a sector; remove the edge-column
     `dose_scale`
   - `ratio = (img / kv) / flat_interp`, then floor it at a small epsilon (e.g. 1e-6) so
     `-log(ratio)` is finite; no dark/gain step. Do NOT clamp `ratio >= 1`: ratio is below 1
     wherever the patient attenuates, so that would zero the sinogram. If TIGRE also caps at
     1 (non-negative line integrals), check its behaviour before copying; capping air noise at 1
     biases the air region.
   - skip terminator frames from the returned empty array (remove the struct pre-check)
4. Angles: use the frame's `GantryRtn`. The XML angles are about `180 - GantryRtn`, while all
   validated TIGRE runs used `GantryRtn` with the detector columns un-flipped. Decide the
   convention objectively in step 5a, not by trial reconstruction: for each candidate pair
   (angle = `GantryRtn` or `180 - GantryRtn`, columns flipped or not), compare against
   `tigre_sino.npy` at matching angles and keep the pair with the lowest difference.
5. Validate in this order, stopping at the first failure:
   a. native sinogram vs `tigre_sino.npy` frame by frame (same angle): mean/std of the
      difference in air and body regions (expect small, TIGRE additionally has detector + FASKS
      scatter correction and a (1, 9) column median filter). This also settles the angle and
      flip convention from step 4.
   b. `python -m cbct recon recon.toml` with the half-fan `_halffan_prepare` already in
      `cbct/reconstruct.py`: no saturation (< 0.1% of values at the floor), no ring, centre/plateau
      ratio near 1.1, soft tissue about 0.017 /mm. Record the ROIs (slice index, pixel boxes)
      these two numbers come from in the plan or in `recon.toml` so the check is repeatable.
   c. correlation with TIGRE FDK on the same slice (target > 0.95)
6. Then, optionally: column median filter (1, 9), detector point scatter and FASKS scatter
   (Sun and Star-Lack 2010) to remove the remaining central brightening; Hann filter (paper uses
   cutoff 0.4 for Varian); HU conversion `HU = mu * 216 - 1024`.

Open items carried over: z-flip check, empirical frame-correlation check of angle/flip
convention, bright inner disk (~150 px radius) and vertical streak near column 265 present in
both TIGRE and ASTRA reconstructions (data/preprocessing, not the reconstruction method).
