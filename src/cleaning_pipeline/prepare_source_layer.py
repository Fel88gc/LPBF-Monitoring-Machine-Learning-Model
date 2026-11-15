"""Prepare one raw Snow layer as a new, source-traceable sensor-feature shard.

Default scope is the root-lookup AMMTO Fatigue Bar specimens present in the layer.
Candidate XCT labels reproduce pilot rules, remain scientifically unvalidated,
and are never exported as a final y target. No existing file is overwritten.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import h5py
import numpy as np

RAW_NAME = "2024-05-01 M2 AMMTO Fatigue Blanks 05.hdf5"
CHANNEL_PATHS = ("/slices/camera_data/visible/0", "/slices/camera_data/visible/1", "/slices/camera_data/nir/1")
PATCH = 24
MIN_PART_FRACTION = .75
MIN_RAW_POSITIVE_PROXY = .50
MAX_TILE_BYTES = 16 * 1024**2


def lookup(value):
    if isinstance(value, bytes):
        value = value.decode("utf-8", errors="replace")
    return str(value).split(",")


def write_csv(path, rows):
    if not rows:
        return
    with path.open("x", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True, help="New layer-shard directory, never an existing folder")
    parser.add_argument("--layer", type=int, required=True)
    parser.add_argument("--part-ids", type=int, nargs="+", help="Optional explicit IDs; default selects present AMMTO Fatigue Bar names")
    args = parser.parse_args()
    root, out = args.root.resolve(strict=True), args.output.resolve()
    if out == root or not out.is_relative_to(root) or any(out.is_relative_to(root / p) for p in ("data/raw", "data/processed")):
        raise ValueError("Output must be a new project directory outside original raw/processed inputs")
    if out.exists():
        raise FileExistsError(f"Refusing to overwrite layer shard: {out}")
    raw = root / "data/raw" / RAW_NAME
    before = raw.stat()
    started = time.monotonic()
    images, records, quarantine, scope_excluded, part_summaries = [], [], [], [], []
    hashes, logical_bytes, discovered, selected = {}, 0, [], []
    with h5py.File(raw, "r", rdcc_nbytes=32 * 1024**2, rdcc_nslots=10007) as h5:
        part_ds, sample_ds = h5["/slices/part_ids"], h5["/slices/sample_ids"]
        ct_ds, flaw_ds = h5["/slices/registered_data/x-ray_ct_data"], h5["/slices/registered_data/x-ray_ct_flaw"]
        sensors = [h5[path] for path in CHANNEL_PATHS]
        if not 0 <= args.layer < part_ds.shape[0]:
            raise ValueError("Layer index is outside source slice-axis bounds")
        if any(ds.shape != part_ds.shape for ds in [sample_ds, *sensors]) or ct_ds.shape != flaw_ds.shape:
            raise ValueError("Source modality shapes are inconsistent")
        if any(ds.ndim != 3 for ds in [part_ds, sample_ds, ct_ds, flaw_ds, *sensors]):
            raise ValueError("Expected layer,Y,X source arrays")
        if ct_ds.shape[0] != part_ds.shape[0]:
            raise ValueError("XCT and camera layer-axis lengths disagree")
        parts, samples = part_ds[args.layer], sample_ds[args.layer]
        logical_bytes += parts.nbytes + samples.nbytes
        discovered = [int(value) for value in np.unique(parts) if value != 0]
        names = lookup(h5.attrs.get("parts/part_stl_filenames", ""))
        sample_names = lookup(h5.attrs.get("samples/sample_stl_filenames", ""))
        layer_note = str(h5.attrs.get(f"layer_notes/{args.layer}", "")).strip()
        acquisition_event = any(word in layer_note.lower() for word in ("trigger", "occlud", "recoater", "subsequent layer"))
        name_for = lambda ident: names[ident] if 0 <= ident < len(names) else "UNKNOWN_ROOT_LOOKUP"
        requested = set(args.part_ids) if args.part_ids else {ident for ident in discovered if "AMMTO Fatigue Bar" in name_for(ident)}
        selected = sorted(set(discovered) & requested - {0})
        if not selected:
            raise ValueError("No requested research specimens are present in the source layer")
        sy, sx = ct_ds.shape[1] / parts.shape[0], ct_ds.shape[2] / parts.shape[1]
        out.mkdir(parents=True, exist_ok=False)
        for part_id in selected:
            yy, xx = np.where(parts == part_id)
            y_min, y_max, x_min, x_max = int(yy.min()), int(yy.max()), int(xx.min()), int(xx.max())
            candidates = []
            grid_count = 0
            for y in range(y_min, y_max - PATCH + 2, PATCH):
                for x in range(x_min, x_max - PATCH + 2, PATCH):
                    grid_count += 1
                    fraction = float(np.mean(parts[y:y+PATCH, x:x+PATCH] == part_id))
                    if fraction < MIN_PART_FRACTION:
                        scope_excluded.append({"layer": args.layer, "part_id": part_id, "camera_y": y, "camera_x": x,
                                               "part_fraction": fraction, "reason": "outside_legacy_0.75_part_geometry_scope"})
                    else:
                        candidates.append((y, x, fraction))
            if not candidates:
                part_summaries.append({"part_id": part_id, "part_name": name_for(part_id), "grid_candidates": grid_count,
                                       "geometry_selected": 0, "retained": 0, "quarantined": 0})
                continue
            by0, by1 = min(p[0] for p in candidates), max(p[0] + PATCH for p in candidates)
            bx0, bx1 = min(p[1] for p in candidates), max(p[1] + PATCH for p in candidates)
            ty0, ty1, tx0, tx1 = round(by0*sy), round(by1*sy), round(bx0*sx), round(bx1*sx)
            tile_valid = 0 <= ty0 < ty1 <= ct_ds.shape[1] and 0 <= tx0 < tx1 <= ct_ds.shape[2]
            ct_tile_bytes = (ty1-ty0) * (tx1-tx0) * (ct_ds.dtype.itemsize + flaw_ds.dtype.itemsize)
            raw_tile = flaw_tile = None
            if tile_valid and ct_tile_bytes <= MAX_TILE_BYTES:
                raw_tile = ct_ds[args.layer, ty0:ty1, tx0:tx1]
                flaw_tile = flaw_ds[args.layer, ty0:ty1, tx0:tx1]
                logical_bytes += raw_tile.nbytes + flaw_tile.nbytes
            camera_bytes = (by1-by0) * (bx1-bx0) * sum(ds.dtype.itemsize for ds in sensors)
            sensor_tiles = [ds[args.layer, by0:by1, bx0:bx1] for ds in sensors] if camera_bytes <= MAX_TILE_BYTES else None
            if sensor_tiles:
                logical_bytes += sum(tile.nbytes for tile in sensor_tiles)
            retained_before, quarantined_before = len(records), len(quarantine)
            for y, x, part_fraction in candidates:
                raw_images = [tile[y-by0:y-by0+PATCH, x-bx0:x-bx0+PATCH] for tile in sensor_tiles] if sensor_tiles else [ds[args.layer, y:y+PATCH, x:x+PATCH] for ds in sensors]
                if sensor_tiles is None:
                    logical_bytes += sum(image.nbytes for image in raw_images)
                row = {"sample_id": f"snow_L{args.layer:04d}_P{part_id:02d}_Y{y}_X{x}_S{PATCH}", "layer": args.layer,
                       "part_id": part_id, "part_name": name_for(part_id), "unknown_part_lookup": int(part_id >= len(names)),
                       "camera_y": y, "camera_x": x, "patch_size": PATCH, "part_fraction": part_fraction,
                       "source_hdf5": str(raw.relative_to(root)), "sensor_paths": ";".join(CHANNEL_PATHS),
                       "mapping_version": "dimension_ratio_pilot_round_v0_candidate", "scale_y": sy, "scale_x": sx,
                       "visible_divisor": 255, "nir_divisor": 65535, "label_validated": 0, "coverage_validated": 0,
                       "source_layer_note": layer_note,
                       "dataset_status": "source_prepared_candidate_labels_unvalidated"}
                reasons = []
                if any(image.shape != (PATCH, PATCH) for image in raw_images):
                    reasons.append("invalid_sensor_shape")
                if any(not np.isfinite(image).all() for image in raw_images):
                    reasons.append("nonfinite_sensor_values")
                if all(not np.any(image) for image in raw_images):
                    reasons.append("all_three_sensor_channels_zero")
                if reasons:
                    quarantine.append({**row, "quarantine_reason": ";".join(reasons), "feature_row": -1})
                    continue
                digest = hashlib.sha256()
                flags = []
                if acquisition_event:
                    flags.append("author_layer_event_affected_region_requires_review")
                for channel, image in enumerate(raw_images):
                    digest.update(str(image.dtype).encode("ascii")); digest.update(np.ascontiguousarray(image).tobytes())
                    constant = bool(np.ptp(image) == 0)
                    dtype_max = np.iinfo(image.dtype).max if np.issubdtype(image.dtype, np.integer) else None
                    row[f"channel_{channel}_dtype"] = str(image.dtype)
                    row[f"channel_{channel}_constant"] = int(constant)
                    row[f"channel_{channel}_zero_fraction"] = float(np.mean(image == 0))
                    row[f"channel_{channel}_stored_max_fraction"] = float(np.mean(image == dtype_max)) if dtype_max is not None else None
                    if constant:
                        flags.append(f"channel_{channel}_constant")
                    if np.all(image == 0):
                        flags.append(f"channel_{channel}_zero")
                    if dtype_max is not None and np.any(image == dtype_max):
                        flags.append(f"channel_{channel}_has_stored_max")
                raw_hash = digest.hexdigest()
                row["raw_image_sha256"] = raw_hash
                row["duplicate_of_feature_row"] = hashes.get(raw_hash, -1)
                if row["duplicate_of_feature_row"] >= 0:
                    flags.append("exact_duplicate_content_within_layer")
                else:
                    hashes[raw_hash] = len(records)
                y0, y1, x0, x1 = round(y*sy), round((y+PATCH)*sy), round(x*sx), round((x+PATCH)*sx)
                row.update(xct_y0=y0, xct_y1=y1, xct_x0=x0, xct_x1=x1)
                valid_bounds = 0 <= y0 < y1 <= ct_ds.shape[1] and 0 <= x0 < x1 <= ct_ds.shape[2]
                raw_positive, flaw_count, candidate_y = None, None, -1
                if valid_bounds:
                    if raw_tile is not None:
                        ct = raw_tile[y0-ty0:y1-ty0, x0-tx0:x1-tx0]
                        flaw = flaw_tile[y0-ty0:y1-ty0, x0-tx0:x1-tx0]
                    else:
                        ct, flaw = ct_ds[args.layer, y0:y1, x0:x1], flaw_ds[args.layer, y0:y1, x0:x1]
                        logical_bytes += ct.nbytes + flaw.nbytes
                    raw_positive = float(np.mean(ct > 0))
                    flaw_count = int(np.count_nonzero(flaw))
                    if raw_positive >= MIN_RAW_POSITIVE_PROXY:
                        candidate_y = int(flaw_count > 0)
                    else:
                        flags.append("low_raw_xct_positive_proxy_candidate_unknown")
                else:
                    flags.append("xct_candidate_bounds_outside_array")
                sample_crop = samples[y:y+PATCH, x:x+PATCH]
                sample_ids = [int(value) for value in np.unique(sample_crop)]
                row.update(feature_row=len(records), candidate_y=candidate_y, candidate_flaw_pixels=flaw_count,
                           raw_xct_positive_proxy=raw_positive, sample_template_nonzero_fraction=float(np.mean(sample_crop > 0)),
                           sample_template_ids=";".join(map(str, sample_ids)), quality_flags=";".join(flags),
                           candidate_target_status="unknown_proxy_or_bounds" if candidate_y == -1 else "provisional_nonzero_annotation_rule")
                images.append(np.stack([image.astype(np.float32) / divisor for image, divisor in zip(raw_images, (255., 255., 65535.))]))
                records.append(row)
            part_summaries.append({"part_id": part_id, "part_name": name_for(part_id), "grid_candidates": grid_count,
                                   "geometry_selected": len(candidates), "retained": len(records)-retained_before,
                                   "quarantined": len(quarantine)-quarantined_before})
            del raw_tile, flaw_tile, sensor_tiles
            print(f"Layer {args.layer}, P{part_id}: {len(records)-retained_before} prepared; {len(quarantine)-quarantined_before} quarantined", flush=True)
        source_dtypes = {ds.name: str(ds.dtype) for ds in [part_ds, sample_ds, ct_ds, flaw_ds, *sensors]}
    X = np.stack(images).astype(np.float32, copy=False) if images else np.empty((0, 3, PATCH, PATCH), dtype=np.float32)
    with (out / "features.npz").open("xb") as handle:
        np.savez_compressed(handle, X=X, candidate_y=np.array([r["candidate_y"] for r in records], dtype=np.int8),
                            groups=np.array([r["part_id"] for r in records], dtype=np.int32),
                            layers=np.full(len(records), args.layer, dtype=np.int32),
                            coords=np.array([[r["camera_y"], r["camera_x"]] for r in records], dtype=np.int32).reshape(-1, 2),
                            label_validated=np.zeros(len(records), dtype=bool), coverage_validated=np.zeros(len(records), dtype=bool))
    write_csv(out / "manifest.csv", records)
    write_csv(out / "quarantine.csv", quarantine)
    write_csv(out / "geometry_scope_excluded.csv", scope_excluded)
    after = raw.stat()
    preserved = (before.st_size, before.st_mtime_ns) == (after.st_size, after.st_mtime_ns)
    flags = Counter(flag for row in records for flag in row["quality_flags"].split(";") if flag)
    summary = {"created_utc": datetime.now(timezone.utc).isoformat(), "layer": args.layer, "rows": len(records),
               "source_file": str(raw), "source_dtypes": source_dtypes, "raw_open_mode": "r",
               "source_size_bytes": before.st_size, "source_mtime_ns": before.st_mtime_ns, "raw_size_and_mtime_unchanged": preserved,
               "discovered_parts": [{"part_id": ident, "name": name_for(ident)} for ident in discovered],
               "selected_parts": selected, "out_of_scope_parts": [{"part_id": ident, "name": name_for(ident)} for ident in discovered if ident not in selected],
               "requested_but_absent_ids": sorted(requested - set(discovered)), "sample_name_lookup": sample_names,
               "part_summary": part_summaries, "geometry_scope_excluded": len(scope_excluded), "quarantined": len(quarantine),
               "candidate_label_counts": dict(Counter(str(row["candidate_y"]) for row in records)), "quality_flag_counts": dict(flags),
               "feature_shape": list(X.shape), "feature_bytes": X.nbytes, "logical_array_bytes_read": logical_bytes,
               "io_note": "Logical selected arrays only; HDF5 chunk decompression reads more bytes. No whole CT layer/volume loaded.",
               "cache_note": "32 MiB cache per open dataset; seven dataset handles; bounded working set designed below about 500 MiB, not a measured RSS guarantee.",
               "elapsed_seconds": round(time.monotonic()-started, 3), "source_scope": "AMMTO Fatigue Bar names present in one layer unless explicit IDs supplied",
               "parameters": {"patch_size": PATCH, "minimum_part_fraction": MIN_PART_FRACTION, "raw_positive_proxy_threshold": MIN_RAW_POSITIVE_PROXY,
                              "visible_divisor": 255, "nir_divisor": 65535, "mapping": "dimension ratio with round boundaries; candidate only"},
               "ready_for_model_training": False, "final_y_exported": False, "scientific_limit": "Raw-positive XCT proxy is not validated measured coverage; candidate_y 0 is not a certified physical negative."}
    summary["script_sha256"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    summary["source_layer_note"] = layer_note
    with (out / "summary.json").open("x", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2, allow_nan=False)
    with (out / "README.md").open("x", encoding="utf-8") as handle:
        handle.write("# Prepared Snow sensor layer\n\nThis shard is source-data preparation, not validated defect ground truth. "
                     "The feature array has three sensor channels, using the unchanged pilot normalization. "
                     "candidate_y is -1 for low XCT intensity proxy or invalid bounds; otherwise it follows the provisional nonzero-annotation rule. "
                     "There is no final y target. label_validated and coverage_validated are false for every row. "
                     "Constant channels, stored-maximum endpoints and exact duplicates are flagged and retained. "
                     "Only structurally invalid/nonfinite/all-three-zero sensor patches are quarantined. "
                     "Geometry-scope filtering reuses the pilot's 0.75 part-fraction rule; default source objects are named AMMTO Fatigue Bars. "
                     "Sample templates describe nominal geometry and do not validate measured XCT support. See manifest.csv and summary.json.\n")
    print(json.dumps({key: summary[key] for key in ("layer", "rows", "quarantined", "candidate_label_counts", "elapsed_seconds", "logical_array_bytes_read", "raw_size_and_mtime_unchanged")}, indent=2))
    if not preserved:
        raise RuntimeError("Raw source size/mtime changed; inspect before accepting shard")


if __name__ == "__main__":
    main()
