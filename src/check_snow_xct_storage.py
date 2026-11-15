import h5py
import numpy as np

FILE = (
    r"C:\NUS\FYP\FYP Organized\data\raw"
    r"\2024-05-01 M2 AMMTO Fatigue Blanks 05.hdf5"
)

DATASETS = [
    "/slices/registered_data/x-ray_ct_data",
    "/slices/registered_data/x-ray_ct_flaw",
]

MAX_CHUNKS_TO_CHECK = 120

with h5py.File(FILE, "r") as f:

    for path in DATASETS:

        ds = f[path]

        print("\n" + "=" * 60)
        print("DATASET:", path)
        print("=" * 60)

        print("Shape:", ds.shape)
        print("Data type:", ds.dtype)
        print("Chunk shape:", ds.chunks)
        print("Fill value:", ds.fillvalue)

        storage_bytes = ds.id.get_storage_size()

        print(
            "Allocated storage:",
            round(storage_bytes / (1024**3), 3),
            "GiB"
        )

        num_chunks = ds.id.get_num_chunks()

        print("Stored chunks:", num_chunks)

        if num_chunks == 0:
            print("WARNING: No stored chunks found.")
            continue

        # Select chunk locations distributed across the dataset.
        indices = np.unique(
            np.linspace(
                0,
                num_chunks - 1,
                min(MAX_CHUNKS_TO_CHECK, num_chunks),
                dtype=np.int64
            )
        )

        found = False
        checked = 0
        sampled_layers = []

        for index in indices:

            info = ds.id.get_chunk_info(int(index))

            z0, y0, x0 = map(int, info.chunk_offset)
            sampled_layers.append(z0)

            y1 = min(y0 + ds.chunks[1], ds.shape[1])
            x1 = min(x0 + ds.chunks[2], ds.shape[2])

            # Check two layers within each selected chunk.
            test_layers = sorted(set([
                z0,
                min(z0 + ds.chunks[0] // 2, ds.shape[0] - 1)
            ]))

            for layer in test_layers:

                tile = ds[layer, y0:y1, x0:x1]

                nonzero_count = int(np.count_nonzero(tile))
                checked += 1

                if nonzero_count > 0:

                    found = True

                    print("\nNONZERO DATA FOUND!")
                    print("Layer:", layer)
                    print("Y coordinate:", y0)
                    print("X coordinate:", x0)
                    print("Nonzero pixels:", nonzero_count)
                    print("Minimum:", int(tile.min()))
                    print("Maximum:", int(tile.max()))

                    nonzero_values = tile[tile != 0]

                    print(
                        "Example nonzero values:",
                        np.unique(nonzero_values)[:15]
                    )

                    break

            if found:
                break

        print("\nTiles checked:", checked)

        if sampled_layers:
            print(
                "Sampled chunk-start layer range:",
                min(sampled_layers),
                "to",
                max(sampled_layers)
            )

        if not found:
            print(
                "No nonzero values found in selected stored chunks."
            )
            print(
                "This is inconclusive if storage was allocated."
            )

print("\nXCT storage inspection completed.")