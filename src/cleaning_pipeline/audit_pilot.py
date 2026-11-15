"""Read-only pilot-file audit; never changes inputs or selects scientific labels.

Run from any working directory with explicit --root and a NEW --output directory.
The output folder must not already exist, protecting earlier audit results.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.metadata
import json
import platform
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

CHANNELS = ["Visible post-melt", "Visible post-recoat", "NIR integrated max"]
INTEGER_FIELDS = ["layer", "part_id", "camera_y", "camera_x", "patch_size", "flaw_pixels", "label"]
FLOAT_FIELDS = ["part_fraction", "ct_coverage"]
THRESHOLDS = [1, 5, 10, 25, 50, 100]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, value: object) -> None:
    with path.open("x", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, allow_nan=False)
        handle.write("\n")


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        return
    with path.open("x", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def summarize(values: np.ndarray) -> dict:
    finite = values[np.isfinite(values)]
    if not finite.size:
        return {"finite_count": 0}
    quantiles = np.quantile(finite, [0, 0.01, 0.25, 0.5, 0.75, 0.99, 1])
    return {
        "finite_count": int(finite.size),
        "mean": float(finite.mean()),
        "std": float(finite.std()),
        "quantiles": dict(zip(["min", "p01", "p25", "median", "p75", "p99", "max"], map(float, quantiles))),
    }


def correlation(left: np.ndarray, right: np.ndarray) -> float | None:
    a = left.astype(np.float64).ravel()
    b = right.astype(np.float64).ravel()
    a -= a.mean()
    b -= b.mean()
    denominator = float(np.linalg.norm(a) * np.linalg.norm(b))
    if denominator == 0 or not np.isfinite(denominator):
        return None
    return float(np.dot(a, b) / denominator)


def audit(root: Path, output: Path) -> dict:
    root = root.resolve(strict=True)
    output = output.resolve()
    manifest_path = root / "data/processed/snow_pilot_manifest.csv"
    archive_candidates = sorted((root / "data/processed").glob("snow_pilot_patches*.npz*"))
    if len(archive_candidates) != 1:
        raise ValueError(f"Expected exactly one pilot archive; found {archive_candidates}")
    archive_path = archive_candidates[0]
    source_before = {str(path): sha256(path) for path in (archive_path, manifest_path)}
    if output == root or root in output.parents and any(name in output.relative_to(root).parts for name in ("raw", "processed")):
        raise ValueError("Output must be a new audit folder outside raw/processed inputs")
    output.mkdir(parents=True, exist_ok=False)

    with np.load(archive_path, allow_pickle=False) as archive:
        arrays = {name: archive[name] for name in archive.files}
    required = {"X", "y", "groups", "layers"}
    if not required.issubset(arrays):
        raise ValueError(f"Missing required pilot arrays: {sorted(required - arrays.keys())}")
    X, y, groups, layers = (arrays[name] for name in ("X", "y", "groups", "layers"))
    with manifest_path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        columns = reader.fieldnames or []
        raw_records = list(reader)
    missing_columns = sorted(set(INTEGER_FIELDS + FLOAT_FIELDS) - set(columns))
    if missing_columns:
        raise ValueError(f"Missing manifest columns: {missing_columns}")
    records = []
    for number, raw in enumerate(raw_records, 2):
        row = {}
        for field in INTEGER_FIELDS:
            value = float(raw[field])
            if not np.isfinite(value) or not value.is_integer():
                raise ValueError(f"Manifest row {number}: {field} is not a finite integer")
            row[field] = int(value)
        for field in FLOAT_FIELDS:
            value = float(raw[field])
            if not np.isfinite(value):
                raise ValueError(f"Manifest row {number}: {field} is nonfinite")
            row[field] = value
        records.append(row)

    n = len(records)
    checks = []
    def check(name: str, passed: bool, evidence: object, scope: str = "internal consistency") -> None:
        checks.append({"check": name, "status": "pass" if passed else "fail", "scope": scope, "evidence": evidence})

    check("array_and_manifest_row_counts", all(array.shape[0] == n for array in (X, y, groups, layers)),
          {"manifest": n, **{name: int(arrays[name].shape[0]) for name in required}})
    check("expected_pilot_shape", X.shape == (2024, 3, 24, 24), list(X.shape), "handoff expectation")
    check("target_vector_shape", y.shape == (n,) and groups.shape == (n,) and layers.shape == (n,),
          {name: list(arrays[name].shape) for name in ("y", "groups", "layers")})
    if X.ndim != 4 or X.shape[1] != 3 or not all(array.shape[0] == n for array in (X, y, groups, layers)):
        raise ValueError("Unexpected pilot dimensions prevent aligned per-row checks")
    expected = {"y": np.array([r["label"] for r in records]), "groups": np.array([r["part_id"] for r in records]),
                "layers": np.array([r["layer"] for r in records])}
    alignment = {}
    for name, values in expected.items():
        mismatches = np.flatnonzero(arrays[name] != values)
        alignment[name] = int(mismatches.size)
        check(f"manifest_{name}_alignment", not mismatches.size, {"mismatch_rows": int(mismatches.size), "first_row_indices": mismatches[:10].tolist()})
    check("binary_target_values", bool(np.isin(y, [0, 1]).all()), np.unique(y).tolist())
    check("all_image_values_finite", bool(np.isfinite(X).all()), {"nan": int(np.isnan(X).sum()), "inf": int(np.isinf(X).sum())})

    keys = [(r["layer"], r["part_id"], r["camera_y"], r["camera_x"], r["patch_size"]) for r in records]
    duplicates = sum(count - 1 for count in Counter(keys).values() if count > 1)
    check("unique_coordinate_keys", duplicates == 0, {"duplicate_rows_beyond_first": duplicates, "key": ["layer", "part_id", "camera_y", "camera_x", "patch_size"]})
    digests = [hashlib.sha256(np.ascontiguousarray(patch).tobytes()).hexdigest() for patch in X]
    image_duplicates = sum(count - 1 for count in Counter(digests).values() if count > 1)
    check("no_exact_duplicate_image_content", image_duplicates == 0, {"duplicate_rows_beyond_first": image_duplicates, "method": "SHA256 of three-channel float32 patch bytes"})
    empty = np.flatnonzero(np.all(X == 0, axis=(1, 2, 3)))
    constant = np.flatnonzero(np.ptp(X, axis=(1, 2, 3)) == 0)
    check("no_completely_zero_image_patches", empty.size == 0, {"rows": int(empty.size), "first_row_indices": empty[:10].tolist()})
    check("no_whole_patch_constant_images", constant.size == 0, {"rows": int(constant.size), "first_row_indices": constant[:10].tolist()})
    label_rule_mismatches = [i for i, r in enumerate(records) if r["label"] != int(r["flaw_pixels"] > 0)]
    check("stored_flaw_pixel_target_rule", not label_rule_mismatches, {"mismatch_rows": len(label_rule_mismatches)}, "stored >0 rule only, not scientific correctness")
    bounds_bad = [i for i, r in enumerate(records) if not (0 <= r["part_fraction"] <= 1 and 0 <= r["ct_coverage"] <= 1)]
    check("fractions_in_unit_interval", not bounds_bad, {"invalid_rows": len(bounds_bad)})
    threshold_bad = [i for i, r in enumerate(records) if r["part_fraction"] < .75 or r["ct_coverage"] < .5]
    check("stored_pilot_inclusion_thresholds", not threshold_bad, {"invalid_rows": len(threshold_bad)}, "project-defined heuristics only")
    geometry_bad = [i for i, r in enumerate(records) if r["layer"] < 0 or r["camera_y"] < 0 or r["camera_x"] < 0 or r["patch_size"] != X.shape[-1] or r["flaw_pixels"] < 0]
    check("nonnegative_coordinates_counts_and_patch_sizes", not geometry_bad, {"invalid_rows": len(geometry_bad)})

    per_specimen, per_layer, per_specimen_layer = [], [], []
    for field, target in (("part_id", per_specimen), ("layer", per_layer)):
        for value in sorted({r[field] for r in records}):
            chosen = [r for r in records if r[field] == value]
            positive = sum(r["label"] for r in chosen)
            target.append({field: value, "patches": len(chosen), "positive": positive, "negative": len(chosen) - positive,
                           "positive_fraction": positive / len(chosen)})
    for part in sorted({r["part_id"] for r in records}):
        for layer in sorted({r["layer"] for r in records}):
            chosen = [r for r in records if r["part_id"] == part and r["layer"] == layer]
            positive = sum(r["label"] for r in chosen)
            per_specimen_layer.append({"part_id": part, "layer": layer, "patches": len(chosen), "positive": positive,
                                       "negative": len(chosen) - positive, "positive_fraction": positive / len(chosen) if chosen else None})
    write_csv(output / "per_specimen.csv", per_specimen)
    write_csv(output / "per_layer.csv", per_layer)
    write_csv(output / "per_specimen_layer.csv", per_specimen_layer)

    channel_stats = []
    for channel, name in enumerate(CHANNELS):
        values = X[:, channel]
        item = {"channel": name, **summarize(values), "zero_pixels": int(np.count_nonzero(values == 0)),
                "one_pixels": int(np.count_nonzero(values == 1)), "outside_zero_one_pixels": int(np.count_nonzero((values < 0) | (values > 1))),
                "all_zero_channel_patches": int(np.count_nonzero(np.all(values == 0, axis=(1, 2)))),
                "constant_channel_patches": int(np.count_nonzero(np.ptp(values, axis=(1, 2)) == 0)),
                "zero_pixel_fraction": float(np.mean(values == 0)), "one_pixel_fraction": float(np.mean(values == 1))}
        channel_stats.append(item)
    check("normalized_input_values_in_zero_one", all(r["outside_zero_one_pixels"] == 0 for r in channel_stats),
          {r["channel"]: r["outside_zero_one_pixels"] for r in channel_stats}, "consistency with existing integer-divisor normalization")
    sample_quality = []
    for index, row in enumerate(records):
        item = {"row_index": index, **{field: row[field] for field in ("part_id", "layer", "camera_y", "camera_x", "patch_size", "label")},
                "any_nonfinite": not bool(np.isfinite(X[index]).all()), "all_channels_zero": bool(np.all(X[index] == 0))}
        for channel in range(3):
            values = X[index, channel]
            item[f"channel_{channel}_constant"] = bool(np.ptp(values) == 0)
            item[f"channel_{channel}_zero_fraction"] = float(np.mean(values == 0))
            item[f"channel_{channel}_stored_max_fraction"] = float(np.mean(values == 1))
        item["constant_channel_review_flag"] = any(item[f"channel_{channel}_constant"] for channel in range(3))
        sample_quality.append(item)
    write_csv(output / "sample_channel_quality.csv", sample_quality)
    flagged_channel_samples = [row for row in sample_quality if row["constant_channel_review_flag"] or row["any_nonfinite"] or row["all_channels_zero"]]
    write_json(output / "channel_review_flags.json", {
        "interpretation": "Review flags only; no samples removed. Stored maximum (normalized 1.0) is an endpoint statistic, not proof of physical sensor saturation.",
        "samples": flagged_channel_samples,
    })

    flaw_counts = np.array([r["flaw_pixels"] for r in records])
    sensitivity = []
    for threshold in THRESHOLDS:
        positive = int(np.count_nonzero(flaw_counts >= threshold))
        sensitivity.append({"minimum_flaw_pixels": threshold, "positive": positive, "negative": n - positive,
                            "positive_fraction": positive / n, "label_changes_from_ge1": int(np.count_nonzero((flaw_counts >= threshold) != (flaw_counts >= 1)))})
    write_csv(output / "threshold_sensitivity.csv", sensitivity)

    by_location = defaultdict(list)
    for index, row in enumerate(records):
        by_location[(row["part_id"], row["camera_y"], row["camera_x"], row["patch_size"])].append(index)
    pairs = []
    for key, indices in by_location.items():
        indices.sort(key=lambda i: records[i]["layer"])
        for first, second in zip(indices, indices[1:]):
            a, b = records[first], records[second]
            pair = {"part_id": key[0], "camera_y": key[1], "camera_x": key[2], "first_row_index": first,
                    "second_row_index": second, "first_layer": a["layer"], "second_layer": b["layer"],
                    "layer_index_gap": b["layer"] - a["layer"],
                    "rmse_three_channels": float(np.sqrt(np.mean((X[first].astype(np.float64) - X[second]) ** 2)))}
            for channel in range(3):
                pair[f"pearson_channel_{channel}"] = correlation(X[first, channel], X[second, channel])
            pairs.append(pair)
    write_csv(output / "same_location_adjacent_selected_layers.csv", pairs)
    dependence = {"pair_count": len(pairs), "interpretation": "Consecutive sampled layers at repeated camera coordinates within one specimen; descriptive correlation only. No samples excluded.",
                  "rmse": summarize(np.array([p["rmse_three_channels"] for p in pairs])) if pairs else None}
    for channel in range(3):
        values = np.array([p[f"pearson_channel_{channel}"] for p in pairs if p[f"pearson_channel_{channel}"] is not None])
        dependence[f"channel_{channel}_pearson"] = summarize(values) if values.size else None

    # A leave-one-specimen-out inventory is planning only; no split is chosen and no model is trained.
    split_planning = []
    for row in per_specimen:
        split_planning.append({"hypothetical_held_out_specimen": row["part_id"], "held_out_patches": row["patches"],
                               "held_out_positive": row["positive"], "held_out_negative": row["negative"],
                               "remaining_patches": n - row["patches"], "remaining_positive": int(y.sum()) - row["positive"],
                               "status": "planning_only_not_an_assigned_split"})
    write_csv(output / "specimen_holdout_planning.csv", split_planning)

    # Publication-style static diagnostics; all targets are explicitly provisional.
    plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False})
    fig, ax = plt.subplots(figsize=(9, 5), constrained_layout=True)
    positions = np.arange(len(per_specimen))
    ax.bar(positions, [r["negative"] for r in per_specimen], color="#4C78A8", label="Provisional label 0")
    ax.bar(positions, [r["positive"] for r in per_specimen], bottom=[r["negative"] for r in per_specimen], color="#E45756", label="Provisional label 1")
    ax.set_xticks(positions, [f"P{r['part_id']}" for r in per_specimen])
    ax.set_ylabel("Pilot patches")
    ax.set_title("Pilot class balance differs strongly between specimens")
    ax.set_ylim(0, max(r["patches"] for r in per_specimen) * 1.24)
    ax.legend(loc="upper right", frameon=False)
    fig.savefig(output / "pilot_label_distribution.png", dpi=160)
    plt.close(fig)
    fig, ax = plt.subplots(figsize=(8, 4.5), constrained_layout=True)
    ax.bar([str(r["minimum_flaw_pixels"]) for r in sensitivity], [r["positive"] for r in sensitivity], color="#E45756")
    for position, row in enumerate(sensitivity):
        ax.text(position, row["positive"] + 12, str(row["positive"]), ha="center", fontsize=9)
    ax.set_ylim(0, max(r["positive"] for r in sensitivity) * 1.15)
    ax.set_xlabel("Minimum nonzero flaw-mask pixels per patch (sensitivity only)")
    ax.set_ylabel("Patches assigned provisional label 1")
    ax.set_title("Threshold choice changes provisional targets; no threshold selected")
    fig.savefig(output / "threshold_sensitivity.png", dpi=160)
    plt.close(fig)
    fig, axes = plt.subplots(1, 3, figsize=(12, 4), constrained_layout=True)
    for channel, ax in enumerate(axes):
        ax.hist(X[:, channel].ravel(), bins=np.linspace(0, 1, 81), color=["#4C78A8", "#72B7B2", "#F58518"][channel])
        ax.set_yscale("log")
        ax.set_xlabel("Existing normalized pixel value")
        ax.set_title(CHANNELS[channel])
    axes[0].set_ylabel("Pixel count (log scale)")
    fig.suptitle("Stored sensor-channel distributions; no preprocessing changed")
    fig.savefig(output / "channel_distributions.png", dpi=160)
    plt.close(fig)

    source_after = {str(path): sha256(path) for path in (archive_path, manifest_path)}
    check("input_sha256_unchanged", source_before == source_after, {"before": source_before, "after": source_after}, "input preservation")
    warning_items = [
        {"severity": "high", "finding": "Physical registration and XCT coverage semantics are outside this file-only audit and remain unverified."},
        {"severity": "high", "finding": "Patch labels are project-derived >0 flaw-mask targets, not validated author-provided binary ground truth."},
        {"severity": "high", "finding": "Eight specimens in one build with selected layers are dependent samples. Hold out whole specimens for later evaluation; cross-build generalization is untested."},
        {"severity": "medium", "finding": "All pilot ct_coverage values are 1.0; this metric cannot discriminate samples here and nonzero grayscale is not independently verified observation coverage."},
        {"severity": "low", "finding": f"Pilot archive has actual filename {archive_path.name}; loaded as-is without renaming."},
    ]
    if flagged_channel_samples:
        warning_items.append({"severity": "medium", "finding": f"{len(flagged_channel_samples)} patch(es) have a constant sensor channel or nonfinite/empty data; inspect channel_review_flags.json. No patch excluded."})
    summary = {
        "created_utc": datetime.now(timezone.utc).isoformat(), "purpose": "Read-only internal-consistency audit of existing provisional pilot",
        "root": str(root), "output": str(output), "command_arguments": sys.argv,
        "environment": {"python": platform.python_version(), "numpy": np.__version__, "matplotlib": matplotlib.__version__},
        "script_sha256": sha256(Path(__file__)), "source_sha256_before": source_before, "source_sha256_after": source_after,
        "arrays": {name: {"shape": list(array.shape), "dtype": str(array.dtype)} for name, array in arrays.items()},
        "manifest_columns": columns, "rows": n, "positive": int(np.count_nonzero(y == 1)), "negative": int(np.count_nonzero(y == 0)),
        "checks": checks, "checks_passed": sum(r["status"] == "pass" for r in checks), "checks_failed": sum(r["status"] == "fail" for r in checks),
        "per_specimen": per_specimen, "per_layer": per_layer, "channel_stats": channel_stats,
        "channel_review_flag_samples": flagged_channel_samples,
        "part_fraction": summarize(np.array([r["part_fraction"] for r in records])),
        "ct_coverage": summarize(np.array([r["ct_coverage"] for r in records])),
        "flaw_pixels": summarize(flaw_counts), "threshold_sensitivity": sensitivity, "same_location_layer_dependence": dependence,
        "warnings": warning_items, "ready_for_model_training": False,
        "scientific_validation": "not established by internal consistency checks; see separate registration and coverage diagnostics",
    }
    write_json(output / "pilot_audit.json", summary)
    write_csv(output / "checks.csv", [{"check": item["check"], "status": item["status"], "scope": item["scope"], "evidence": json.dumps(item["evidence"])} for item in checks])
    lines = ["# Pilot file audit", "", "This is an internal-consistency audit of provisional labels, not a validation of physical registration.", "",
             f"- Patches: {n}; provisional positive: {summary['positive']}; provisional negative: {summary['negative']}.",
             f"- Checks passed: {summary['checks_passed']}; failed: {summary['checks_failed']}.",
             f"- Input archive and manifest SHA256 unchanged: {source_before == source_after}.",
             f"- Consecutive sampled-layer pairs at repeated specimen/camera locations: {len(pairs)}.", "",
             "## Important limits", ""]
    lines += [f"- {item['finding']}" for item in warning_items]
    lines += ["", "## Reproduce", "", "Use a new output directory on every run:", "", "```powershell",
              f"& '{sys.executable}' -B '{Path(__file__).resolve()}' --root '{root}' --output '<NEW audit output directory>'", "```", ""]
    with (output / "pilot_audit.md").open("x", encoding="utf-8") as handle:
        handle.write("\n".join(lines))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True, help="A NEW directory; existing directories are refused")
    args = parser.parse_args()
    summary = audit(args.root, args.output)
    print(json.dumps({key: summary[key] for key in ("output", "rows", "positive", "negative", "checks_passed", "checks_failed", "ready_for_model_training")}, indent=2))
    if summary["checks_failed"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
