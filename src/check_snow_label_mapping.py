import h5py
import numpy as np

FILE = (
    r"C:\NUS\FYP\FYP Organized\data\raw"
    r"\2024-05-01 M2 AMMTO Fatigue Blanks 05.hdf5"
)

LAYER = 600
PATCH_SIZE = 24

SAMPLES = {
    "POSITIVE": (1997, 1994),
    "NEGATIVE": (2021, 1994),
}


def get_bounds(start, scale, method):
    a = start * scale
    b = (start + PATCH_SIZE) * scale

    if method == "pilot_round":
        return round(a), round(b)

    if method == "audit_floor_ceil":
        return int(np.floor(a)), int(np.ceil(b))

    if method == "export_floor":
        return int(np.floor(a)), int(np.floor(b))

    raise ValueError("Unknown method")


with h5py.File(FILE, "r") as f:

    camera = f["/slices/part_ids"]
    ct = f["/slices/registered_data/x-ray_ct_data"]
    flaw = f["/slices/registered_data/x-ray_ct_flaw"]

    scale_y = ct.shape[1] / camera.shape[1]
    scale_x = ct.shape[2] / camera.shape[2]

    methods = [
        "pilot_round",
        "audit_floor_ceil",
        "export_floor",
    ]

    for name, (y, x) in SAMPLES.items():

        print(f"\n=== {name} PATCH ===")
        print(f"Camera coordinates: Y={y}, X={x}")

        for method in methods:

            y0, y1 = get_bounds(y, scale_y, method)
            x0, x1 = get_bounds(x, scale_x, method)

            crop = flaw[LAYER, y0:y1, x0:x1]

            count = int(np.count_nonzero(crop))

            print(f"\nMethod: {method}")
            print(f"XCT bounds: Y={y0}:{y1}, X={x0}:{x1}")
            print(f"Flaw-mask pixels: {count}")

print("\nComparison completed.")
print("The original HDF5 file was not modified.")