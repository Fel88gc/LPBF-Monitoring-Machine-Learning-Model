
import argparse
from pathlib import Path

import h5py

MAX_ITEMS = 2000


def inspect_hdf5(file_path):
    path = Path(file_path)

    print("\n=== SNOW HDF5 INVENTORY ===")

    if not path.is_file():
        raise FileNotFoundError(f"File not found: {path}")

    size_gb = path.stat().st_size / (1024 ** 3)
    print(f"File: {path.name}")
    print(f"Size: {size_gb:.2f} GiB")

    if not h5py.is_hdf5(str(path)):
        raise ValueError("File is not recognized as HDF5")

    with h5py.File(path, "r") as f:
        print("\nTop-level entries:")
        for key in f.keys():
            print(" -", key)

        print("\nRoot attribute names:")
        print(list(f.attrs.keys()))

        print("\n=== INTERNAL STRUCTURE ===")

        count = 0

        def describe(name, obj):
            nonlocal count

            if count >= MAX_ITEMS:
                return True

            count += 1

            if isinstance(obj, h5py.Dataset):
                print(
                    f"[DATASET] /{name}\n"
                    f"  shape: {obj.shape}\n"
                    f"  dtype: {obj.dtype}\n"
                    f"  chunks: {obj.chunks}\n"
                    f"  compression: {obj.compression}"
                )
            elif isinstance(obj, h5py.Group):
                print(f"[GROUP] /{name}")

            attr_names = list(obj.attrs.keys())
            if attr_names:
                print(f"  attributes: {attr_names[:10]}")

        f.visititems(describe)

        print(f"\nObjects inspected: {count}")
        if count >= MAX_ITEMS:
            print("Inventory limited to first 2000 objects.")

    print("\nRead-only inspection completed.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("file", help="Path to Snow HDF5 file")
    args = parser.parse_args()

    inspect_hdf5(args.file)
