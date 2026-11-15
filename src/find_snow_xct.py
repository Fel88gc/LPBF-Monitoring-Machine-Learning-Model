
from pathlib import Path

import h5py
import numpy as np
import matplotlib.pyplot as plt

FILE = (
    r"C:\NUS\FYP\FYP Organized\data\raw"
    r"\2024-05-01 M2 AMMTO Fatigue Blanks 05.hdf5"
)

LAYER = 500
TILE_SIZE = 256
GRID_SIZE = 9

OUTPUT = Path("results")
OUTPUT.mkdir(exist_ok=True)

with h5py.File(FILE, "r") as f:

    raw = f["/slices/registered_data/x-ray_ct_data"]
    flaw = f["/slices/registered_data/x-ray_ct_flaw"]

    height, width = raw.shape[1:]

    ys = np.linspace(
        0, height - TILE_SIZE, GRID_SIZE, dtype=int
    )
    xs = np.linspace(
        0, width - TILE_SIZE, GRID_SIZE, dtype=int
    )

    best_raw_count = 0
    best_flaw_count = 0
    best_raw_location = None
    best_flaw_location = None

    print("Searching small XCT regions...")

    for row_number, y in enumerate(ys, start=1):
        for x in xs:

            raw_tile = raw[
                LAYER,
                y:y + TILE_SIZE,
                x:x + TILE_SIZE
            ]

            flaw_tile = flaw[
                LAYER,
                y:y + TILE_SIZE,
                x:x + TILE_SIZE
            ]

            raw_count = int(np.count_nonzero(raw_tile))
            flaw_count = int(np.count_nonzero(flaw_tile))

            if raw_count > best_raw_count:
                best_raw_count = raw_count
                best_raw_location = (y, x)

            if flaw_count > best_flaw_count:
                best_flaw_count = flaw_count
                best_flaw_location = (y, x)

        print(
            f"Checked grid row {row_number}/{GRID_SIZE}",
            flush=True
        )

    print("\n=== SEARCH RESULTS ===")
    print("Largest raw nonzero count:", best_raw_count)
    print("Best raw location:", best_raw_location)
    print("Largest flaw nonzero count:", best_flaw_count)
    print("Best flaw location:", best_flaw_location)

    location = (
        best_flaw_location
        if best_flaw_location is not None
        else best_raw_location
    )

    if location is None:
        print(
            "\nNo nonzero values found in sampled tiles."
            "\nThis does not prove the XCT volume is empty."
        )

    else:
        y, x = location

        raw_tile = raw[
            LAYER,
            y:y + TILE_SIZE,
            x:x + TILE_SIZE
        ]

        flaw_tile = flaw[
            LAYER,
            y:y + TILE_SIZE,
            x:x + TILE_SIZE
        ]

        values, counts = np.unique(
            flaw_tile, return_counts=True
        )

        top = np.argsort(counts)[-10:][::-1]

        print("\nMost common flaw-array values:")
        for i in top:
            print(int(values[i]), ":", int(counts[i]))

        fig, axes = plt.subplots(1, 2, figsize=(10, 5))

        axes[0].imshow(raw_tile, cmap="gray")
        axes[0].set_title("Raw XCT")

        axes[1].imshow(flaw_tile, cmap="magma")
        axes[1].set_title("XCT flaw values")

        for ax in axes:
            ax.axis("off")

        fig.suptitle(
            f"Layer {LAYER} | XCT crop at y={y}, x={x}"
        )

        plt.tight_layout()

        filename = (
            OUTPUT / f"snow_xct_search_layer_{LAYER}.png"
        )

        plt.savefig(filename, dpi=150)
        plt.close()

        print("\nSaved:", filename)

print("\nSearch completed.")
