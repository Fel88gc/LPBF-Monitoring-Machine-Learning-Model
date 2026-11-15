"""Extract fixed sensor-only descriptors from the verified prepared SNOW shards.

This is an exploratory baseline feature export. It neither fits preprocessing nor
changes the unvalidated candidate targets, source quality flags, or row cohort.
Only X enters ``extract_sensor_features``; targets and metadata remain separate.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import itertools
import json
import platform
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from numpy.lib.format import open_memmap


CHANNELS = ("visible_melt", "visible_recoat", "nir_max")
STATISTICS = (
    "mean", "std", "min", "max", "p10", "median", "p90", "p99",
    "zero_fraction", "one_fraction", "mean_abs_dx", "mean_abs_dy",
    "gradient_rms", "entropy16",
)
FEATURE_NAMES = [f"{channel}_{stat}" for channel in CHANNELS for stat in STATISTICS]
METADATA_COLUMNS = (
    "sample_id", "part_id", "layer", "camera_y", "camera_x", "candidate_y",
    "catalog_row", "feature_shard", "feature_row", "quality_flags",
    "channel_2_constant", "candidate_flaw_pixels", "label_validated",
    "coverage_validated",
)
DEFINITIONS = {
    "mean": "Arithmetic mean of the 576 normalized sensor pixels.",
    "std": "Population standard deviation of the 576 pixels (ddof=0).",
    "min": "Minimum normalized sensor pixel.",
    "max": "Maximum normalized sensor pixel.",
    "p10": "10th percentile of the pixels, NumPy linear interpolation.",
    "median": "50th percentile of the pixels, NumPy linear interpolation.",
    "p90": "90th percentile of the pixels, NumPy linear interpolation.",
    "p99": "99th percentile of the pixels, NumPy linear interpolation.",
    "zero_fraction": "Number of pixels exactly equal to 0 divided by 576.",
    "one_fraction": "Number of pixels exactly equal to 1 divided by 576.",
    "mean_abs_dx": "Mean absolute difference of horizontally adjacent pixels (axis x).",
    "mean_abs_dy": "Mean absolute difference of vertically adjacent pixels (axis y).",
    "gradient_rms": "sqrt((mean(dx**2) + mean(dy**2)) / 2), using all adjacent pairs on each axis.",
    "entropy16": "-sum(p*log2(p))/4 for 16 equal-width bins over [0,1]; left edges inclusive, right edges exclusive except final bin includes 1; 0*log2(0)=0.",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, value: object) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write("\n")


def checked_source_path(root: Path, relative: str, prepared: Path) -> Path:
    path = (root / relative).resolve()
    if not path.is_relative_to(prepared):
        raise ValueError(f"Source path escapes the prepared source directory: {relative}")
    return path


def extract_sensor_features(x: np.ndarray) -> np.ndarray:
    """Return N x 42 descriptors from N x 3 x 24 x 24 sensor images only.

    Arithmetic is float64 after reading the existing float32 normalized input;
    the final, finite matrix is stored as float32. There are no fitted statistics.
    """
    if x.ndim != 4 or x.shape[1:] != (3, 24, 24):
        raise ValueError(f"Expected N x 3 x 24 x 24, received {x.shape}")
    if x.dtype.kind != "f" or not np.isfinite(x).all():
        raise ValueError("Sensor images must contain finite floating-point values")
    if np.any(x < 0) or np.any(x > 1):
        raise ValueError("Prepared normalized sensor values must be in [0,1]")
    n = len(x)
    output = np.empty((n, len(FEATURE_NAMES)), dtype=np.float32)
    if not n:
        return output
    for channel in range(3):
        # Materialize one channel at a time, so memory does not scale with cohort.
        pixels = np.asarray(x[:, channel], dtype=np.float64)
        flat = pixels.reshape(n, -1)
        quantiles = np.quantile(flat, (0.10, 0.50, 0.90, 0.99), axis=1, method="linear")
        dx = np.diff(pixels, axis=2)
        dy = np.diff(pixels, axis=1)
        bins = np.minimum((flat * 16).astype(np.uint8), 15)
        histogram = np.bincount(
            (bins.astype(np.int64) + 16 * np.arange(n, dtype=np.int64)[:, None]).ravel(),
            minlength=n * 16,
        ).reshape(n, 16)
        probabilities = histogram / flat.shape[1]
        log_probabilities = np.zeros_like(probabilities)
        np.log2(probabilities, out=log_probabilities, where=probabilities > 0)
        values = (
            flat.mean(axis=1), flat.std(axis=1, ddof=0), flat.min(axis=1),
            flat.max(axis=1), *quantiles,
            np.mean(flat == 0, axis=1), np.mean(flat == 1, axis=1),
            np.mean(np.abs(dx), axis=(1, 2)), np.mean(np.abs(dy), axis=(1, 2)),
            np.sqrt((np.mean(dx * dx, axis=(1, 2)) + np.mean(dy * dy, axis=(1, 2))) / 2),
            -np.sum(probabilities * log_probabilities, axis=1) / 4,
        )
        output[:, channel * 14:(channel + 1) * 14] = np.column_stack(values)
    if not np.isfinite(output).all():
        raise ValueError("Extracted features are not all finite")
    return output


def verify_array(name: str, actual: np.ndarray, expected: np.ndarray) -> None:
    if actual.shape != expected.shape or not np.array_equal(actual, expected):
        raise ValueError(f"NPZ/catalog alignment failed for {name}")


def extract(root: Path, output: Path) -> dict:
    started = time.perf_counter()
    root, output = root.resolve(), output.resolve()
    if not output.is_relative_to(root / "data" / "features"):
        raise ValueError("Output must be a new directory within this project's data/features")
    if output.exists():
        raise FileExistsError(f"Refusing existing output directory: {output}")
    prepared = (root / "data/cleaned/snow_source_preparation_v1").resolve()
    catalog = prepared / "catalog/manifest.csv"
    summary_path = prepared / "catalog/summary.json"
    source_summary = json.loads(summary_path.read_text(encoding="utf-8"))
    catalog_hash = sha256_file(catalog)
    if catalog_hash != source_summary["catalog_artifacts_sha256"]["manifest.csv"]:
        raise ValueError("Source catalog checksum does not match catalog summary")
    rows_expected = int(source_summary["rows"])
    for name, expected_hash in source_summary["source_metadata_sha256"].items():
        if sha256_file(prepared / name) != expected_hash:
            raise ValueError(f"Source metadata checksum failed: {name}")

    output.parent.mkdir(parents=True, exist_ok=True)
    output.mkdir(exist_ok=False)
    write_json(output / "feature_names.json", FEATURE_NAMES)
    write_json(output / "feature_dictionary.json", {
        "input": "Existing normalized X arrays with shape N x 3 x 24 x 24; no targets or metadata enter feature computation.",
        "channel_order": list(CHANNELS), "feature_order": FEATURE_NAMES,
        "input_divisors_already_applied": [255, 255, 65535],
        "arithmetic_dtype": "float64", "output_dtype": "float32",
        "fitted_statistics": False, "spatial_axes": "X channel image axes are y then x",
        "definitions": DEFINITIONS,
        "target_status": "All candidate targets are unvalidated; -1 unknown, 0/1 provisional. No labels, flags, or rows are changed.",
    })
    features = open_memmap(output / "features.npy", mode="w+", dtype=np.float32,
                           shape=(rows_expected, len(FEATURE_NAMES)))
    targets = open_memmap(output / "candidate_y.npy", mode="w+", dtype=np.int8, shape=(rows_expected,))
    groups = open_memmap(output / "groups.npy", mode="w+", dtype=np.int32, shape=(rows_expected,))
    catalog_rows = open_memmap(output / "catalog_row.npy", mode="w+", dtype=np.int64, shape=(rows_expected,))
    counts: Counter = Counter()
    group_counts: Counter = Counter()
    flags: Counter = Counter()
    shard_records = []
    seen_shards = set()
    row_offset = 0
    with catalog.open("r", encoding="utf-8-sig", newline="") as source_stream, \
            (output / "metadata.csv").open("x", encoding="utf-8", newline="") as meta_stream:
        reader = csv.DictReader(source_stream)
        metadata_writer = csv.DictWriter(meta_stream, fieldnames=METADATA_COLUMNS)
        metadata_writer.writeheader()
        for shard_name, grouped_rows in itertools.groupby(reader, key=lambda row: row["feature_shard"]):
            if shard_name in seen_shards:
                raise ValueError(f"Noncontiguous canonical shard: {shard_name}")
            seen_shards.add(shard_name)
            rows = list(grouped_rows)
            n = len(rows)
            if row_offset + n > rows_expected:
                raise ValueError("Catalog exceeds declared row count")
            shard = checked_source_path(root, shard_name, prepared)
            manifests = {row["manifest_shard"] for row in rows}
            if len(manifests) != 1:
                raise ValueError("A feature shard maps to more than one manifest")
            manifest = checked_source_path(root, manifests.pop(), prepared)
            if manifest.parent != shard.parent:
                raise ValueError("Shard and manifest directories differ")
            provenance_path = shard.parent / "shard_provenance.json"
            provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
            if provenance["worker_sha256"] != source_summary["worker_sha256"]:
                raise ValueError(f"Worker provenance differs: {shard_name}")
            verified_hashes = {}
            for source_file in (shard, manifest):
                actual_hash = sha256_file(source_file)
                if actual_hash != provenance["files_sha256"][source_file.name]:
                    raise ValueError(f"Shard checksum failed: {source_file}")
                verified_hashes[source_file.name] = actual_hash
            with manifest.open("r", encoding="utf-8-sig", newline="") as stream:
                original_rows = list(csv.DictReader(stream))
            if len(original_rows) != n:
                raise ValueError(f"Shard/catalog row-count mismatch: {shard_name}")
            for index, (row, original_row) in enumerate(zip(rows, original_rows)):
                if int(row["feature_row"]) != index or int(row["catalog_row"]) != row_offset + index:
                    raise ValueError("Canonical feature_row/catalog_row order is not consecutive")
                for field in METADATA_COLUMNS:
                    if field in original_row and row[field] != original_row[field]:
                        raise ValueError(f"Shard/catalog metadata mismatch: {field} at {row_offset + index}")
            expected_targets = np.array([int(row["candidate_y"]) for row in rows], dtype=np.int8)
            if not np.isin(expected_targets, (-1, 0, 1)).all():
                raise ValueError("Candidate target outside {-1,0,1}")
            expected_groups = np.array([int(row["part_id"]) for row in rows], dtype=np.int32)
            with np.load(shard, allow_pickle=False) as arrays:
                expected_keys = {"X", "candidate_y", "groups", "layers", "coords", "label_validated", "coverage_validated"}
                if set(arrays.files) != expected_keys:
                    raise ValueError(f"Unexpected shard arrays: {arrays.files}")
                x = arrays["X"]
                if x.dtype != np.float32 or x.shape != (n, 3, 24, 24):
                    raise ValueError(f"Unexpected prepared sensor shape/dtype: {x.shape} {x.dtype}")
                verify_array("candidate_y", arrays["candidate_y"], expected_targets)
                verify_array("groups", arrays["groups"], expected_groups)
                verify_array("layers", arrays["layers"], np.array([int(row["layer"]) for row in rows], dtype=np.int32))
                verify_array("coords", arrays["coords"], np.array([[int(row["camera_y"]), int(row["camera_x"])] for row in rows], dtype=np.int32))
                for name in ("label_validated", "coverage_validated"):
                    expected = np.array([bool(int(row[name])) for row in rows], dtype=bool)
                    verify_array(name, arrays[name], expected)
                    if expected.any():
                        raise ValueError("This provisional baseline expects the source validation flags to remain false")
                features[row_offset:row_offset + n] = extract_sensor_features(x)
                del x
            targets[row_offset:row_offset + n] = expected_targets
            groups[row_offset:row_offset + n] = expected_groups
            catalog_rows[row_offset:row_offset + n] = np.arange(row_offset, row_offset + n, dtype=np.int64)
            for row in rows:
                metadata_writer.writerow({field: row[field] for field in METADATA_COLUMNS})
                counts[str(row["candidate_y"])] += 1
                group_counts[str(row["part_id"])] += 1
                flags.update(flag for flag in row["quality_flags"].split(";") if flag)
            shard_records.append({
                "feature_shard": shard_name, "rows": n,
                "catalog_row_start": row_offset, "catalog_row_stop_exclusive": row_offset + n,
                "source_files_sha256": verified_hashes,
                "shard_provenance_sha256": sha256_file(provenance_path),
                "npz_catalog_values_verified": ["groups", "layers", "coords", "candidate_y", "label_validated", "coverage_validated"],
            })
            row_offset += n
            if len(shard_records) == 1 or len(shard_records) % 10 == 0:
                print(f"Verified/extracted {len(shard_records)} shards; {row_offset:,}/{rows_expected:,} rows", flush=True)
    if row_offset != rows_expected or len(shard_records) != int(source_summary["layers_cataloged"]):
        raise ValueError("Final row or shard count does not match source summary")
    if dict(counts) != source_summary["candidate_label_counts"]:
        raise ValueError("Final candidate counts do not match source summary")
    if sha256_file(catalog) != catalog_hash:
        raise ValueError("Source catalog changed during extraction")
    for array in (features, targets, groups, catalog_rows):
        array.flush()
    # Close Windows mappings before downstream readers open them.
    del features, targets, groups, catalog_rows, array
    artifact_names = ("features.npy", "candidate_y.npy", "groups.npy", "catalog_row.npy",
                      "metadata.csv", "feature_names.json", "feature_dictionary.json")
    result = {
        "stage": "exploratory_baseline_v1_sensor_features_complete",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "rows": row_offset, "features": len(FEATURE_NAMES), "shape": [row_offset, len(FEATURE_NAMES)],
        "dtype": "float32", "source_shards": len(shard_records),
        "source_manifest": str(catalog.relative_to(root)).replace("\\", "/"),
        "source_manifest_sha256": catalog_hash,
        "source_catalog_summary_sha256": sha256_file(summary_path),
        "source_metadata_sha256": source_summary["source_metadata_sha256"],
        "extractor_sha256": sha256_file(Path(__file__).resolve()),
        "python_version": platform.python_version(), "numpy_version": np.__version__,
        "all_source_shard_hashes_verified": True, "all_npz_catalog_alignment_checks_passed": True,
        "all_input_images_finite_and_in_unit_interval": True, "all_features_finite": True,
        "canonical_row_order": "Source catalog order; catalog_row is consecutive from 0; each feature_row matches NPZ row.",
        "candidate_label_counts": dict(sorted(counts.items())),
        "specimens": len(group_counts), "specimen_rows": dict(sorted(group_counts.items(), key=lambda item: int(item[0]))),
        "source_quality_flag_counts_preserved": dict(sorted(flags.items())),
        "unknown_rows_retained": counts["-1"], "rows_dropped": 0,
        "fitted_statistics": False, "raw_hdf5_read": False, "source_files_written": False,
        "label_validated": False, "coverage_validated": False,
        "target_status": "All targets remain unvalidated: 0/1 are provisional and -1 is unknown. Intended only for exploratory feasibility, not validated defect-detection claims.",
        "artifacts_sha256": {name: sha256_file(output / name) for name in artifact_names},
        "shards": shard_records, "elapsed_seconds": round(time.perf_counter() - started, 3),
    }
    write_json(output / "summary.json", result)
    print(f"Complete: {row_offset:,} rows x {len(FEATURE_NAMES)} sensor features in {result['elapsed_seconds']:.1f}s", flush=True)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    extract(args.root, args.output if args.output.is_absolute() else args.root / args.output)


if __name__ == "__main__":
    main()
