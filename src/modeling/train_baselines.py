"""Train the predeclared exploratory sensor-to-candidate baselines.

Only prepared image descriptors are model inputs. Targets remain provisional.
The final specimen holdout is scored after development selection is saved.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import platform
import sys
import time
import warnings
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.exceptions import ConvergenceWarning
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from threadpoolctl import threadpool_limits

from evaluation import binary_metrics, per_group_metrics


METHODS = ["dummy_prior", "logistic_combined", "random_forest_combined",
           "logistic_visible", "logistic_nir"]


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def write_csv(path, rows):
    if not rows:
        return
    with Path(path).open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def make_model(name, config):
    params = config["params"].copy()
    if name == "dummy_prior":
        return DummyClassifier(**params)
    if name.startswith("logistic_"):
        return make_pipeline(StandardScaler(), LogisticRegression(**params))
    if name == "random_forest_combined":
        return RandomForestClassifier(**params)
    raise ValueError(name)


def model_features(name):
    if name == "logistic_visible":
        return np.arange(28)
    if name == "logistic_nir":
        return np.arange(28, 42)
    return np.arange(42)


def fit_and_score(name, config, features, target, train_rows, score_rows):
    model = make_model(name, config)
    columns = model_features(name)
    started = time.monotonic()
    with warnings.catch_warnings(record=True) as caught, threadpool_limits(limits=2):
        warnings.simplefilter("always", ConvergenceWarning)
        model.fit(features[train_rows][:, columns], target[train_rows])
        scores = model.predict_proba(features[score_rows][:, columns])[:, list(model.classes_).index(1)]
    recorded = [{"category": item.category.__name__, "message": str(item.message)} for item in caught]
    # A failed convergence check requires attention before opening the holdout.
    if any(item["category"] == "ConvergenceWarning" for item in recorded):
        raise RuntimeError(f"{name} convergence warning: {recorded}")
    if not np.isfinite(scores).all():
        raise RuntimeError(f"Nonfinite predictions: {name}")
    return model, scores, time.monotonic() - started, recorded


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--protocol", type=Path)
    parser.add_argument("--features", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--models-output", type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    protocol_dir = args.protocol or root / "results/baseline_v1_2026-11-08/protocol"
    feature_dir = args.features or root / "data/features/baseline_v1_2026-11-08"
    output = args.output or root / "results/baseline_v1_2026-11-08/training"
    model_dir = args.models_output or root / "models/baseline_v1_2026-11-08"
    for path in (output, model_dir):
        if path.exists():
            raise FileExistsError(f"Refusing to overwrite existing run: {path}")
        path.resolve().relative_to(root)

    protocol_path = protocol_dir / "protocol.json"
    protocol_hashes = json.loads((protocol_dir / "artifact_hashes.json").read_text(encoding="utf-8"))
    for name, expected in protocol_hashes.items():
        assert sha256(protocol_dir / name) == expected, f"Frozen protocol hash mismatch: {name}"
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    assert protocol["test_fold"] == 0 and protocol["development_folds"] == [1, 2, 3, 4]
    assert protocol["decision_threshold"] == 0.5
    assert set(protocol["models"]) == set(METHODS)
    assert protocol["target_status"] == "provisional_candidates_exploratory"
    threshold = protocol["decision_threshold"]
    feature_summary = json.loads((feature_dir / "summary.json").read_text(encoding="utf-8"))
    for name, expected in feature_summary["artifacts_sha256"].items():
        assert sha256(feature_dir / name) == expected, f"Feature artifact hash mismatch: {name}"
    for name in METHODS:
        expected_columns = protocol["feature_sets"][protocol["models"][name]["feature_set"]]
        assert model_features(name).tolist() == expected_columns
    names = json.loads((feature_dir / "feature_names.json").read_text(encoding="utf-8"))
    assert names == protocol["feature_names"] and len(names) == 42
    features = np.load(feature_dir / "features.npy", mmap_mode="r", allow_pickle=False)
    target = np.load(feature_dir / "candidate_y.npy", allow_pickle=False)
    groups = np.load(feature_dir / "groups.npy", allow_pickle=False)
    catalog_row = np.load(feature_dir / "catalog_row.npy", allow_pickle=False)
    with np.load(protocol_dir / "splits.npz", allow_pickle=False) as split:
        fold = split["fold_id"].copy()
        eligible = split["eligible"].copy()
        for key, actual in (("candidate_y", target), ("groups", groups), ("catalog_row", catalog_row)):
            assert np.array_equal(split[key], actual), key
    assert features.shape == (329828, 42) and features.dtype == np.float32
    assert np.isfinite(features).all() and np.array_equal(eligible, np.isin(target, [0, 1]))
    assert np.array_equal(catalog_row, np.arange(len(target)))
    assert eligible.sum() == 323280 and np.unique(groups).size == 64
    assert all(np.unique(fold[groups == group]).size == 1 for group in np.unique(groups))
    metadata = pd.read_csv(feature_dir / "metadata.csv", usecols=[
        "sample_id", "catalog_row", "part_id", "layer", "camera_y", "camera_x",
        "quality_flags", "channel_2_constant", "label_validated", "coverage_validated"])
    assert np.array_equal(metadata.catalog_row, catalog_row)
    assert np.array_equal(metadata.part_id, groups)
    for column in ("label_validated", "coverage_validated"):
        assert metadata[column].astype(str).str.lower().isin(["false", "0"]).all()
    dev = eligible & (fold != 0)
    test = eligible & (fold == 0)
    assert set(groups[dev]).isdisjoint(groups[test])

    input_paths = [protocol_path, protocol_dir / "splits.npz", feature_dir / "features.npy",
                   feature_dir / "feature_names.json", feature_dir / "summary.json",
                   feature_dir / "metadata.csv",
                   root / "data/cleaned/snow_source_preparation_v1/catalog/manifest.csv"]
    initial_hashes = {path.relative_to(root).as_posix(): sha256(path) for path in input_paths}
    assert initial_hashes["data/cleaned/snow_source_preparation_v1/catalog/manifest.csv"] == \
        "71bc9e998c0042b7c630ef6443b4dbfe8bbbd3bec9213f7f8425d360af236010"
    source_path = root / "data/raw/2024-05-01 M2 AMMTO Fatigue Blanks 05.hdf5"
    raw_stat = {"size": source_path.stat().st_size, "mtime_ns": source_path.stat().st_mtime_ns}
    baseline = json.loads((root / "work/baseline_2026-11-08_run01.json").read_text(encoding="utf-8"))
    assert raw_stat == {key: baseline["raw"][key] for key in ("size", "mtime_ns")}
    output.mkdir(parents=True)
    model_dir.mkdir(parents=True)
    started = time.monotonic()
    record = {
        "started_utc": datetime.now(timezone.utc).isoformat(),
        "target_status": protocol["target_status"], "protocol_sha256": sha256(protocol_path),
        "trainer_sha256": sha256(__file__), "evaluation_sha256": sha256(Path(__file__).with_name("evaluation.py")),
        "python": platform.python_version(), "sklearn": sklearn.__version__,
        "numpy": np.__version__, "pandas": pd.__version__, "joblib": joblib.__version__,
        "thread_limit": 2, "input_sha256": initial_hashes, "raw_stat_before": raw_stat,
        "development_rows": int(dev.sum()), "test_rows": int(test.sum()),
        "unknown_rows_excluded": int((~eligible).sum()), "decision_threshold": threshold,
        "prediction_interpretation": "class-weighted model scores; no probability calibration",
        "method_order": METHODS, "status": "development_in_progress",
    }
    write_json(output / "run_record.json", record)
    print(f"Frozen protocol verified. Development {dev.sum():,}; held-out {test.sum():,}; unknown excluded {(~eligible).sum():,}.", flush=True)

    oof = np.full((len(target), len(METHODS)), np.nan, dtype=np.float32)
    fold_rows, fits = [], []
    for val_fold in protocol["development_folds"]:
        train_rows = np.flatnonzero(dev & (fold != val_fold))
        val_rows = np.flatnonzero(dev & (fold == val_fold))
        assert set(groups[train_rows]).isdisjoint(groups[val_rows])
        for method_index, name in enumerate(METHODS):
            print(f"Development fold {val_fold}: fitting {name} ({len(train_rows):,} train / {len(val_rows):,} validation)", flush=True)
            _, scores, seconds, caught = fit_and_score(name, protocol["models"][name], features, target, train_rows, val_rows)
            oof[val_rows, method_index] = scores
            metrics = binary_metrics(target[val_rows], scores, threshold)
            fold_rows.append({"method": name, "fold": val_fold, **metrics, "fit_predict_seconds": seconds})
            fits.append({"phase": "development", "method": name, "validation_fold": val_fold, "seconds": seconds, "warnings": caught})
            print(f"  AP={metrics['average_precision']:.5f}; balanced accuracy={metrics['balanced_accuracy']:.5f}; {seconds:.1f}s", flush=True)
            write_csv(output / "development_fold_metrics.csv", fold_rows)
            write_json(output / "fit_log.json", fits)
    assert np.isfinite(oof[dev]).all() and np.isnan(oof[~dev]).all()
    np.save(output / "development_oof_scores.npy", oof, allow_pickle=False)
    summary_rows, group_rows = [], []
    for index, name in enumerate(METHODS):
        aps = [row["average_precision"] for row in fold_rows if row["method"] == name]
        summary_rows.append({"method": name, "mean_fold_ap": float(np.mean(aps)),
                             "std_fold_ap": float(np.std(aps)),
                             **binary_metrics(target[dev], oof[dev, index], threshold)})
        group_rows.extend({"method": name, **row} for row in per_group_metrics(target[dev], oof[dev, index], groups[dev], threshold))
    write_csv(output / "development_summary.csv", summary_rows)
    write_csv(output / "development_per_specimen.csv", group_rows)
    primary_order = ["dummy_prior", "logistic_combined", "random_forest_combined"]
    mean_aps = {row["method"]: row["mean_fold_ap"] for row in summary_rows}
    best_ap = max(mean_aps[name] for name in primary_order)
    selected = next(name for name in primary_order if best_ap - mean_aps[name] <= 1e-4)
    selection = {"selected_primary_method": selected,
                 "selection_basis": "highest mean development fold average precision; within 1e-4 prefer dummy, logistic, then forest",
                 "mean_development_ap": {name: mean_aps[name] for name in primary_order},
                 "decision_threshold": threshold, "selected_before_holdout_scoring": True,
                 "created_utc": datetime.now(timezone.utc).isoformat(),
                 "holdout_policy": "All five predeclared methods scored once; no holdout-based model reselection or tuning"}
    write_json(output / "selection_before_holdout.json", selection)
    selection_hash = sha256(output / "selection_before_holdout.json")
    print(f"Development selection frozen: {selected}. Starting the predeclared final holdout suite.", flush=True)
    record["status"] = "selection_frozen_final_refits"
    record["selection_sha256"] = selection_hash
    write_json(output / "run_record.json", record)

    train_rows, test_rows = np.flatnonzero(dev), np.flatnonzero(test)
    test_scores = np.full((len(target), len(METHODS)), np.nan, dtype=np.float32)
    test_metrics, test_groups, descriptor_rows = [], [], []
    for index, name in enumerate(METHODS):
        print(f"Final development-only refit: {name}", flush=True)
        model, scores, seconds, caught = fit_and_score(name, protocol["models"][name], features, target, train_rows, test_rows)
        test_scores[test_rows, index] = scores
        metrics = binary_metrics(target[test_rows], scores, threshold)
        test_metrics.append({"method": name, "selected_primary": name == selected, **metrics})
        test_groups.extend({"method": name, **row} for row in per_group_metrics(target[test_rows], scores, groups[test_rows], threshold))
        fits.append({"phase": "final_development_refit", "method": name, "seconds": seconds, "warnings": caught})
        artifact = {"estimator": model, "feature_indices": model_features(name).tolist(),
                    "feature_names": [names[i] for i in model_features(name)], "target_status": protocol["target_status"],
                    "protocol_sha256": record["protocol_sha256"], "selection_sha256": selection_hash,
                    "training_specimens": np.unique(groups[dev]).tolist(), "decision_threshold": threshold}
        joblib.dump(artifact, model_dir / f"{name}.joblib", compress=3)
        if name.startswith("logistic_"):
            values = model[-1].coef_[0]
            kind = "standardized_logistic_coefficient"
        elif name == "random_forest_combined":
            values = model.feature_importances_
            kind = "forest_impurity_importance_descriptive_only"
        else:
            values = []
            kind = "none"
        descriptor_rows.extend({"method": name, "feature": names[column], "kind": kind, "value": float(value)}
                               for column, value in zip(model_features(name), values))
        print(f"  Holdout AP={metrics['average_precision']:.5f}; balanced accuracy={metrics['balanced_accuracy']:.5f}; {seconds:.1f}s", flush=True)
        write_csv(output / "test_metrics.csv", test_metrics)
        write_json(output / "fit_log.json", fits)
    assert np.isfinite(test_scores[test]).all() and np.isnan(test_scores[~test]).all()
    np.save(output / "test_scores.npy", test_scores, allow_pickle=False)
    write_csv(output / "test_per_specimen.csv", test_groups)
    write_csv(output / "feature_descriptors.csv", descriptor_rows)

    for phase, mask, scores in (("development_oof", dev, oof), ("test", test, test_scores)):
        frame = metadata.loc[mask, ["sample_id", "catalog_row", "part_id", "layer", "camera_y", "camera_x"]].copy()
        frame["candidate_y"] = target[mask]
        frame["fold_id"] = fold[mask]
        for index, name in enumerate(METHODS):
            frame[name] = scores[mask, index]
        frame.to_csv(output / f"{phase}_predictions.csv", index=False, float_format="%.9g")

    constant_nir = metadata.channel_2_constant.astype(str).str.lower().isin(["true", "1"]).to_numpy()
    source_event = metadata.quality_flags.fillna("").str.contains("author_layer_event_affected_region_requires_review", regex=False).to_numpy()
    sensitivity = []
    for phase, mask, scores in (("development_oof", dev, oof), ("test", test, test_scores)):
        for label, excluded in (("all_primary_rows", np.zeros(len(target), dtype=bool)),
                                ("exclude_constant_nir_evaluation_only", constant_nir),
                                ("exclude_author_event_evaluation_only", source_event)):
            subset = mask & ~excluded
            for index, name in enumerate(METHODS):
                sensitivity.append({"phase": phase, "subset": label, "method": name,
                                    "excluded_rows": int((mask & excluded).sum()),
                                    **binary_metrics(target[subset], scores[subset, index], threshold)})
    write_csv(output / "sensitivity_metrics.csv", sensitivity)
    after_hashes = {path.relative_to(root).as_posix(): sha256(path) for path in input_paths}
    assert after_hashes == initial_hashes, "Input changed during training"
    assert {"size": source_path.stat().st_size, "mtime_ns": source_path.stat().st_mtime_ns} == raw_stat
    preserved = []
    for original in baseline["files"]:
        path = root / original["path"]
        if "sha256" in original:
            assert sha256(path) == original["sha256"], f"Original file changed: {path}"
            preserved.append(original["path"])
    record.update({"status": "complete", "completed_utc": datetime.now(timezone.utc).isoformat(),
                   "elapsed_seconds": time.monotonic() - started, "selected_primary_method": selected,
                   "all_input_hashes_unchanged": True, "raw_size_mtime_unchanged": True,
                   "original_files_hash_verified": preserved,
                   "validation_flags_remain_false": True, "holdout_evaluation_passes": 1,
                   "model_files_sha256": {path.name: sha256(path) for path in model_dir.glob("*.joblib")}})
    write_json(output / "run_record.json", record)
    write_json(output / "results_summary.json", {"target_status": protocol["target_status"],
               "selection": selection, "development": summary_rows, "test": test_metrics,
               "elapsed_seconds": record["elapsed_seconds"],
               "limitations": ["Candidate annotations remain unvalidated", "One build; no cross-build evidence",
                               "Spatial and layer correlation remains within specimens", "Scores are not calibrated physical defect probabilities",
                               "Pooled patch metrics can hide weak within-specimen discrimination"]})
    print(f"Complete: {selected}; {record['elapsed_seconds']:.1f}s; original inputs unchanged.", flush=True)


if __name__ == "__main__":
    main()
