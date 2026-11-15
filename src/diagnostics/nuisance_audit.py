"""Development-only location/layer controls; no held-out scores or raw HDF5 reads.

The new controls are diagnostic comparators, not sensor-model replacements and
not evidence of a causal confound. Metadata enters only these named controls.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import sys
import time
import warnings
from datetime import datetime, timezone
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import sklearn
from sklearn.ensemble import RandomForestClassifier
from sklearn.exceptions import ConvergenceWarning
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from threadpoolctl import threadpool_limits

SEED = 20261108
MAP_PARTS = [2, 3, 35, 60]
METHODS = ["sensor_logistic", "sensor_random_forest", "metadata_logistic", "metadata_random_forest"]
LABELS = {"sensor_logistic": "Sensor logistic", "sensor_random_forest": "Sensor forest",
          "metadata_logistic": "Layer/position logistic", "metadata_random_forest": "Layer/position forest"}


def sha(path):
    result = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024**2), b""):
            result.update(block)
    return result.hexdigest()


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def save_json(path, data):
    with path.open("x", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, allow_nan=False)
        handle.write("\n")


def save_csv(path, data):
    with path.open("x", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(data[0]))
        writer.writeheader()
        writer.writerows(data)


def finite_mean(values):
    valid = [value for value in values if value is not None and np.isfinite(value)]
    return float(np.mean(valid)) if valid else None


def finite_median(values):
    valid = [value for value in values if value is not None and np.isfinite(value)]
    return float(np.median(valid)) if valid else None


def save_figure(fig, path):
    with path.open("xb") as handle:
        fig.savefig(handle, format="png", dpi=180, facecolor="white")
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    root = args.root.resolve(strict=True)
    out = (args.output or root / "results/development_diagnostics_v1_2026-11-08/nuisance").resolve()
    assets = root / "reports/development_diagnostics_v1_2026-11-08/assets"
    if not out.is_relative_to(root / "results/development_diagnostics_v1_2026-11-08"):
        raise ValueError("Use the isolated development diagnostics output directory")
    if out.exists():
        raise FileExistsError(f"Refusing to overwrite diagnostic run: {out}")
    figure_paths = {name: assets / f"nuisance_{name}.png" for name in ("overview", "per_specimen_difference", "spatial_maps")}
    if any(path.exists() for path in figure_paths.values()):
        raise FileExistsError("Existing nuisance figures are protected")
    sys.path.insert(0, str(root / "src/modeling"))
    from evaluation import binary_metrics, per_group_metrics
    protocol_dir = root / "results/baseline_v1_2026-11-08/protocol"
    baseline = root / "results/baseline_v1_2026-11-08/training"
    feature_dir = root / "data/features/baseline_v1_2026-11-08"
    for filename, expected in load(protocol_dir / "artifact_hashes.json").items():
        if sha(protocol_dir / filename) != expected:
            raise ValueError(f"Frozen protocol artifact changed: {filename}")
    frozen = load(protocol_dir / "protocol.json")
    feature_summary = load(feature_dir / "summary.json")
    metadata_path = feature_dir / "metadata.csv"
    assert sha(metadata_path) == feature_summary["artifacts_sha256"]["metadata.csv"]
    verification = load(root / "results/baseline_v1_2026-11-08/verification.json")
    oof_path = baseline / "development_oof_scores.npy"
    assert sha(oof_path) == verification["saved_prediction_sha256"][oof_path.name]
    run_record = load(baseline / "run_record.json")
    with np.load(protocol_dir / "splits.npz", allow_pickle=False) as split:
        fold, eligible, y, groups, catalog_row = (split[key] for key in ("fold_id", "eligible", "candidate_y", "groups", "catalog_row"))
    n = len(y)
    assert n == 329828 and np.array_equal(catalog_row, np.arange(n))
    dev = eligible & np.isin(fold, [1, 2, 3, 4])
    dev_indices = np.flatnonzero(dev)
    assert dev.sum() == 262369 and np.unique(groups[dev]).size == 52
    assert not np.any(dev & (fold == 0)) and np.isin(y[dev], [0, 1]).all()
    assert set(groups[dev]).isdisjoint(set(groups[fold == 0]))
    assert all(np.unique(fold[groups == group]).size == 1 for group in np.unique(groups))
    position = np.full(n, -1, dtype=np.int64)
    position[dev_indices] = np.arange(len(dev_indices))
    metadata_X = np.empty((len(dev_indices), 3), dtype=np.float64)
    sample_ids = [None] * len(dev_indices)
    metadata_rows = 0
    with metadata_path.open(newline="", encoding="utf-8-sig") as handle:
        for index, row in enumerate(csv.DictReader(handle)):
            assert int(row["catalog_row"]) == index
            metadata_rows += 1
            if not dev[index]:
                continue
            at = position[index]
            assert int(row["part_id"]) == groups[index] and int(row["candidate_y"]) == y[index]
            sample_ids[at] = row["sample_id"]
            metadata_X[at] = [float(row[key]) for key in ("layer", "camera_y", "camera_x")]
    assert metadata_rows == n and all(sample_ids) and np.isfinite(metadata_X).all()
    source_oof = np.load(oof_path, mmap_mode="r", allow_pickle=False)
    sensor_columns = [run_record["method_order"].index(name) for name in ("logistic_combined", "random_forest_combined")]
    sensor_scores = np.asarray(source_oof[dev_indices][:, sensor_columns], dtype=np.float64)
    assert np.isfinite(sensor_scores).all()
    source_paths = [protocol_dir / "protocol.json", protocol_dir / "splits.npz", metadata_path, feature_dir / "summary.json", oof_path]
    before_hashes = {str(path.relative_to(root)): sha(path) for path in source_paths}
    new_params = {"metadata_logistic": frozen["models"]["logistic_combined"]["params"],
                  "metadata_random_forest": frozen["models"]["random_forest_combined"]["params"]}
    protocol = {"created_utc": datetime.now(timezone.utc).isoformat(), "purpose": "Development-only nuisance comparators, not intended sensor predictors or proof of confounding",
                "seed": SEED, "new_predictors": ["layer", "camera_y", "camera_x"], "new_models": new_params,
                "development_folds": [1, 2, 3, 4], "test_fold_accessed_for_fitting_or_scoring": False,
                "heldout_prediction_files_read": False, "unknown_rows_supervised": False,
                "sensor_models_refitted": False, "decision_threshold": .5,
                "split_policy": "For each development validation fold, train on the other three development folds; preserve whole specimens",
                "scaling": "Metadata logistic StandardScaler fitted only on its training fold; metadata forest unscaled",
                "quality_policy": "Keep all eligible development rows including flags; no extra exclusions",
                "maps_predeclared": {"specimens": MAP_PARTS, "layer": 600, "population": "eligible development patches only"},
                "conditional_metrics": "Selected sensor-forest OOF: specimen/layer blocks; ranking metrics only for blocks with both classes; report excluded single-class blocks and rows",
                "uncertainty": "No individual-patch independence assumptions or confidence intervals; no permutation significance test",
                "input_sha256": before_hashes, "script_sha256": sha(__file__), "sklearn": sklearn.__version__}
    out.mkdir(parents=True, exist_ok=False)
    assets.mkdir(parents=True, exist_ok=True)
    save_json(out / "protocol.json", protocol)
    started = time.monotonic()
    y_dev, g_dev, f_dev = y[dev], groups[dev], fold[dev]
    new_scores = np.full((n, 2), np.nan, dtype=np.float64)
    fit_log = []
    for validation_fold in [1, 2, 3, 4]:
        training = np.flatnonzero(f_dev != validation_fold)
        validation = np.flatnonzero(f_dev == validation_fold)
        assert set(g_dev[training]).isdisjoint(set(g_dev[validation]))
        assert set(np.unique(y_dev[training])) == {0, 1} == set(np.unique(y_dev[validation]))
        for column, name in enumerate(("metadata_logistic", "metadata_random_forest")):
            model = (make_pipeline(StandardScaler(), LogisticRegression(**new_params[name])) if name == "metadata_logistic" else RandomForestClassifier(**new_params[name]))
            fit_started = time.monotonic()
            with warnings.catch_warnings(record=True) as caught, threadpool_limits(limits=2):
                warnings.simplefilter("always", ConvergenceWarning)
                model.fit(metadata_X[training], y_dev[training])
                scores = model.predict_proba(metadata_X[validation])[:, list(model.classes_).index(1)]
            if any(issubclass(item.category, ConvergenceWarning) for item in caught):
                raise RuntimeError(f"Convergence failure: {name}, fold {validation_fold}")
            assert np.isfinite(scores).all()
            new_scores[dev_indices[validation], column] = scores
            elapsed = time.monotonic() - fit_started
            fit_log.append({"method": name, "validation_fold": validation_fold, "training_rows": len(training),
                            "validation_rows": len(validation), "seconds": elapsed,
                            "warnings": [{"category": item.category.__name__, "message": str(item.message)} for item in caught]})
            print(f"Development {validation_fold}: {name}; AP={binary_metrics(y_dev[validation], scores)['average_precision']:.6f}; {elapsed:.1f}s", flush=True)
    assert np.isfinite(new_scores[dev]).all() and np.isnan(new_scores[~dev]).all()
    with (out / "metadata_oof_scores.npy").open("xb") as handle:
        np.save(handle, new_scores, allow_pickle=False)
    combined = np.column_stack([sensor_scores, new_scores[dev]])
    fold_metrics, pooled_metrics, specimen_metrics, method_summary = [], [], [], []
    for column, name in enumerate(METHODS):
        method_folds = []
        for val_fold in [1, 2, 3, 4]:
            mask = f_dev == val_fold
            item = {"method": name, "fold_id": val_fold, **binary_metrics(y_dev[mask], combined[mask, column])}
            fold_metrics.append(item); method_folds.append(item)
        pooled_metrics.append({"method": name, **binary_metrics(y_dev, combined[:, column])})
        per_group = per_group_metrics(y_dev, combined[:, column], g_dev)
        for item in per_group:
            item["ap_gain_over_local_prevalence"] = None if item["average_precision"] is None else item["average_precision"] - item["prevalence"]
        specimen_metrics.extend({"method": name, **item} for item in per_group)
        method_summary.append({"method": name, "mean_fold_ap": finite_mean([item["average_precision"] for item in method_folds]),
                               "std_fold_ap": float(np.std([item["average_precision"] for item in method_folds])),
                               "pooled_ap": pooled_metrics[-1]["average_precision"], "pooled_recall": pooled_metrics[-1]["recall"],
                               "mean_specimen_roc_auc": finite_mean([item["roc_auc"] for item in per_group]),
                               "median_specimen_roc_auc": finite_median([item["roc_auc"] for item in per_group]),
                               "mean_specimen_ap_gain": finite_mean([item["ap_gain_over_local_prevalence"] for item in per_group]),
                               "median_specimen_ap_gain": finite_median([item["ap_gain_over_local_prevalence"] for item in per_group]),
                               "mean_specimen_recall": finite_mean([item["recall"] for item in per_group]),
                               "specimens_with_ranking_metrics": sum(item["roc_auc"] is not None for item in per_group)})
    save_csv(out / "fold_metrics.csv", fold_metrics)
    save_csv(out / "pooled_metrics.csv", pooled_metrics)
    save_csv(out / "per_specimen_metrics.csv", specimen_metrics)
    save_csv(out / "method_summary.csv", method_summary)
    save_json(out / "fit_log.json", fit_log)
    with (out / "development_predictions.csv").open("x", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["sample_id", "catalog_row", "part_id", "layer", "camera_y", "camera_x", "candidate_y", "fold_id", *METHODS])
        for i, idx in enumerate(dev_indices):
            writer.writerow([sample_ids[i], int(idx), int(g_dev[i]), *map(int, metadata_X[i]), int(y_dev[i]), int(f_dev[i]), *map(float, combined[i])])
    order = np.lexsort((metadata_X[:, 0], g_dev))
    changes = np.flatnonzero((np.diff(g_dev[order]) != 0) | (np.diff(metadata_X[order, 0]) != 0)) + 1
    blocks = np.split(order, changes)
    conditional = []
    for indices in blocks:
        metrics = binary_metrics(y_dev[indices], sensor_scores[indices, 1])
        conditional.append({"part_id": int(g_dev[indices[0]]), "layer": int(metadata_X[indices[0], 0]),
                            "both_classes": bool(metrics["positive"] and metrics["negative"]), **metrics})
    save_csv(out / "sensor_forest_within_specimen_layer.csv", conditional)
    usable = [item for item in conditional if item["both_classes"]]
    conditional_summary = {"total_blocks": len(conditional), "both_class_blocks": len(usable),
                           "single_class_blocks_excluded_from_ranking": len(conditional)-len(usable),
                           "rows_in_both_class_blocks": sum(item["n"] for item in usable),
                           "rows_in_single_class_blocks": sum(item["n"] for item in conditional if not item["both_classes"]),
                           "mean_within_block_roc_auc": finite_mean([item["roc_auc"] for item in usable]),
                           "median_within_block_roc_auc": finite_median([item["roc_auc"] for item in usable]),
                           "mean_within_block_ap_gain": finite_mean([item["average_precision"]-item["prevalence"] for item in usable]),
                           "interpretation": "Conditional development-only ranking where a specimen/layer has both classes; excluded single-class blocks limit representativeness. No patch-independent confidence interval or causal attribution."}
    plt.rcParams.update({"font.size": 12, "axes.spines.top": False, "axes.spines.right": False})
    fig, axes = plt.subplots(1, 2, figsize=(12, 5.2), layout="constrained")
    colors = ["#4c78a8", "#1864ab", "#f2a541", "#d17b00"]
    positions = np.arange(4)
    for ax, key, title in [(axes[0], "mean_fold_ap", "Mean of four development-fold APs"),
                           (axes[1], "mean_specimen_roc_auc", "Mean within-specimen AUROC")]:
        ax.bar(positions, [item[key] for item in method_summary], color=colors)
        if key == "mean_fold_ap":
            ax.errorbar(positions, [item[key] for item in method_summary], yerr=[item["std_fold_ap"] for item in method_summary], fmt="none", color="black", capsize=3)
        for x, item in enumerate(method_summary):
            ax.text(x, item[key]+.025, f"{item[key]:.3f}", ha="center", fontsize=11)
        ax.set_xticks(positions, ["Sensor\nlogistic", "Sensor\nforest", "Layer/XY\nlogistic", "Layer/XY\nforest"], fontsize=11)
        ax.set_ylim(0, 1.05); ax.set_title(title, fontsize=13)
    fig.suptitle("Development-only nuisance controls: metadata is a diagnostic comparator", fontsize=14)
    fig.supxlabel("52 development specimens; class and support rules unchanged. Error bars: fold SD, not confidence intervals.", fontsize=10)
    save_figure(fig, figure_paths["overview"])
    sensor_by_group = {row["part_id"]: row for row in specimen_metrics if row["method"] == "sensor_random_forest"}
    meta_by_group = {row["part_id"]: row for row in specimen_metrics if row["method"] == "metadata_random_forest"}
    differences = [{"part_id": group, "sensor_roc_auc": sensor_by_group[group]["roc_auc"], "metadata_roc_auc": meta_by_group[group]["roc_auc"],
                    "sensor_minus_metadata_roc_auc": None if sensor_by_group[group]["roc_auc"] is None else sensor_by_group[group]["roc_auc"]-meta_by_group[group]["roc_auc"]}
                   for group in sorted(sensor_by_group)]
    save_csv(out / "per_specimen_forest_difference.csv", differences)
    fig, ax = plt.subplots(figsize=(11, 5), layout="constrained")
    ax.axhline(0, color="#777777", linewidth=1)
    valid = [row for row in differences if row["sensor_minus_metadata_roc_auc"] is not None]
    ax.scatter([row["part_id"] for row in valid], [row["sensor_minus_metadata_roc_auc"] for row in valid], color="#1864ab", s=35)
    for row in valid:
        if row["part_id"] in MAP_PARTS:
            ax.annotate(f"P{row['part_id']}", (row["part_id"], row["sensor_minus_metadata_roc_auc"]), xytext=(4, 6), textcoords="offset points", fontsize=11)
    ax.set_xlabel("Development specimen ID (display order, not a spatial build map)")
    ax.set_ylabel("Sensor forest AUROC minus layer/XY forest AUROC")
    ax.set_title("Within-specimen differences under the same development folds", fontsize=14)
    fig.supxlabel("Positive: sensor ranking higher; negative: metadata ranking higher. Descriptive comparison, not a causal test.", fontsize=10)
    save_figure(fig, figure_paths["per_specimen_difference"])
    fig, axes = plt.subplots(4, 3, figsize=(11, 12.5), layout="constrained")
    for r, part in enumerate(MAP_PARTS):
        mask = (g_dev == part) & (metadata_X[:, 0] == 600)
        assert mask.any(), f"Predeclared development map missing P{part} layer600"
        for c, (values, label) in enumerate([(y_dev, "Candidate target"), (sensor_scores[:, 1], "Sensor forest OOF"), (new_scores[dev, 1], "Layer/XY forest OOF")]):
            image = axes[r, c].scatter(metadata_X[mask, 2]+12, metadata_X[mask, 1]+12, c=values[mask], marker="s", s=110, cmap="viridis", vmin=0, vmax=1)
            axes[r, c].set_aspect("equal"); axes[r, c].set_title(f"P{part}: {label}", fontsize=12)
            axes[r, c].set_xlabel("Camera X (patch centre)", fontsize=10); axes[r, c].set_ylabel("Camera Y", fontsize=10)
            axes[r, c].tick_params(labelsize=9)
    fig.colorbar(image, ax=axes.ravel().tolist(), shrink=.55, label="Candidate 0/1 or score, fixed [0,1]")
    fig.suptitle("Predeclared development maps at layer 600; eligible patches only\nUnknowns omitted; candidate targets remain unvalidated", fontsize=14)
    save_figure(fig, figure_paths["spatial_maps"])
    after_hashes = {str(path.relative_to(root)): sha(path) for path in source_paths}
    assert before_hashes == after_hashes, "Source artifact changed during diagnostics"
    summary = {"stage": "development_nuisance_audit_complete", "development_rows": len(dev_indices), "development_specimens": len(np.unique(g_dev)),
               "methods": method_summary, "conditional_sensor_forest": conditional_summary, "new_model_fits": 8,
               "test_rows_fitted_or_scored": 0, "heldout_prediction_files_read": False, "raw_hdf5_read": False,
               "sensor_models_refitted": False, "input_hashes_unchanged": True, "quality_flag_exclusions": 0,
               "source_metadata_arrays_written": False, "elapsed_seconds": time.monotonic()-started,
               "figure_files": {key: str(path.relative_to(root)) for key, path in figure_paths.items()},
               "limitations": ["Metadata comparator is not an intended sensor predictor", "Differences do not prove confounding or physical flaw detection", "One build and provisional targets", "Scores are not calibrated physical probabilities", "Conditional metrics omit single-class specimen/layer blocks", "Saved sensor OOF scores are float32; new control scores are saved float64"]}
    save_json(out / "summary.json", summary)
    save_json(out / "artifact_hashes.json", {path.name: sha(path) for path in sorted(out.iterdir()) if path.is_file()})
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
