from pathlib import Path

import h5py
import numpy as np
import matplotlib.pyplot as plt


FILE = (
    r"C:\NUS\FYP\FYP Organized\data\raw"
    r"\2024-05-01 M2 AMMTO Fatigue Blanks 05.hdf5"
)

LAYER = 600
PART_ID = 16
PADDING = 25

BUILD_SIZE_MM = 245.0

OUTPUT = Path("results")
OUTPUT.mkdir(parents=True, exist_ok=True)


with h5py.File(FILE, "r") as f:

    # Find the selected specimen.
    part_map = f["/slices/part_ids"][LAYER]

    ys, xs = np.where(part_map == PART_ID)

    if len(xs) == 0:
        raise ValueError(
            f"Part {PART_ID} not found at layer {LAYER}"
        )

    y0 = max(0, int(ys.min()) - PADDING)
    y1 = min(part_map.shape[0], int(ys.max()) + PADDING + 1)

    x0 = max(0, int(xs.min()) - PADDING)
    x1 = min(part_map.shape[1], int(xs.max()) + PADDING + 1)

    # Read the in-situ images.
    visible = f[
        "/slices/camera_data/visible/0"
    ][LAYER, y0:y1, x0:x1]

    nir = f[
        "/slices/camera_data/nir/1"
    ][LAYER, y0:y1, x0:x1]

    # Access the registered XCT arrays.
    ct_ds = f[
        "/slices/registered_data/x-ray_ct_data"
    ]

    flaw_ds = f[
        "/slices/registered_data/x-ray_ct_flaw"
    ]

    # Candidate scale factors, assuming the same
    # physical build-plate extent in both arrays.
    scale_y = ct_ds.shape[1] / part_map.shape[0]
    scale_x = ct_ds.shape[2] / part_map.shape[1]

    cy0 = int(np.floor(y0 * scale_y))
    cy1 = int(np.ceil(y1 * scale_y))

    cx0 = int(np.floor(x0 * scale_x))
    cx1 = int(np.ceil(x1 * scale_x))

    raw_ct = ct_ds[LAYER, cy0:cy1, cx0:cx1]
    flaw = flaw_ds[LAYER, cy0:cy1, cx0:cx1]


print("\n=== ALIGNMENT CHECK ===")
print("Layer:", LAYER)
print("Part ID:", PART_ID)

print("\nCamera crop:", (y0, y1, x0, x1))
print("XCT crop:", (cy0, cy1, cx0, cx1))

print("\nCamera-to-XCT scale:")
print("Y:", scale_y)
print("X:", scale_x)

print("\nRaw XCT nonzero pixels:", np.count_nonzero(raw_ct))
print("XCT flaw nonzero pixels:", np.count_nonzero(flaw))


# Convert pixel boundaries to physical coordinates.
cam_mm_per_pixel = BUILD_SIZE_MM / part_map.shape[1]
ct_mm_per_pixel = BUILD_SIZE_MM / ct_ds.shape[2]

camera_extent = (
    x0 * cam_mm_per_pixel,
    x1 * cam_mm_per_pixel,
    y0 * cam_mm_per_pixel,
    y1 * cam_mm_per_pixel,
)

ct_extent = (
    cx0 * ct_mm_per_pixel,
    cx1 * ct_mm_per_pixel,
    cy0 * ct_mm_per_pixel,
    cy1 * ct_mm_per_pixel,
)


# Prepare XCT display.
positive_ct = raw_ct[raw_ct > 0]

if positive_ct.size:
    vmin, vmax = np.percentile(positive_ct, [2, 98])

    if vmax <= vmin:
        vmax = vmin + 1
else:
    vmin, vmax = 0, 1

ct_display = np.ma.masked_equal(raw_ct, 0)
flaw_display = np.ma.masked_equal(flaw, 0)


fig, axes = plt.subplots(
    1, 3,
    figsize=(16, 5),
    constrained_layout=True
)

axes[0].imshow(
    visible,
    cmap="gray",
    origin="lower",
    extent=camera_extent
)
axes[0].set_title("Visible Post-Melt")

axes[1].imshow(
    np.log1p(nir.astype(np.float32)),
    cmap="inferno",
    origin="lower",
    extent=camera_extent
)
axes[1].set_title("NIR Integrated Max")

axes[2].imshow(
    ct_display,
    cmap="gray",
    origin="lower",
    extent=ct_extent,
    vmin=vmin,
    vmax=vmax
)

axes[2].imshow(
    flaw_display,
    cmap="autumn",
    origin="lower",
    extent=ct_extent,
    alpha=0.85
)
axes[2].set_title("XCT + Flaw Labels")


# Plot XCT flaw locations on the in-situ images.
flaw_y, flaw_x = np.where(flaw > 0)

if len(flaw_x):

    # Limit plotted points to keep the figure readable.
    step = max(1, len(flaw_x) // 5000)

    x_mm = (
        cx0 + flaw_x[::step] + 0.5
    ) * ct_mm_per_pixel

    y_mm = (
        cy0 + flaw_y[::step] + 0.5
    ) * ct_mm_per_pixel

    for ax in axes[:2]:
        ax.scatter(
            x_mm,
            y_mm,
            s=2,
            c="cyan",
            alpha=0.6
        )


for ax in axes:
    ax.set_xlim(camera_extent[0], camera_extent[1])
    ax.set_ylim(camera_extent[2], camera_extent[3])

    ax.set_xlabel("X (mm)")
    ax.set_ylabel("Y (mm)")
    ax.set_aspect("equal")


fig.suptitle(
    "Snow Dataset — Layer 600, Part P16\n"
    "Candidate spatial mapping: verification required"
)

filename = OUTPUT / "snow_alignment_P16_layer600.png"

plt.savefig(filename, dpi=150)
plt.close()

print("\nSaved:", filename)
print("Alignment test completed.")