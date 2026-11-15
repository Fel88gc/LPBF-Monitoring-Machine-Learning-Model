"""Package unchanged pilot arrays with audit flags, never final scientific labels."""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
from pathlib import Path
import numpy as np


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path, value):
    with path.open("x", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, allow_nan=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--run", type=Path, required=True)
    args = parser.parse_args()
    root, run = args.root.resolve(), args.run.resolve()
    if not run.is_relative_to(root / "results/data_quality"):
        raise ValueError("Run must be inside results/data_quality")
    pilot = load_json(run / "pilot/final/pilot_audit.json")
    spatial = load_json(run / "spatial/summary.json")
    if pilot["checks_failed"] or spatial["pilot_count_mismatches"] or spatial["raw_sensor_rows_not_exactly_reproduced"]:
        raise RuntimeError("Cannot package: source reproduction or consistency checks failed")
    destination = root / "data/review" / run.name
    if destination.exists():
        raise FileExistsError(f"Refusing to replace review dataset: {destination}")
    with (run / "spatial/candidate_crop_comparison.csv").open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    channel_flags = {int(item["row_index"]): item for item in pilot["channel_review_flag_samples"]}
    if len(rows) != pilot["rows"] or [int(row["pilot_row"]) for row in rows] != list(range(pilot["rows"])):
        raise ValueError("Review rows do not align with pilot row order")
    crop_sensitive = np.array([int(row["crop_label_disagreement"]) for row in rows], dtype=bool)
    channel_review = np.array([index in channel_flags for index in range(len(rows))], dtype=bool)
    archive_path = root / "data/processed/snow_pilot_patches.npz.npz"
    if not archive_path.exists():
        archive_path = root / "data/processed/snow_pilot_patches.npz"
    manifest_path = root / "data/processed/snow_pilot_manifest.csv"
    expected_archive_hash = pilot["source_sha256_after"][str(archive_path)]
    if hashlib.sha256(archive_path.read_bytes()).hexdigest() != expected_archive_hash:
        raise RuntimeError("Pilot archive changed since the audit; run a new audit before packaging")
    if hashlib.sha256(manifest_path.read_bytes()).hexdigest() != spatial["source_manifest_sha256"]:
        raise RuntimeError("Source manifest changed since spatial verification")
    with np.load(archive_path, allow_pickle=False) as incoming:
        arrays = {name: incoming[name] for name in ("X", "y", "groups", "layers")}
    destination.mkdir(parents=True)
    archive_out = destination / "snow_audited_provisional.npz"
    with archive_out.open("xb") as handle:
        np.savez_compressed(handle, **arrays, crop_boundary_sensitive=crop_sensitive,
                            channel_review_flag=channel_review,
                            raw_features_reproduced=np.ones(len(rows), dtype=bool),
                            registration_validated=np.zeros(len(rows), dtype=bool),
                            coverage_validated=np.zeros(len(rows), dtype=bool),
                            dataset_status=np.array("provisional_review_only"))
    with np.load(archive_out, allow_pickle=False) as check:
        identical = all(arrays[name].dtype == check[name].dtype and arrays[name].shape == check[name].shape
                        and arrays[name].tobytes() == check[name].tobytes() for name in arrays)
    if not identical:
        raise RuntimeError("Review package changed the original arrays")
    for index, row in enumerate(rows):
        row.update(channel_review_flag=int(channel_review[index]),
                   registration_validated=0, coverage_validated=0,
                   dataset_status="provisional_review_only",
                   mapping_version="dimension_ratio_v0_candidate",
                   source_hdf5="data/raw/2024-05-01 M2 AMMTO Fatigue Blanks 05.hdf5",
                   source_pilot=str(archive_path.relative_to(root)),
                   visible_divisor=255, nir_divisor=65535,
                   output_label_policy="original_pilot_label_preserved",
                   exclusion_applied=0)
    manifest_out = destination / "review_manifest.csv"
    with manifest_out.open("x", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    trace_rows = [row for row in rows if int(row["part_id"]) == 16 and int(row["layer"]) == 600
                  and int(row["camera_x"]) == 1994 and int(row["camera_y"]) in (1997, 2021)]
    if len(trace_rows) != 2:
        raise ValueError("Expected the two recorded P16 trace examples")
    save_json(destination / "record_trace_P16_layer600.json", {
        "sensor_paths": ["/slices/camera_data/visible/0", "/slices/camera_data/visible/1", "/slices/camera_data/nir/1"],
        "target_source": "/slices/registered_data/x-ray_ct_flaw",
        "label_rule": "1 if the candidate crop has any nonzero annotation pixel; provisional",
        "interpretation": "Dataset-detected XCT annotation; not a count of pores or proof of physical registration",
        "records": trace_rows})
    summary = {"dataset_status": "provisional_review_only", "ready_for_model_training": False,
               "rows": len(rows), "features_and_original_labels_bitwise_identical": identical,
               "exclusions": 0, "labels_changed": 0,
               "crop_sensitive_rows": int(crop_sensitive.sum()),
               "channel_review_rows": int(channel_review.sum()),
               "unique_local_review_flag_rows": int((crop_sensitive | channel_review).sum()),
               "registration_unvalidated_rows": len(rows), "coverage_unvalidated_rows": len(rows),
               "archive_sha256": hashlib.sha256(archive_out.read_bytes()).hexdigest(),
               "manifest_sha256": hashlib.sha256(manifest_out.read_bytes()).hexdigest(),
               "source_pilot_sha256": hashlib.sha256(archive_path.read_bytes()).hexdigest(),
               "preserved_label_rule": "original pilot_round and nonzero annotation count > 0",
               "why_not_final_cleaned_data": "Exact registered-grid conversion and true XCT support remain unresolved; no scientific threshold/exclusion policy has been approved."}
    save_json(destination / "review_status.json", summary)
    with (destination / "README.md").open("x", encoding="utf-8") as handle:
        handle.write("# Audited provisional review dataset\n\n"
                     "This package preserves all 2,024 original feature/label rows. It is **not ready for model training**.\n\n"
                     "The X, y, groups and layers arrays are bitwise equal to the existing pilot. "
                     "Extra arrays record crop-boundary sensitivity and channel review flags. No rows were excluded and no labels changed. "
                     "registration_validated and coverage_validated are false for every row; these are unresolved evidence requirements, not measured failures.\n\n"
                     "review_manifest.csv preserves the original coordinates, all three candidate XCT crops/counts, source paths and preprocessing divisors. "
                     "record_trace_P16_layer600.json traces the two presentation examples. "
                     "See the run's data-cleaning report before using any target for ML.\n")
    print(json.dumps({"output": str(destination), **summary}, indent=2))


if __name__ == "__main__":
    main()
