"""Reproduce pilot crops and measure sensitivity without changing source data.

The dimension-ratio transform is a candidate, not a validated registration.
Outputs are diagnostics and must not be used as final training labels.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import time
from collections import Counter, defaultdict
from pathlib import Path

import h5py
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


METHODS = ("pilot_round", "audit_floor_ceil", "export_floor")
RAW_NAME = "2024-05-01 M2 AMMTO Fatigue Blanks 05.hdf5"


def crop_bounds(y, x, size, scale_y, scale_x, method):
    """Half-open pixel boundaries; Python round reproduces the original pilot."""
    values = (y * scale_y, (y + size) * scale_y,
              x * scale_x, (x + size) * scale_x)
    if method == "pilot_round":
        return tuple(round(value) for value in values)
    if method == "audit_floor_ceil":
        return (math.floor(values[0]), math.ceil(values[1]),
                math.floor(values[2]), math.ceil(values[3]))
    if method == "export_floor":
        return tuple(math.floor(value) for value in values)
    raise ValueError(f"Unknown crop method: {method}")


def write_json(path, value):
    with path.open("x", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, allow_nan=False)


def write_csv(path, rows):
    if not rows:
        return
    with path.open("x", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def outline(ax, array, extent, color, label):
    mask = np.asarray(array, dtype=float)
    if mask.min() != mask.max():
        ax.contour(mask, levels=[0.5], origin="lower", extent=extent,
                   colors=[color], linewidths=1.0)
    ax.plot([], [], color=color, label=label)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    out = args.output.resolve()
    if not out.is_relative_to(root):
        raise ValueError("Diagnostic output must stay inside the project")
    if out.exists():
        raise FileExistsError(f"Refusing to overwrite output directory: {out}")
    raw_path = root / "data/raw" / RAW_NAME
    manifest_path = root / "data/processed/snow_pilot_manifest.csv"
    pilot_path = root / "data/processed/snow_pilot_patches.npz.npz"
    if not pilot_path.exists():
        pilot_path = root / "data/processed/snow_pilot_patches.npz"
    raw_stat_before = raw_path.stat()
    with manifest_path.open(newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    with np.load(pilot_path, allow_pickle=False) as archive:
        X = archive["X"]
        original_y = archive["y"]
        original_groups = archive["groups"]
        original_layers = archive["layers"]
    if len(rows) != len(X):
        raise ValueError("Manifest and feature counts disagree")
    if not (np.array_equal(original_y, [int(r["label"]) for r in rows])
            and np.array_equal(original_groups, [int(r["part_id"]) for r in rows])
            and np.array_equal(original_layers, [int(r["layer"]) for r in rows])):
        raise ValueError("Pilot and manifest rows are not aligned")
    out.mkdir(parents=True)
    records = [None] * len(rows)
    grouped = defaultdict(list)
    for index, row in enumerate(rows):
        grouped[(int(row["layer"]), int(row["part_id"]))].append((index, row))
    footprints = []
    figures = []
    observed_flaw_values = set()
    start = time.monotonic()
    logical_read_bytes = 0

    with h5py.File(raw_path, "r", rdcc_nbytes=128 * 1024**2,
                   rdcc_nslots=10007) as handle:
        part_ds = handle["/slices/part_ids"]
        sample_ds = handle["/slices/sample_ids"]
        ct_ds = handle["/slices/registered_data/x-ray_ct_data"]
        flaw_ds = handle["/slices/registered_data/x-ray_ct_flaw"]
        sensor_datasets = [handle[path] for path in (
            "/slices/camera_data/visible/0", "/slices/camera_data/visible/1",
            "/slices/camera_data/nir/1")]
        sy = ct_ds.shape[1] / part_ds.shape[1]
        sx = ct_ds.shape[2] / part_ds.shape[2]
        if ct_ds.shape != flaw_ds.shape:
            raise ValueError("XCT grayscale and flaw grids disagree")
        for layer in sorted({key[0] for key in grouped}):
            parts = part_ds[layer]
            samples = sample_ds[layer]
            logical_read_bytes += parts.nbytes + samples.nbytes
            for part_id in sorted(p for l, p in grouped if l == layer):
                members = grouped[(layer, part_id)]
                all_bounds = [crop_bounds(int(r["camera_y"]), int(r["camera_x"]),
                                          int(r["patch_size"]), sy, sx, method)
                              for _, r in members for method in METHODS]
                ty0 = min(b[0] for b in all_bounds)
                ty1 = max(b[1] for b in all_bounds)
                tx0 = min(b[2] for b in all_bounds)
                tx1 = max(b[3] for b in all_bounds)
                if not (0 <= ty0 < ty1 <= ct_ds.shape[1]
                        and 0 <= tx0 < tx1 <= ct_ds.shape[2]):
                    raise ValueError("An XCT crop falls outside the grid")
                raw_tile = ct_ds[layer, ty0:ty1, tx0:tx1]
                flaw_tile = flaw_ds[layer, ty0:ty1, tx0:tx1]
                observed_flaw_values.update(int(v) for v in np.unique(flaw_tile))
                logical_read_bytes += raw_tile.nbytes + flaw_tile.nbytes
                by0 = min(int(r["camera_y"]) for _, r in members)
                by1 = max(int(r["camera_y"]) + int(r["patch_size"]) for _, r in members)
                bx0 = min(int(r["camera_x"]) for _, r in members)
                bx1 = max(int(r["camera_x"]) + int(r["patch_size"]) for _, r in members)
                sensor_tiles = [ds[layer, by0:by1, bx0:bx1] for ds in sensor_datasets]
                logical_read_bytes += sum(t.nbytes for t in sensor_tiles)
                footprint_ids, footprint_counts = np.unique(samples[parts == part_id], return_counts=True)
                footprints.append({"layer": layer, "part_id": part_id,
                                   "part_pixels": int(np.count_nonzero(parts == part_id)),
                                   "sample_ids_within_part": json.dumps(dict(zip(
                                       footprint_ids.astype(int).tolist(), footprint_counts.astype(int).tolist())))})
                for index, row in members:
                    y, x, size = (int(row[name]) for name in ("camera_y", "camera_x", "patch_size"))
                    part_crop = parts[y:y+size, x:x+size]
                    sample_crop = samples[y:y+size, x:x+size]
                    ids = np.unique(sample_crop)
                    record = {"pilot_row": index, "layer": layer, "part_id": part_id,
                              "camera_y": y, "camera_x": x, "patch_size": size,
                              "original_label": int(row["label"]),
                              "original_flaw_pixels": int(row["flaw_pixels"]),
                              "part_fraction_recomputed": float(np.mean(part_crop == part_id)),
                              "sample_template_nonzero_fraction": float(np.mean(sample_crop != 0)),
                              "sample_template_ids": ";".join(str(int(v)) for v in ids),
                              "mapping_status": "candidate_dimension_ratio_unvalidated",
                              "coverage_status": "raw_positive_proxy_not_validated_coverage"}
                    errors = []
                    for channel, (tile, divisor) in enumerate(zip(sensor_tiles, (255.0, 255.0, 65535.0))):
                        source = tile[y-by0:y-by0+size, x-bx0:x-bx0+size].astype(np.float32) / divisor
                        errors.append(float(np.max(np.abs(source - X[index, channel]))))
                    record["raw_sensor_max_abs_error"] = max(errors)
                    for method in METHODS:
                        y0, y1, x0, x1 = crop_bounds(y, x, size, sy, sx, method)
                        raw_crop = raw_tile[y0-ty0:y1-ty0, x0-tx0:x1-tx0]
                        flaw_crop = flaw_tile[y0-ty0:y1-ty0, x0-tx0:x1-tx0]
                        count = int(np.count_nonzero(flaw_crop))
                        for name, value in zip(("y0", "y1", "x0", "x1"), (y0, y1, x0, x1)):
                            record[f"{method}_{name}"] = value
                        record[f"{method}_flaw_pixels"] = count
                        record[f"{method}_label"] = int(count > 0)
                        record[f"{method}_raw_positive_fraction"] = float(np.mean(raw_crop > 0))
                    record["round_count_matches_original"] = int(record["pilot_round_flaw_pixels"] == int(row["flaw_pixels"]))
                    record["crop_label_disagreement"] = int(len({record[f"{m}_label"] for m in METHODS}) > 1)
                    records[index] = record

                # Independent masks are displayed, but all cross-grid overlays still use the candidate transform.
                if layer in (540, 600, 640) and part_id in (2, 16, 24):
                    yy, xx = np.where(parts == part_id)
                    fy0, fy1 = max(0, int(yy.min())-20), min(parts.shape[0], int(yy.max())+21)
                    fx0, fx1 = max(0, int(xx.min())-20), min(parts.shape[1], int(xx.max())+21)
                    qy0, qy1, qx0, qx1 = crop_bounds(fy0, fx0, 1, sy, sx, "pilot_round")
                    qy1, qx1 = round(fy1*sy), round(fx1*sx)
                    visible = sensor_datasets[0][layer, fy0:fy1, fx0:fx1]
                    ct = ct_ds[layer, qy0:qy1, qx0:qx1]
                    flaw = flaw_ds[layer, qy0:qy1, qx0:qx1]
                    logical_read_bytes += visible.nbytes + ct.nbytes + flaw.nbytes
                    cextent = (fx0, fx1, fy0, fy1)
                    texent = (qx0/sx, qx1/sx, qy0/sy, qy1/sy)
                    fig, axes = plt.subplots(1, 3, figsize=(14, 4.7), layout="constrained")
                    axes[0].imshow(visible, origin="lower", extent=cextent, cmap="gray", vmin=0, vmax=255)
                    nonzero = ct[ct > 0]
                    lo, hi = np.percentile(nonzero, [2, 98]) if nonzero.size else (0, 1)
                    axes[1].imshow(ct, origin="lower", extent=texent, cmap="gray", vmin=lo, vmax=max(hi, lo+1))
                    axes[2].imshow(flaw > 0, origin="lower", extent=texent, cmap="binary", vmin=0, vmax=1)
                    for ax in axes:
                        outline(ax, parts[fy0:fy1, fx0:fx1] == part_id, cextent, "#1864ab", "Part template")
                        outline(ax, samples[fy0:fy1, fx0:fx1] > 0, cextent, "#d17b00", "Sample template")
                        ax.set_xlim(fx0, fx1)
                        ax.set_ylim(fy0, fy1)
                        ax.set_xlabel("Camera-grid X (pixel boundary)")
                        ax.set_ylabel("Camera-grid Y (pixel boundary)")
                    for ax, title in zip(axes, ("Visible post-melt", "XCT grayscale", "Nonzero XCT flaw annotation")):
                        ax.set_title(title)
                    axes[0].legend(loc="upper right", fontsize=8)
                    fig.suptitle(f"P{part_id}, layer {layer}: candidate scale mapping; physical registration unvalidated", fontsize=12)
                    name = f"candidate_P{part_id}_layer{layer}.png"
                    fig.savefig(out/name, dpi=160, facecolor="white")
                    plt.close(fig)
                    figures.append(name)
            print(f"Compared all candidate crops for layer {layer}", flush=True)

    summary = {"status": "diagnostics_complete_scientific_validation_pending",
               "mapping": {"name": "dimension_ratio", "scale_y": sy, "scale_x": sx,
                           "validation": "not established by crop agreement or overlays"},
               "rows": len(records), "elapsed_seconds": round(time.monotonic()-start, 2),
               "logical_array_bytes_read": logical_read_bytes,
               "io_note": "Selected arrays only; HDF5 chunks decompress additional bytes, not measured here.",
               "pilot_count_mismatches": sum(not r["round_count_matches_original"] for r in records),
               "raw_sensor_rows_not_exactly_reproduced": sum(r["raw_sensor_max_abs_error"] != 0 for r in records),
               "raw_sensor_max_abs_error": max(r["raw_sensor_max_abs_error"] for r in records),
               "label_disagreement_rows": sum(r["crop_label_disagreement"] for r in records),
               "sample_template_fraction_range": [min(r["sample_template_nonzero_fraction"] for r in records),
                                                  max(r["sample_template_nonzero_fraction"] for r in records)],
               "sampled_flaw_values": sorted(observed_flaw_values), "methods": {},
               "figures": figures,
               "source_manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest()}
    for method in METHODS:
        changed = [r for r in records if r[f"{method}_label"] != r["original_label"]]
        summary["methods"][method] = {
            "positive_labels": sum(r[f"{method}_label"] for r in records),
            "labels_changed_from_pilot": len(changed),
            "negative_to_positive": sum(r["original_label"] == 0 for r in changed),
            "positive_to_negative": sum(r["original_label"] == 1 for r in changed),
            "flaw_counts_changed_from_pilot": sum(r[f"{method}_flaw_pixels"] != r["original_flaw_pixels"] for r in records),
            "raw_positive_fraction_range": [min(r[f"{method}_raw_positive_fraction"] for r in records),
                                            max(r[f"{method}_raw_positive_fraction"] for r in records)]}
    after = raw_path.stat()
    summary["raw_size_and_mtime_unchanged"] = (raw_stat_before.st_size == after.st_size and raw_stat_before.st_mtime_ns == after.st_mtime_ns)
    write_csv(out / "candidate_crop_comparison.csv", records)
    write_csv(out / "sample_template_by_specimen_layer.csv", footprints)
    write_csv(out / "label_disagreements.csv", [r for r in records if r["crop_label_disagreement"]])
    write_json(out / "summary.json", summary)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
