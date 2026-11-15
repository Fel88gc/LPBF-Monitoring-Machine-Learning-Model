import csv
from pathlib import Path

import h5py
import numpy as np


FILE = (
    r"C:\NUS\FYP\FYP Organized\data\raw"
    r"\2024-05-01 M2 AMMTO Fatigue Blanks 05.hdf5"
)

LAYER = 600
PART_ID = 16
PATCH_SIZE = 24

OUTPUT = Path("results")
OUTPUT.mkdir(exist_ok=True)

rows = []


with h5py.File(FILE, "r") as f:

    parts = f["/slices/part_ids"][LAYER]

    raw_ct = f[
        "/slices/registered_data/x-ray_ct_data"
    ]

    flaw_ct = f[
        "/slices/registered_data/x-ray_ct_flaw"
    ]

    ys, xs = np.where(parts == PART_ID)

    if len(xs) == 0:
        raise ValueError("Selected part was not found.")

    scale_y = raw_ct.shape[1] / parts.shape[0]
    scale_x = raw_ct.shape[2] / parts.shape[1]

    y_min = int(ys.min())
    y_max = int(ys.max())

    x_min = int(xs.min())
    x_max = int(xs.max())

    for y in range(y_min, y_max - PATCH_SIZE + 2, PATCH_SIZE):

        for x in range(x_min, x_max - PATCH_SIZE + 2, PATCH_SIZE):

            # Check how much of the patch belongs to P16.
            part_patch = parts[
                y:y + PATCH_SIZE,
                x:x + PATCH_SIZE
            ]

            if part_patch.shape != (PATCH_SIZE, PATCH_SIZE):
                continue

            part_fraction = np.mean(part_patch == PART_ID)

            if part_fraction < 0.75:
                continue

            # Convert camera coordinates to XCT coordinates.
            cy0 = int(np.floor(y * scale_y))
            cy1 = int(np.ceil((y + PATCH_SIZE) * scale_y))

            cx0 = int(np.floor(x * scale_x))
            cx1 = int(np.ceil((x + PATCH_SIZE) * scale_x))

            raw_patch = raw_ct[
                LAYER, cy0:cy1, cx0:cx1
            ]

            flaw_patch = flaw_ct[
                LAYER, cy0:cy1, cx0:cx1
            ]

            # Exclude regions without sufficient XCT content.
            ct_coverage = float(np.mean(raw_patch > 0))

            if ct_coverage < 0.50:
                continue

            flaw_pixels = int(np.count_nonzero(flaw_patch))

            # Provisional binary label:
            # 1 = annotated flaw present
            # 0 = no annotated flaw in this valid region
            label = int(flaw_pixels > 0)

            rows.append({
                "layer": LAYER,
                "part_id": PART_ID,
                "camera_y": y,
                "camera_x": x,
                "patch_size": PATCH_SIZE,
                "part_fraction": round(float(part_fraction), 4),
                "ct_coverage": round(ct_coverage, 4),
                "flaw_pixels": flaw_pixels,
                "label": label
            })


filename = OUTPUT / "snow_P16_layer600_patch_audit.csv"

if rows:

    with open(filename, "w", newline="", encoding="utf-8") as file:

        writer = csv.DictWriter(
            file,
            fieldnames=list(rows[0].keys())
        )

        writer.writeheader()
        writer.writerows(rows)

    positive = sum(row["label"] == 1 for row in rows)
    negative = sum(row["label"] == 0 for row in rows)

    print("\n=== FIRST ML PATCH AUDIT ===")
    print("Total valid patches:", len(rows))
    print("Positive patches:", positive)
    print("Negative patches:", negative)
    print("Positive percentage:", round(100 * positive / len(rows), 2), "%")
    print("Saved:", filename)

else:
    print("No valid patches found. Check the coverage thresholds.")