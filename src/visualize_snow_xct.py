from pathlib import Path

import h5py
import numpy as np
import matplotlib.pyplot as plt


FILE = (
    r"C:\NUS\FYP\FYP Organized\data\raw"
    r"\2024-05-01 M2 AMMTO Fatigue Blanks 05.hdf5"
)

LAYER = 522

# Location confirmed by our previous test
CENTER_Y = 11180 + 100
CENTER_X = 9460 + 100

CROP_SIZE = 1200

OUTPUT = Path("results")
OUTPUT.mkdir(parents=True, exist_ok=True)


with h5py.File(FILE, "r") as f:

    raw_ds = f["/slices/registered_data/x-ray_ct_data"]
    flaw_ds = f["/slices/registered_data/x-ray_ct_flaw"]

    half = CROP_SIZE // 2

    y0 = max(0, CENTER_Y - half)
    x0 = max(0, CENTER_X - half)

    y1 = min(raw_ds.shape[1], y0 + CROP_SIZE)
    x1 = min(raw_ds.shape[2], x0 + CROP_SIZE)

    # Read only a small region, not the full XCT volume.
    raw = raw_ds[LAYER, y0:y1, x0:x1]
    flaw = flaw_ds[LAYER, y0:y1, x0:x1]


print("\n=== XCT REGION CHECK ===")

print("Layer:", LAYER)
print("Crop coordinates:", (y0, y1, x0, x1))

print("\nRAW XCT")
print("Shape:", raw.shape)
print("Nonzero pixels:", np.count_nonzero(raw))
print("Minimum:", raw.min())
print("Maximum:", raw.max())

print("\nXCT FLAW")
print("Nonzero pixels:", np.count_nonzero(flaw))
print("Minimum:", flaw.min())
print("Maximum:", flaw.max())

if np.any(flaw != 0):
    print("Nonzero flaw values:", np.unique(flaw[flaw != 0])[:20])
else:
    print("No nonzero flaw values in this crop.")


# Use only nonzero XCT pixels to determine display contrast.
positive_raw = raw[raw > 0]

if positive_raw.size:
    vmin, vmax = np.percentile(positive_raw, [2, 98])

    if vmax <= vmin:
        vmax = vmin + 1
else:
    vmin, vmax = 0, 1


raw_display = np.ma.masked_equal(raw, 0)
flaw_display = np.ma.masked_equal(flaw, 0)


fig, axes = plt.subplots(1, 3, figsize=(15, 5))

for ax in axes:
    ax.set_facecolor("black")
    ax.axis("off")


# Panel 1: Raw XCT
axes[0].imshow(
    raw_display,
    cmap="gray",
    vmin=vmin,
    vmax=vmax
)
axes[0].set_title("Raw XCT")


# Panel 2: Flaw mask
axes[1].imshow(
    flaw_display,
    cmap="magma",
    interpolation="nearest"
)
axes[1].set_title("XCT Flaw Mask")


# Panel 3: Overlay
axes[2].imshow(
    raw_display,
    cmap="gray",
    vmin=vmin,
    vmax=vmax
)

axes[2].imshow(
    flaw_display,
    cmap="autumn",
    alpha=0.8,
    interpolation="nearest"
)

axes[2].set_title("Flaw Mask Overlay")


fig.suptitle(
    f"Snow Dataset | Layer {LAYER} | XCT Region",
    fontsize=15
)

plt.tight_layout()

filename = OUTPUT / "snow_xct_layer_522_verified.png"

plt.savefig(
    filename,
    dpi=150,
    bbox_inches="tight"
)

plt.close()

print("\nSaved image to:", filename)
print("Visualization completed.")