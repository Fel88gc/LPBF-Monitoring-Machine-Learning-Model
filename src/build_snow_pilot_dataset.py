import csv
from pathlib import Path

import h5py
import numpy as np


FILE = (
    r"C:\NUS\FYP\FYP Organized\data\raw"
    r"\2024-05-01 M2 AMMTO Fatigue Blanks 05.hdf5"
)

# Small pilot covering multiple specimens and layers.
LAYERS = [540, 560, 580, 600, 620, 638, 640]
PART_IDS = [2, 9, 16, 24, 35, 43, 52, 60]

PATCH_SIZE = 24
MIN_PART_FRACTION = 0.75
MIN_CT_COVERAGE = 0.50

OUTPUT = Path("data/processed")
OUTPUT.mkdir(parents=True, exist_ok=True)

images = []
records = []


with h5py.File(FILE, "r") as f:

    part_ds = f["/slices/part_ids"]

    visible_melt = f["/slices/camera_data/visible/0"]
    visible_recoat = f["/slices/camera_data/visible/1"]
    nir_max = f["/slices/camera_data/nir/1"]

    ct_ds = f["/slices/registered_data/x-ray_ct_data"]
    flaw_ds = f["/slices/registered_data/x-ray_ct_flaw"]

    scale_y = ct_ds.shape[1] / part_ds.shape[1]
    scale_x = ct_ds.shape[2] / part_ds.shape[2]

    for layer in LAYERS:

        parts = part_ds[layer]

        before = len(records)

        for part_id in PART_IDS:

            ys, xs = np.where(parts == part_id)

            if len(xs) == 0:
                continue

            y_min = int(ys.min())
            y_max = int(ys.max())

            x_min = int(xs.min())
            x_max = int(xs.max())

            for y in range(
                y_min,
                y_max - PATCH_SIZE + 2,
                PATCH_SIZE
            ):

                for x in range(
                    x_min,
                    x_max - PATCH_SIZE + 2,
                    PATCH_SIZE
                ):

                    part_patch = parts[
                        y:y + PATCH_SIZE,
                        x:x + PATCH_SIZE
                    ]

                    if part_patch.shape != (
                        PATCH_SIZE,
                        PATCH_SIZE
                    ):
                        continue

                    part_fraction = float(
                        np.mean(part_patch == part_id)
                    )

                    if part_fraction < MIN_PART_FRACTION:
                        continue

                    # Consistent rounded boundaries prevent
                    # adjacent patches from sharing XCT pixels.
                    cy0 = round(y * scale_y)
                    cy1 = round((y + PATCH_SIZE) * scale_y)

                    cx0 = round(x * scale_x)
                    cx1 = round((x + PATCH_SIZE) * scale_x)

                    raw = ct_ds[
                        layer, cy0:cy1, cx0:cx1
                    ]

                    ct_coverage = float(np.mean(raw > 0))

                    if ct_coverage < MIN_CT_COVERAGE:
                        continue

                    flaw = flaw_ds[
                        layer, cy0:cy1, cx0:cx1
                    ]

                    flaw_pixels = int(
                        np.count_nonzero(flaw)
                    )

                    label = int(flaw_pixels > 0)

                    # Read only the selected image patches.
                    v_melt = visible_melt[
                        layer,
                        y:y + PATCH_SIZE,
                        x:x + PATCH_SIZE
                    ].astype(np.float32) / 255.0

                    v_recoat = visible_recoat[
                        layer,
                        y:y + PATCH_SIZE,
                        x:x + PATCH_SIZE
                    ].astype(np.float32) / 255.0

                    thermal = nir_max[
                        layer,
                        y:y + PATCH_SIZE,
                        x:x + PATCH_SIZE
                    ].astype(np.float32) / 65535.0

                    # Shape: (3, 24, 24)
                    image = np.stack(
                        [v_melt, v_recoat, thermal],
                        axis=0
                    )

                    images.append(image)

                    records.append({
                        "layer": layer,
                        "part_id": part_id,
                        "camera_y": y,
                        "camera_x": x,
                        "patch_size": PATCH_SIZE,
                        "part_fraction": round(part_fraction, 4),
                        "ct_coverage": round(ct_coverage, 4),
                        "flaw_pixels": flaw_pixels,
                        "label": label
                    })

        print(
            f"Layer {layer} completed: "
            f"{len(records) - before} patches",
            flush=True
        )


if not records:
    raise RuntimeError("No valid patches were extracted.")


# Convert to machine-learning arrays.
X = np.stack(images).astype(np.float32)

y = np.array(
    [row["label"] for row in records],
    dtype=np.uint8
)

groups = np.array(
    [row["part_id"] for row in records],
    dtype=np.int32
)

layers = np.array(
    [row["layer"] for row in records],
    dtype=np.int32
)


# Save image arrays and labels.
npz_path = OUTPUT / "snow_pilot_patches.npz"

np.savez_compressed(
    npz_path,
    X=X,
    y=y,
    groups=groups,
    layers=layers
)


# Save a CSV for inspection.
csv_path = OUTPUT / "snow_pilot_manifest.csv"

with open(csv_path, "w", newline="", encoding="utf-8") as file:

    writer = csv.DictWriter(
        file,
        fieldnames=list(records[0].keys())
    )

    writer.writeheader()
    writer.writerows(records)


print("\n=== MULTI-SPECIMEN DATASET ===")

print("X shape:", X.shape)
print("y shape:", y.shape)

print("Total patches:", len(y))
print("Positive patches:", int(np.sum(y)))
print("Negative patches:", int(np.sum(y == 0)))

print("\nPer-specimen summary:")

for part_id in sorted(np.unique(groups)):

    mask = groups == part_id

    print(
        f"Part {part_id}: "
        f"{int(np.sum(mask))} patches, "
        f"{int(np.sum(y[mask]))} positive"
    )

print("\nSaved:", npz_path)
print("Saved:", csv_path)
print("Pilot dataset preparation completed.")