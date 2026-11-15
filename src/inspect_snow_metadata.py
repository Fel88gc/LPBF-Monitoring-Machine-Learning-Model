from pathlib import Path

import h5py
import numpy as np


FILE = (
    r"C:\NUS\FYP\FYP Organized\data\raw"
    r"\2024-05-01 M2 AMMTO Fatigue Blanks 05.hdf5"
)

OUTPUT = Path("results")
OUTPUT.mkdir(exist_ok=True)

PATHS = [
    "/",
    "/slices",
    "/slices/camera_data",
    "/slices/camera_data/visible",
    "/slices/camera_data/visible/0",
    "/slices/camera_data/nir/0",
    "/slices/registered_data",
    "/slices/registered_data/x-ray_ct_data",
    "/slices/registered_data/x-ray_ct_flaw",
    "/slices/part_ids",
    "/slices/sample_ids",
]

lines = []


def log(message):
    lines.append(str(message))


def describe(value):

    if isinstance(value, np.ndarray):
        preview = value.flat[:10].tolist()

        return (
            f"Array | shape={value.shape} | "
            f"dtype={value.dtype} | preview={preview}"
        )

    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")[:1000]

    return repr(value)[:1000]


with h5py.File(FILE, "r") as f:

    for path in PATHS:

        log("\n" + "=" * 70)
        log("OBJECT: " + path)
        log("=" * 70)

        obj = f[path]

        if isinstance(obj, h5py.Dataset):
            log("Shape: " + str(obj.shape))
            log("Dtype: " + str(obj.dtype))

        keys = list(obj.attrs.keys())

        log("Number of attributes: " + str(len(keys)))

        if not keys:
            log("No attributes found.")

        for key in sorted(keys):

            value = obj.attrs[key]

            log(f"\nAttribute: {key}")
            log(f"Value: {describe(value)}")


filename = OUTPUT / "snow_registration_metadata.txt"

filename.write_text(
    "\n".join(lines),
    encoding="utf-8"
)

print("\nMetadata inspection completed.")
print("Saved to:", filename)