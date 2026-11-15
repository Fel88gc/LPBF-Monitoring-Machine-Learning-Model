
from pathlib import Path

import h5py
import numpy as np
import matplotlib.pyplot as plt

FILE = (
    r"C:\NUS\FYP\FYP Organized\data\raw"
    r"\2024-05-01 M2 AMMTO Fatigue Blanks 05.hdf5"
)

LAYER = 500
CROP_SIZE = 512

OUTPUT = Path("results")
OUTPUT.mkdir(parents=True, exist_ok=True)

PANELS = [
    ("Visible post-melt",
     "/slices/camera_data/visible/0", "gray"),

    ("Visible post-recoat",
     "/slices/camera_data/visible/1", "gray"),

    ("NIR integrated sum",
     "/slices/camera_data/nir/0", "inferno"),

    ("NIR integrated max",
     "/slices/camera_data/nir/1", "inferno"),

    ("NIR argmax",
     "/slices/camera_data/nir/2", "viridis"),

    ("Raw XCT",
     "/slices/registered_data/x-ray_ct_data", "gray"),

    ("XCT flaw values",
     "/slices/registered_data/x-ray_ct_flaw", "magma"),

    ("Part IDs",
     "/slices/part_ids", "tab20"),
]


def read_center_crop(dataset):
    """Read one small region, never a full 3D dataset."""
    height = dataset.shape[1]
    width = dataset.shape[2]

    y0 = (height - CROP_SIZE) // 2
    x0 = (width - CROP_SIZE) // 2

    return dataset[
        LAYER,
        y0:y0 + CROP_SIZE,
        x0:x0 + CROP_SIZE
    ]


with h5py.File(FILE, "r") as f:

    fig, axes = plt.subplots(2, 4, figsize=(16, 8))

    for ax, (title, path, cmap) in zip(
        axes.flat, PANELS
    ):
        dataset = f[path]
        image = read_center_crop(dataset)

        print(f"\n{title}")
        print("Shape:", image.shape)
        print("Dtype:", image.dtype)
        print("Minimum:", np.min(image))
        print("Maximum:", np.max(image))
        print("Nonzero pixels:", np.count_nonzero(image))

        ax.imshow(image, cmap=cmap)
        ax.set_title(title)
        ax.axis("off")

    fig.suptitle(
        f"Snow Dataset - Layer {LAYER}\n"
        "Independent central crops; spatial alignment not verified",
        fontsize=14
    )

    plt.tight_layout()

    filename = OUTPUT / f"snow_layer_{LAYER}_preview.png"

    plt.savefig(filename, dpi=150, bbox_inches="tight")
    plt.close()

    print("\nSaved preview to:", filename)
