
import h5py
import numpy as np

FILE = (
    r"C:\NUS\FYP\FYP Organized\data\raw"
    r"\2024-05-01 M2 AMMTO Fatigue Blanks 05.hdf5"
)


def describe_dataset(ds):
    print("  Shape:", ds.shape)
    print("  Dtype:", ds.dtype)
    print("  Chunks:", ds.chunks)
    print("  Compression:", ds.compression)

    if ds.chunks:
        chunk_mib = (
            np.prod(ds.chunks) * ds.dtype.itemsize / 1024**2
        )
        print(f"  Uncompressed chunk: {chunk_mib:.2f} MiB")

    for key in ds.attrs.keys():
        value = repr(ds.attrs[key])
        print(f"  Attribute [{key}]: {value[:250]}")


with h5py.File(FILE, "r") as f:

    print("=== 1. CAMERA CHANNELS ===")

    for group_path in [
        "/slices/camera_data/visible",
        "/slices/camera_data/nir",
    ]:
        print("\nGROUP:", group_path)

        group = f[group_path]

        for name in group.keys():
            obj = group[name]
            print("\nCHANNEL:", obj.name)

            if isinstance(obj, h5py.Dataset):
                describe_dataset(obj)
            else:
                print("  Contains:", list(obj.keys())[:10])

    print("\n=== 2. XCT AND ID DATASETS ===")

    paths = [
        "/slices/registered_data/x-ray_ct_data",
        "/slices/registered_data/x-ray_ct_flaw",
        "/slices/part_ids",
        "/slices/sample_ids",
    ]

    for path in paths:
        print("\nDATASET:", path)
        describe_dataset(f[path])

    print("\n=== 3. FATIGUE LABEL COVERAGE ===")

    path = "/parts/test_results/log10_fatigue_life"
    fatigue = f[path][:]

    print("Total stored entries:", fatigue.size)
    print("Finite entries:", np.isfinite(fatigue).sum())
    print("NaN entries:", np.isnan(fatigue).sum())
    print("First 12 values:", fatigue[:12])

    print("\n=== 4. PART AND SEGMENTATION METADATA ===")

    for group_path in [
        "/parts",
        "/slices/segmentation_results",
    ]:
        group = f[group_path]
        print("\nGROUP:", group_path)

        for key in group.attrs.keys():
            value = repr(group.attrs[key])
            print(f"{key}: {value[:1500]}")

    print("\n=== 5. SCAN LAYER COVERAGE ===")

    keys = list(f["/scans"].keys())
    print("Scan datasets:", len(keys))

    layer_numbers = set()

    for key in keys:
        first = key.split()[0]
        if first.isdigit():
            layer_numbers.add(int(first))

    if layer_numbers:
        print("Unique scan layers:", len(layer_numbers))
        print("Minimum layer:", min(layer_numbers))
        print("Maximum layer:", max(layer_numbers))

        expected = set(
            range(min(layer_numbers), max(layer_numbers) + 1)
        )
        missing = sorted(expected - layer_numbers)
        print("Missing indices within range:", missing[:20])

    print("\n=== INSPECTION COMPLETE ===")
