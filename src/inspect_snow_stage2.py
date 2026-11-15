
from pathlib import Path
from itertools import islice
import h5py

# Your original Snow dataset
FILE = (
    r"C:\NUS\FYP\FYP Organized\data\raw"
    r"\2024-05-01 M2 AMMTO Fatigue Blanks 05.hdf5"
)

MAX_DEPTH = 2
MAX_CHILDREN = 8


def explore(group, depth=0):
    """Display a small, bounded part of the HDF5 tree."""
    indent = "  " * depth

    print(
        f"{indent}[GROUP] {group.name} "
        f"({len(group)} children)"
    )

    attr_names = list(islice(group.attrs.keys(), 8))
    if attr_names:
        print(f"{indent}  Attributes: {attr_names}")

    limit = 40 if depth == 0 else MAX_CHILDREN

    for name in islice(group.keys(), limit):
        try:
            obj = group[name]

            if isinstance(obj, h5py.Group):
                if depth < MAX_DEPTH:
                    explore(obj, depth + 1)
                else:
                    print(
                        f"{indent}  [GROUP] {obj.name} "
                        f"({len(obj)} children)"
                    )

            elif isinstance(obj, h5py.Dataset):
                print(
                    f"{indent}  [DATASET] {obj.name}\n"
                    f"{indent}    Shape: {obj.shape}\n"
                    f"{indent}    Dtype: {obj.dtype}"
                )

                attrs = list(islice(obj.attrs.keys(), 8))
                if attrs:
                    print(f"{indent}    Attributes: {attrs}")

        except Exception as error:
            print(f"{indent}  Cannot inspect {name}: {error}")

    if len(group) > limit:
        print(
            f"{indent}  ... more children not displayed"
        )


def main():
    path = Path(FILE)

    print("=== SNOW DATASET: STAGE 2 ===")
    print("File exists:", path.is_file())

    if not path.is_file():
        raise FileNotFoundError(path)

    print(
        "File size (GiB):",
        round(path.stat().st_size / 1024**3, 2)
    )

    with h5py.File(path, "r") as f:
        print("\n=== DATASET STRUCTURE ===")
        explore(f)

        print("\n=== SPOT CHECK: SCAN DATA ===")

        scan_path = "/scans/447_point"

        if scan_path in f:
            dataset = f[scan_path]

            print("Path:", scan_path)
            print("Shape:", dataset.shape)
            print("Dtype:", dataset.dtype)

            if dataset.ndim == 2 and dataset.shape[0] > 0:
                indices = [
                    0,
                    dataset.shape[0] // 2,
                    dataset.shape[0] - 1,
                ]

                for i in indices:
                    row = dataset[i, :]
                    print(f"Row {i}: {row.tolist()}")

        else:
            print("Example scan dataset not found.")

    print("\nStage 2 inspection finished.")


if __name__ == "__main__":
    main()
