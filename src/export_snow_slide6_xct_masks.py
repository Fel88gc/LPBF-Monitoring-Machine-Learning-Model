"""
Extract real XCT flaw masks for Slide 6.

Positive patch: P16, Layer 600, expected 308 flaw-mask pixels
Negative patch: P16, Layer 600, expected 0 flaw-mask pixels

The HDF5 file is opened in READ-ONLY mode.
"""

from pathlib import Path

import h5py
import numpy as np
from PIL import Image


# ============================================================
# 1. FILE PATHS
# ============================================================

PROJECT = Path(r"C:\NUS\FYP\FYP Organized")

HDF5_FILE = (
    PROJECT
    / "data"
    / "raw"
    / "2024-05-01 M2 AMMTO Fatigue Blanks 05.hdf5"
)

OUTPUT_FOLDER = PROJECT / "results" / "snow_slide6_xct_masks"

OUTPUT_FOLDER.mkdir(parents=True, exist_ok=True)


# ============================================================
# 2. DATASET SETTINGS
# ============================================================

LAYER = 600

CAMERA_SIZE = 2844
PATCH_SIZE = 24

RAW_XCT_PATH = "/slices/registered_data/x-ray_ct_data"
FLAW_XCT_PATH = "/slices/registered_data/x-ray_ct_flaw"


# Actual examples from our pilot dataset
# Format: (name, camera_y, camera_x, expected_flaw_pixels)

EXAMPLES = [
    ("positive", 1997, 1994, 308),
    ("negative", 2021, 1994, 0),
]


# ============================================================
# 3. OPEN HDF5 IN READ-ONLY MODE
# ============================================================

print("\n=== SLIDE 6 XCT MASK EXTRACTION ===")

report = []

with h5py.File(HDF5_FILE, "r") as h5:

    raw_dataset = h5[RAW_XCT_PATH]
    flaw_dataset = h5[FLAW_XCT_PATH]

    print("Raw XCT shape:", raw_dataset.shape)
    print("Flaw mask shape:", flaw_dataset.shape)

    scale_y = raw_dataset.shape[1] / CAMERA_SIZE
    scale_x = raw_dataset.shape[2] / CAMERA_SIZE

    print("\nCamera-to-XCT scale:")
    print("Y:", scale_y)
    print("X:", scale_x)

    for name, camera_y, camera_x, expected_pixels in EXAMPLES:

        print(f"\n--- {name.upper()} PATCH ---")

        # Candidate conversion from camera to XCT coordinates
        y0 = int(np.floor(camera_y * scale_y))
        y1 = int(np.floor((camera_y + PATCH_SIZE) * scale_y))

        x0 = int(np.floor(camera_x * scale_x))
        x1 = int(np.floor((camera_x + PATCH_SIZE) * scale_x))

        # Read only a small region, not the entire XCT dataset
        raw_crop = raw_dataset[LAYER, y0:y1, x0:x1]
        flaw_crop = flaw_dataset[LAYER, y0:y1, x0:x1]

        flaw_mask = flaw_crop != 0

        actual_pixels = int(np.count_nonzero(flaw_mask))

        print("Camera coordinates (Y, X):", camera_y, camera_x)
        print("XCT crop shape:", raw_crop.shape)
        print("Expected flaw-mask pixels:", expected_pixels)
        print("Actual flaw-mask pixels:", actual_pixels)

        if actual_pixels == expected_pixels:
            status = "PASS"
        else:
            status = "MISMATCH - NEEDS INVESTIGATION"

        print("Count check:", status)

        # ----------------------------------------------------
        # 4. CREATE BINARY XCT FLAW MASK
        # ----------------------------------------------------

        binary_mask = np.where(
            flaw_mask,
            255,
            0
        ).astype(np.uint8)

        mask_image = Image.fromarray(binary_mask)

        mask_image = mask_image.resize(
            (384, 384),
            Image.Resampling.NEAREST
        )

        mask_path = (
            OUTPUT_FOLDER
            / f"snow_P16_L600_{name}_xct_mask.png"
        )

        mask_image.save(mask_path)

        # ----------------------------------------------------
        # 5. CREATE RAW XCT + FLAW OVERLAY
        # ----------------------------------------------------

        raw_float = raw_crop.astype(np.float32)

        nonzero = raw_float[raw_float > 0]

        if nonzero.size > 0:
            lower, upper = np.percentile(nonzero, [2, 98])
        else:
            lower, upper = 0.0, 1.0

        if upper <= lower:
            upper = lower + 1.0

        normalized = np.clip(
            (raw_float - lower) / (upper - lower),
            0,
            1
        )

        grayscale = (normalized * 235).astype(np.uint8)

        rgb = np.stack(
            [grayscale, grayscale, grayscale],
            axis=-1
        )

        # Highlight actual XCT flaw-mask pixels in pink
        rgb[flaw_mask] = [255, 40, 120]

        overlay_image = Image.fromarray(rgb)

        overlay_image = overlay_image.resize(
            (384, 384),
            Image.Resampling.NEAREST
        )

        overlay_path = (
            OUTPUT_FOLDER
            / f"snow_P16_L600_{name}_xct_overlay.png"
        )

        overlay_image.save(overlay_path)

        print("Saved mask:", mask_path.name)
        print("Saved overlay:", overlay_path.name)

        report.append(
            f"{name.upper()}\n"
            f"Camera Y,X: {camera_y}, {camera_x}\n"
            f"XCT bounds: Y={y0}:{y1}, X={x0}:{x1}\n"
            f"Expected flaw pixels: {expected_pixels}\n"
            f"Actual flaw pixels: {actual_pixels}\n"
            f"Status: {status}\n"
        )


# ============================================================
# 6. SAVE AUDIT REPORT
# ============================================================

report_path = (
    OUTPUT_FOLDER
    / "snow_P16_L600_xct_extraction_audit.txt"
)

report_path.write_text(
    "\n".join(report),
    encoding="utf-8"
)

print("\n===================================")
print("XCT EXTRACTION COMPLETED")
print("===================================")

print("\nResults saved to:")
print(OUTPUT_FOLDER)

print("\nIMPORTANT:")
print("This uses a candidate camera-to-XCT mapping.")
print("The coordinates still require spatial verification.")
print("If either pixel count mismatches, investigate before using the images.")