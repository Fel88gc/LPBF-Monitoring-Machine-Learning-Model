"""Catalog completed Snow source-preparation shards without reading raw HDF5.

Retains every prepared sensor row and all provisional targets/quality flags.
Verifies shard hashes and array headers, rejects duplicate sample identities,
and flags exact image-content duplicates across the complete extraction.
The output is a new directory; existing catalogs and shards are never changed.
"""
from __future__ import annotations

import argparse
import ast
import csv
import hashlib
import json
import sqlite3
import time
import zipfile
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path


EXTRA_COLUMNS = (
    "catalog_row", "feature_shard", "manifest_shard",
    "exact_duplicate_of_sample_id", "exact_duplicate_in_catalog",
    "exact_duplicate_across_layers", "catalog_quality_flags",
)
REQUIRED_COLUMNS = {
    "sample_id", "layer", "part_id", "part_name", "camera_y", "camera_x",
    "patch_size", "feature_row", "raw_image_sha256", "candidate_y",
    "label_validated", "coverage_validated", "dataset_status", "quality_flags",
    *{f"channel_{channel}_constant" for channel in range(3)},
    *{f"channel_{channel}_stored_max_fraction" for channel in range(3)},
}
STAT_COLUMNS = (
    "rows", "candidate_unknown", "candidate_zero", "candidate_one",
    "rows_with_quality_flags", "rows_with_constant_channel",
    "rows_with_all_three_channels_constant", "channel_0_constant",
    "channel_1_constant", "channel_2_constant", "rows_with_stored_max",
    "exact_duplicate_rows", "exact_duplicate_rows_across_layers",
)


def read_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return value


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def relative(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def csv_header(path: Path) -> list[str]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        header = next(csv.reader(handle), None)
    if not header or len(header) != len(set(header)):
        raise ValueError(f"Missing or repeated CSV column: {path}")
    if REQUIRED_COLUMNS - set(header):
        raise ValueError(f"Required CSV fields missing in {path}: {sorted(REQUIRED_COLUMNS - set(header))}")
    if set(header) & set(EXTRA_COLUMNS):
        raise ValueError(f"Input fields collide with catalog fields: {path}")
    return header


def npz_headers(path: Path) -> dict:
    """Read compressed NPY headers only; do not materialize feature arrays."""
    result = {}
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)):
            raise ValueError(f"Repeated ZIP members: {path}")
        for name in names:
            if not name.endswith(".npy") or "/" in name or "\\" in name:
                raise ValueError(f"Unexpected NPZ member {name!r}: {path}")
            with archive.open(name) as handle:
                if handle.read(6) != b"\x93NUMPY":
                    raise ValueError(f"Invalid NPY magic: {path}:{name}")
                version = tuple(handle.read(2))
                if version not in {(1, 0), (2, 0), (3, 0)}:
                    raise ValueError(f"Unsupported NPY version {version}: {path}:{name}")
                size_bytes = 2 if version == (1, 0) else 4
                length = int.from_bytes(handle.read(size_bytes), "little")
                if length > 65536:
                    raise ValueError(f"Unexpectedly large NPY header: {path}:{name}")
                header = ast.literal_eval(handle.read(length).decode("utf-8" if version == (3, 0) else "latin1"))
                if not isinstance(header, dict) or set(header) != {"descr", "fortran_order", "shape"}:
                    raise ValueError(f"Malformed NPY header: {path}:{name}")
                if not isinstance(header["descr"], str) or "O" in header["descr"]:
                    raise ValueError(f"Object/structured arrays not permitted: {path}:{name}")
                if not isinstance(header["shape"], tuple) or any(not isinstance(n, int) or n < 0 for n in header["shape"]):
                    raise ValueError(f"Invalid array shape: {path}:{name}")
                result[name[:-4]] = {"shape": list(header["shape"]), "dtype": header["descr"], "fortran_order": header["fortran_order"]}
    return result


def verify_arrays(headers: dict, rows: int, patch: int, path: Path) -> None:
    expected = {
        "X": [rows, 3, patch, patch], "candidate_y": [rows],
        "groups": [rows], "layers": [rows], "coords": [rows, 2],
        "label_validated": [rows], "coverage_validated": [rows],
    }
    if set(headers) != set(expected):
        raise ValueError(f"Unexpected feature arrays (including any final y target): {path}")
    for name, shape in expected.items():
        if headers[name]["shape"] != shape:
            raise ValueError(f"Array shape mismatch {name}: {path}")
    if headers["X"]["dtype"] not in {"<f4", ">f4", "=f4"}:
        raise ValueError(f"Features must be float32: {path}")
    if headers["candidate_y"]["dtype"] not in {"|i1", "<i1", ">i1", "=i1"}:
        raise ValueError(f"Provisional targets must be signed int8: {path}")
    for name in ("label_validated", "coverage_validated"):
        if headers[name]["dtype"] != "|b1":
            raise ValueError(f"Validation flags must be boolean arrays: {path}:{name}")


def string_counter(value: dict) -> Counter:
    return Counter({str(key): int(count) for key, count in value.items() if int(count)})


def stable_source_id(row: dict) -> str:
    return (f"snow_L{int(row['layer']):04d}_P{int(row['part_id']):02d}"
            f"_Y{int(row['camera_y'])}_X{int(row['camera_x'])}_S{int(row['patch_size'])}")


def increment_stats(stats: Counter, candidate: int, flags: set[str], constants: list[bool], stored_max: bool,
                    duplicate: bool, across_layers: bool) -> None:
    stats["rows"] += 1
    stats[{-1: "candidate_unknown", 0: "candidate_zero", 1: "candidate_one"}[candidate]] += 1
    stats["rows_with_quality_flags"] += bool(flags)
    stats["rows_with_constant_channel"] += any(constants)
    stats["rows_with_all_three_channels_constant"] += all(constants)
    stats["rows_with_stored_max"] += stored_max
    stats["exact_duplicate_rows"] += duplicate
    stats["exact_duplicate_rows_across_layers"] += across_layers
    for channel, constant in enumerate(constants):
        stats[f"channel_{channel}_constant"] += constant


def stats_row(stats: Counter) -> dict:
    return {name: int(stats[name]) for name in STAT_COLUMNS}


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    with path.open("x", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def resolve_from(root: Path, argument: Path) -> Path:
    return (argument if argument.is_absolute() else root / argument).resolve()


def consolidate(root: Path, source: Path, out: Path) -> dict:
    started = time.monotonic()
    if not source.is_relative_to(root) or not source.is_dir():
        raise ValueError("Source preparation must be an existing directory within the project")
    if (not out.is_relative_to(root) or out == source or source.is_relative_to(out)
            or out.is_relative_to(source / "layers")
            or any(out.is_relative_to(root / part) for part in ("data/raw", "data/processed"))):
        raise ValueError("Catalog output must be a separate new project directory outside source layer shards and original inputs")
    if out.exists():
        raise FileExistsError(f"Refusing existing catalog destination: {out}")
    config_path, production_path = source / "source_config.json", source / "production_summary.json"
    config, production = read_json(config_path), read_json(production_path)
    if production.get("stage") != "source_sensor_preparation_complete":
        raise ValueError("Source batch is not complete; wait for a completed production_summary.json")
    if production.get("ready_for_model_training") is not False or production.get("final_y_exported") is not False:
        raise ValueError("Expected source-preparation products with unvalidated candidate labels only")
    if production.get("raw_size_and_mtime_unchanged") is not True:
        raise ValueError("Production source-preservation check did not pass")
    first, last = int(config["nominal_gauge_layer_start"]), int(config["nominal_gauge_layer_end_inclusive"])
    layer_ids = list(range(first, last + 1))
    if last < first or int(production["layers_prepared"]) != len(layer_ids):
        raise ValueError("Production layer count does not match the declared source scope")
    if (int(production["layer_start"]), int(production["layer_end_inclusive"])) != (first, last):
        raise ValueError("Production layer bounds disagree with source configuration")
    expected_worker = production["worker_sha256"]
    patch = int(config["patch_size"])
    declared_specimens = set(map(int, config["specimen_ids"]))
    if len(declared_specimens) != int(config["specimen_count"]):
        raise ValueError("Source specimen count/lookup mismatch")
    source_hashes = {"source_config.json": sha256_file(config_path), "production_summary.json": sha256_file(production_path)}
    shards, header, quarantine_total, geometry_total = [], None, 0, 0
    # Verify all completed shard hashes before opening any catalog output.
    for layer in layer_ids:
        directory = source / "layers" / f"layer_{layer:04d}"
        summary_path, provenance_path = directory / "summary.json", directory / "shard_provenance.json"
        summary, provenance = read_json(summary_path), read_json(provenance_path)
        if summary.get("layer") != layer or summary.get("script_sha256") != expected_worker or provenance.get("worker_sha256") != expected_worker:
            raise ValueError(f"Shard identity/worker provenance mismatch: {directory}")
        if summary.get("ready_for_model_training") is not False or summary.get("final_y_exported") is not False:
            raise ValueError(f"Shard is not marked candidate-only: {directory}")
        if summary.get("raw_size_and_mtime_unchanged") is not True:
            raise ValueError(f"Shard source-preservation check failed: {directory}")
        rows = int(summary["rows"])
        actual_hashes = {}
        for name in ("features.npz", "manifest.csv"):
            actual_hashes[name] = sha256_file(directory / name)
            if provenance.get("files_sha256", {}).get(name) != actual_hashes[name]:
                raise ValueError(f"SHA-256 mismatch: {directory / name}")
        current_header = csv_header(directory / "manifest.csv")
        if header is None:
            header = current_header
        elif header != current_header:
            raise ValueError(f"Manifest schema/order changed between source shards: {directory}")
        headers = npz_headers(directory / "features.npz")
        verify_arrays(headers, rows, patch, directory / "features.npz")
        if set(map(int, summary["selected_parts"])) - declared_specimens:
            raise ValueError(f"Unexpected specimen outside declared scope: {directory}")
        quarantine_total += int(summary["quarantined"])
        geometry_total += int(summary["geometry_scope_excluded"])
        shards.append({"layer": layer, "directory": relative(directory, root), "summary": summary,
                       "files_sha256": actual_hashes, "summary_sha256": sha256_file(summary_path),
                       "shard_provenance_sha256": sha256_file(provenance_path), "array_headers": headers})
    if not header:
        raise ValueError("No source shard headers found")
    if quarantine_total != int(production["quarantined_patches"]) or geometry_total != int(production["geometry_scope_excluded"]):
        raise ValueError("Production quarantine/geometry totals disagree with shard summaries")
    if sum(int(shard["summary"]["rows"]) for shard in shards) != int(production["prepared_patches"]):
        raise ValueError("Production prepared-row count disagrees with source shards")

    out.mkdir(parents=True, exist_ok=False)
    total, source_flags, catalog_flags = Counter(), Counter(), Counter()
    candidates, per_layer, per_specimen, per_specimen_layer = Counter(), {}, defaultdict(Counter), defaultdict(Counter)
    part_names, original_part_counts = {}, {}
    database = out / "sample_index.sqlite"
    connection = sqlite3.connect(database)
    try:
        connection.execute("PRAGMA journal_mode=DELETE")
        connection.execute("CREATE TABLE sample_identity (sample_id TEXT PRIMARY KEY, layer INTEGER NOT NULL, part_id INTEGER NOT NULL, feature_row INTEGER NOT NULL, catalog_row INTEGER NOT NULL UNIQUE)")
        connection.execute("CREATE TABLE first_image_content (raw_image_sha256 TEXT PRIMARY KEY, sample_id TEXT NOT NULL, layer INTEGER NOT NULL, catalog_row INTEGER NOT NULL)")
        connection.commit()
        with (out / "manifest.csv").open("x", newline="", encoding="utf-8") as destination, (out / "exact_duplicate_content.csv").open("x", newline="", encoding="utf-8") as duplicates_handle:
            writer = csv.DictWriter(destination, fieldnames=header + list(EXTRA_COLUMNS))
            writer.writeheader()
            duplicate_writer = csv.DictWriter(duplicates_handle, fieldnames=["sample_id", "layer", "part_id", "feature_row", "catalog_row", "raw_image_sha256", "first_sample_id", "first_layer", "first_catalog_row", "across_layers"])
            duplicate_writer.writeheader()
            for shard in shards:
                layer, summary = shard["layer"], shard["summary"]
                directory = root / shard["directory"]
                layer_stats, layer_candidates, layer_flags, part_counts = Counter(), Counter(), Counter(), Counter()
                for part in summary["part_summary"]:
                    ident = int(part["part_id"])
                    if ident in part_names and part_names[ident] != part["part_name"]:
                        raise ValueError(f"Part-name lookup changed for P{ident}")
                    part_names[ident] = part["part_name"]
                    key = (layer, ident)
                    original_part_counts[key] = {"quarantined": int(part["quarantined"]),
                                                 "geometry_scope_excluded": int(part["grid_candidates"]) - int(part["geometry_selected"]),
                                                 "expected_retained": int(part["retained"])}
                with connection, (directory / "manifest.csv").open(newline="", encoding="utf-8-sig") as handle:
                    reader = csv.DictReader(handle)
                    for feature_row, row in enumerate(reader):
                        if None in row or any(value is None for value in row.values()):
                            raise ValueError(f"Malformed CSV record: {directory}, row {feature_row}")
                        ident, row_layer, candidate = int(row["part_id"]), int(row["layer"]), int(row["candidate_y"])
                        if row_layer != layer or int(row["feature_row"]) != feature_row or ident not in declared_specimens:
                            raise ValueError(f"Layer/specimen/feature-row mismatch: {directory}, row {feature_row}")
                        if row["sample_id"] != stable_source_id(row) or int(row["patch_size"]) != patch:
                            raise ValueError(f"Unstable sample identity/patch size: {directory}, row {feature_row}")
                        if candidate not in {-1, 0, 1} or int(row["label_validated"]) != 0 or int(row["coverage_validated"]) != 0:
                            raise ValueError(f"Candidate/validation status mismatch: {directory}, row {feature_row}")
                        if row["dataset_status"] != "source_prepared_candidate_labels_unvalidated":
                            raise ValueError(f"Unexpected sample status: {directory}, row {feature_row}")
                        digest = row["raw_image_sha256"]
                        if len(digest) != 64 or any(ch not in "0123456789abcdef" for ch in digest):
                            raise ValueError(f"Invalid raw-image SHA-256: {directory}, row {feature_row}")
                        global_row = int(total["rows"])
                        try:
                            connection.execute("INSERT INTO sample_identity VALUES (?, ?, ?, ?, ?)", (row["sample_id"], layer, ident, feature_row, global_row))
                        except sqlite3.IntegrityError as exc:
                            raise ValueError(f"Duplicate sample identity: {row['sample_id']}") from exc
                        first_seen = connection.execute("SELECT sample_id, layer, catalog_row FROM first_image_content WHERE raw_image_sha256 = ?", (digest,)).fetchone()
                        duplicate = first_seen is not None
                        across_layers = duplicate and int(first_seen[1]) != layer
                        flags = set(filter(None, row["quality_flags"].split(";")))
                        original_flags = flags.copy()
                        if duplicate:
                            flags.add("exact_duplicate_content_in_catalog")
                            if across_layers:
                                flags.add("exact_duplicate_content_across_layers")
                            duplicate_writer.writerow({"sample_id": row["sample_id"], "layer": layer, "part_id": ident,
                                                       "feature_row": feature_row, "catalog_row": global_row,
                                                       "raw_image_sha256": digest, "first_sample_id": first_seen[0],
                                                       "first_layer": first_seen[1], "first_catalog_row": first_seen[2],
                                                       "across_layers": int(across_layers)})
                        else:
                            connection.execute("INSERT INTO first_image_content VALUES (?, ?, ?, ?)", (digest, row["sample_id"], layer, global_row))
                        constants = []
                        for channel in range(3):
                            value = int(row[f"channel_{channel}_constant"])
                            if value not in {0, 1}:
                                raise ValueError(f"Invalid constant-channel flag: {row['sample_id']}")
                            constants.append(bool(value))
                        stored_max = any(float(row[f"channel_{channel}_stored_max_fraction"]) > 0 for channel in range(3))
                        for stats in (total, layer_stats, per_specimen[ident], per_specimen_layer[(layer, ident)]):
                            increment_stats(stats, candidate, flags, constants, stored_max, duplicate, across_layers)
                        source_flags.update(original_flags)
                        catalog_flags.update(flags)
                        layer_flags.update(original_flags)
                        layer_candidates[str(candidate)] += 1
                        candidates[str(candidate)] += 1
                        part_counts[ident] += 1
                        writer.writerow({**row, "catalog_row": global_row,
                                         "feature_shard": relative(directory / "features.npz", root),
                                         "manifest_shard": relative(directory / "manifest.csv", root),
                                         "exact_duplicate_of_sample_id": first_seen[0] if duplicate else "",
                                         "exact_duplicate_in_catalog": int(duplicate),
                                         "exact_duplicate_across_layers": int(across_layers),
                                         "catalog_quality_flags": ";".join(sorted(flags))})
                if int(layer_stats["rows"]) != int(summary["rows"]):
                    raise ValueError(f"Manifest row count disagrees with shard summary: layer {layer}")
                if layer_candidates != string_counter(summary["candidate_label_counts"]) or layer_flags != string_counter(summary["quality_flag_counts"]):
                    raise ValueError(f"Manifest candidate/quality counts disagree with shard summary: layer {layer}")
                for part in summary["part_summary"]:
                    if part_counts[int(part["part_id"])] != int(part["retained"]):
                        raise ValueError(f"Per-specimen row count disagrees with shard summary: layer {layer}, P{part['part_id']}")
                per_layer[layer] = layer_stats
                destination.flush()
                duplicates_handle.flush()
                print(f"Cataloged {layer}: {total['rows']} rows; {total['exact_duplicate_rows_across_layers']} cross-layer duplicate rows", flush=True)
        unique_images = int(connection.execute("SELECT COUNT(*) FROM first_image_content").fetchone()[0])
        unique_samples = int(connection.execute("SELECT COUNT(*) FROM sample_identity").fetchone()[0])
        connection.execute("CREATE INDEX sample_layer_part ON sample_identity(layer, part_id)")
        connection.commit()
        integrity = connection.execute("PRAGMA quick_check").fetchone()[0]
        if integrity != "ok" or unique_samples != total["rows"]:
            raise ValueError("SQLite integrity/global sample-identity check failed")
    finally:
        connection.close()

    if total["rows"] != int(production["prepared_patches"]) or candidates != string_counter(production["candidate_label_counts"]) or source_flags != string_counter(production["quality_flag_counts"]):
        raise ValueError("Catalog totals disagree with completed production summary")
    for name, expected_hash in source_hashes.items():
        if sha256_file(source / name) != expected_hash:
            raise RuntimeError(f"Source metadata changed while cataloging: {name}")
    layer_rows = [{"layer": layer, **stats_row(per_layer[layer]), "quarantined": int(shard["summary"]["quarantined"]),
                   "geometry_scope_excluded": int(shard["summary"]["geometry_scope_excluded"])}
                  for layer, shard in zip(layer_ids, shards)]
    group_rows = []
    for ident in sorted(part_names):
        keys = [key for key in original_part_counts if key[1] == ident]
        group_rows.append({"part_id": ident, "part_name": part_names[ident], **stats_row(per_specimen[ident]),
                           "quarantined": sum(original_part_counts[key]["quarantined"] for key in keys),
                           "geometry_scope_excluded": sum(original_part_counts[key]["geometry_scope_excluded"] for key in keys)})
    group_layer_rows = [{"layer": layer, "part_id": ident, "part_name": part_names[ident],
                         **stats_row(per_specimen_layer[(layer, ident)]),
                         "quarantined": original_part_counts[(layer, ident)]["quarantined"],
                         "geometry_scope_excluded": original_part_counts[(layer, ident)]["geometry_scope_excluded"]}
                        for layer, ident in sorted(original_part_counts)]
    write_csv(out / "per_layer.csv", layer_rows, ["layer", *STAT_COLUMNS, "quarantined", "geometry_scope_excluded"])
    write_csv(out / "per_specimen.csv", group_rows, ["part_id", "part_name", *STAT_COLUMNS, "quarantined", "geometry_scope_excluded"])
    write_csv(out / "per_specimen_layer.csv", group_layer_rows, ["layer", "part_id", "part_name", *STAT_COLUMNS, "quarantined", "geometry_scope_excluded"])
    with (out / "shard_verification.json").open("x", encoding="utf-8") as handle:
        json.dump({"source_preparation": relative(source, root), "source_metadata_sha256": source_hashes,
                   "worker_sha256": expected_worker, "all_required_files_sha256_verified": True,
                   "shards": [{key: value for key, value in shard.items() if key != "summary"} for shard in shards]}, handle, indent=2, allow_nan=False)
    readme = """# Canonical prepared-source catalog

This catalog indexes prepared three-channel Snow sensor patches; it does not certify
physical registration, measured XCT support, or final defect targets. The nominal
gauge-layer range and named fatigue-bar geometries are an extraction scope, not a
validated experimental coverage mask. Other source layers/geometries remain outside
this declared preparation scope.

`manifest.csv` retains every source manifest field and every prepared row. The stable
`sample_id` identifies layer, specimen and camera region. `feature_shard` is relative
to the project root; `feature_row` indexes X in that shard. `catalog_row` is a global
catalog ordinal. Sensor features use the unchanged pilot divisors 255/255/65535.
Original `quality_flags` remain unchanged; `catalog_quality_flags` additionally marks
exact raw three-channel content duplicates across the catalog. Duplicate rows are
retained, and `exact_duplicate_of_sample_id` refers to the first deterministic
layer/feature-row occurrence. The worker's `duplicate_of_feature_row` remains local
to its shard. No feature file or source manifest is rewritten.

`candidate_y` is -1 for unknown proxy/bounds, or provisional 0/1 from the existing
nonzero-annotation rule. A 0 is not a certified physical negative. All rows have
label_validated=0 and coverage_validated=0. There is no final y target, no chosen
train/test split, no automatic additional exclusions, and no model training.

`exact_duplicate_content.csv` lists later occurrences without deleting them.
`sample_index.sqlite` stores the unique identities and first image-content hashes.
The duplicate test uses the worker-provided SHA-256 over raw channel dtypes and
bytes; it detects exact content identity, not near duplicates or independence.
`per_layer.csv`, `per_specimen.csv` and `per_specimen_layer.csv` summarize retained
rows, provisional candidates and quality flags. Quarantine and geometry-scope
counts are carried from the verified producer summaries, not reapplied here.

`shard_verification.json` records verified SHA-256 digests and NPY header shapes.
The consolidator reads compressed array headers only; it does not load sensor
feature arrays, access raw HDF5, or independently recompute feature-value checks.
The original layer producer is responsible for the sensor-value checks and raw
image hashes. Final catalog completion is recorded only by summary.json.
"""
    with (out / "README.md").open("x", encoding="utf-8") as handle:
        handle.write(readme)
    artifact_hashes = {path.name: sha256_file(path) for path in sorted(out.iterdir()) if path.is_file()}
    result = {
        "stage": "source_preparation_catalog_complete", "created_utc": datetime.now(timezone.utc).isoformat(),
        "source_preparation": relative(source, root), "catalog_directory": relative(out, root),
        "layer_start": first, "layer_end_inclusive": last, "layers_cataloged": len(layer_ids),
        "declared_research_specimens": int(config["specimen_count"]), "specimens_with_rows": sum(bool(stats["rows"]) for stats in per_specimen.values()),
        **stats_row(total), "candidate_label_counts": {str(value): int(candidates[str(value)]) for value in (-1, 0, 1)},
        "source_quality_flag_counts": dict(sorted(source_flags.items())), "catalog_quality_flag_counts": dict(sorted(catalog_flags.items())),
        "unique_sample_ids": unique_samples, "unique_raw_image_hashes": unique_images,
        "quarantined_patches_from_producer": quarantine_total, "geometry_scope_excluded_from_producer": geometry_total,
        "source_metadata_sha256": source_hashes, "worker_sha256": expected_worker,
        "consolidator_sha256": sha256_file(Path(__file__)), "all_shard_manifest_and_feature_hashes_verified": True,
        "array_verification": "NPY headers only; no feature arrays materialized and no raw HDF5 read",
        "sqlite_integrity": integrity, "catalog_artifacts_sha256": artifact_hashes,
        "source_layers_outside_scope_not_prepared": int(production["source_layers_outside_scope_not_prepared"]),
        "label_status": "all candidate targets remain unvalidated; -1 unknown, 0/1 provisional",
        "scope_note": config["scope_note"], "ready_for_model_training": False, "final_y_exported": False,
        "additional_rows_excluded_by_catalog": 0, "elapsed_seconds": round(time.monotonic() - started, 3),
    }
    with (out / "summary.json").open("x", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2, allow_nan=False)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True, help="Existing project root")
    parser.add_argument("--source", type=Path, required=True, help="Completed source-preparation directory, absolute or relative to root")
    parser.add_argument("--output", type=Path, required=True, help="New catalog directory, absolute or relative to root; refuses existing paths")
    args = parser.parse_args()
    root = args.root.resolve(strict=True)
    result = consolidate(root, resolve_from(root, args.source), resolve_from(root, args.output))
    print(json.dumps(result, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
