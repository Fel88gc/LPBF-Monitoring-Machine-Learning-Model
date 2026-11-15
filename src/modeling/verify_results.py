"""Independently verify an already-completed frozen exploratory baseline run.

No fit, model search, model selection based on holdout results, or source writes
occur here. This repeats calculations on the same saved predictions and checks
50 predetermined held-out rows against the already-saved final model objects.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score, average_precision_score, balanced_accuracy_score,
    confusion_matrix, f1_score, precision_score, recall_score, roc_auc_score,
)
from threadpoolctl import threadpool_limits


RANK_METRIC_TOLERANCE = 1e-6
SCORE_TOLERANCE = 1e-7
RATE_TOLERANCE = 1e-12
METHODS = ["dummy_prior", "logistic_combined", "random_forest_combined",
           "logistic_visible", "logistic_nir"]
COUNT_METRICS = {"n", "positive", "negative", "tn", "fp", "fn", "tp"}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(path):
    result = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def own_metrics(y, score, threshold):
    """Independent sklearn metric calls; intentionally does not import evaluation.py."""
    y, score = np.asarray(y), np.asarray(score, dtype=np.float64)
    require(y.ndim == score.ndim == 1 and len(y) == len(score), "Invalid evaluation vectors")
    require(np.isin(y, (0, 1)).all(), "Unknown label reached supervised evaluation")
    require(np.isfinite(score).all(), "Nonfinite score reached evaluation")
    predicted = score >= threshold
    tn, fp, fn, tp = [int(v) for v in confusion_matrix(y, predicted, labels=[0, 1]).ravel()]
    positive, negative = tp + fn, tn + fp
    both = bool(positive and negative)
    return {
        "n": len(y), "positive": positive, "negative": negative,
        "prevalence": float(positive / len(y)) if len(y) else None,
        "accuracy": float(accuracy_score(y, predicted)) if len(y) else None,
        "balanced_accuracy": float(balanced_accuracy_score(y, predicted)) if both else None,
        "precision": float(precision_score(y, predicted, zero_division=0)) if tp + fp else None,
        "recall": float(recall_score(y, predicted, zero_division=0)) if positive else None,
        "f1": float(f1_score(y, predicted, zero_division=0)) if 2 * tp + fp + fn else None,
        "average_precision": float(average_precision_score(y, score)) if both else None,
        "roc_auc": float(roc_auc_score(y, score)) if both else None,
        "tn": tn, "fp": fp, "fn": fn, "tp": tp,
    }


def compare_metrics(recorded, recalculated, description, differences):
    local = {}
    for key, actual in recalculated.items():
        saved = recorded[key]
        if pd.isna(saved):
            saved = None
        if actual is None or saved is None:
            require(actual is None and saved is None, f"Undefined metric differs: {description}/{key}")
            continue
        delta = abs(float(actual) - float(saved))
        local[key] = delta
        if key in COUNT_METRICS:
            require(delta == 0, f"Exact count differs: {description}/{key}: {actual} vs {saved}")
        else:
            tolerance = RANK_METRIC_TOLERANCE if key in ("average_precision", "roc_auc") else RATE_TOLERANCE
            require(delta <= tolerance, f"Metric exceeds tolerance: {description}/{key}: {delta}")
    differences.append({"comparison": description, "absolute_deltas": local})


def verify(root: Path, output: Path):
    root, output = root.resolve(), output.resolve()
    require(output.is_relative_to(root / "results/baseline_v1_2026-11-08"), "Verification output outside this run")
    require(not output.exists(), "Refusing to overwrite existing verification")
    feature_dir = root / "data/features/baseline_v1_2026-11-08"
    results = root / "results/baseline_v1_2026-11-08"
    training, protocol_dir = results / "training", results / "protocol"
    models = root / "models/baseline_v1_2026-11-08"
    run = load_json(training / "run_record.json")
    require(run["status"] == "complete", "Training has not completed; verification may not run")
    protocol = load_json(protocol_dir / "protocol.json")
    feature_summary = load_json(feature_dir / "summary.json")
    selection = load_json(training / "selection_before_holdout.json")
    selection_hash = digest(training / "selection_before_holdout.json")
    checked_hashes = {}
    for directory, entries in (
        (protocol_dir, load_json(protocol_dir / "artifact_hashes.json")),
        (feature_dir, feature_summary["artifacts_sha256"]),
        (root, run["input_sha256"]),
        (models, run["model_files_sha256"]),
    ):
        for name, expected in entries.items():
            path = directory / name
            actual = digest(path)
            require(actual == expected, f"Frozen artifact checksum mismatch: {path}")
            checked_hashes[path.relative_to(root).as_posix()] = actual
    require(digest(protocol_dir / "protocol.json") == run["protocol_sha256"], "Protocol hash mismatch")
    require(selection_hash == run["selection_sha256"], "Selection changed after it was frozen")
    require(run["holdout_evaluation_passes"] == 1, "Recorded holdout evaluation count changed")
    require(run["all_input_hashes_unchanged"] and run["validation_flags_remain_false"], "Run integrity status is false")
    require(run["method_order"] == METHODS and protocol["decision_threshold"] == 0.5, "Method order or threshold differs")
    threshold = protocol["decision_threshold"]
    features = np.load(feature_dir / "features.npy", mmap_mode="r", allow_pickle=False)
    target = np.load(feature_dir / "candidate_y.npy", allow_pickle=False)
    groups = np.load(feature_dir / "groups.npy", allow_pickle=False)
    catalog_row = np.load(feature_dir / "catalog_row.npy", allow_pickle=False)
    names = load_json(feature_dir / "feature_names.json")
    with np.load(protocol_dir / "splits.npz", allow_pickle=False) as split:
        fold, eligible = split["fold_id"].copy(), split["eligible"].copy()
        for key, actual in (("candidate_y", target), ("groups", groups), ("catalog_row", catalog_row)):
            require(np.array_equal(split[key], actual), f"Frozen split vector differs: {key}")
    require(features.shape == (329828, 42) and features.dtype == np.float32, "Feature shape/dtype differs")
    require(np.isfinite(features).all(), "Feature matrix is nonfinite")
    require(names == protocol["feature_names"], "Feature order changed")
    require(np.array_equal(catalog_row, np.arange(len(target))), "Canonical row order differs")
    require(np.array_equal(eligible, np.isin(target, (0, 1))), "Unknown handling differs")
    require(int((~eligible).sum()) == 6548, "Unknown row count differs")
    require(set(np.unique(fold)) == {0, 1, 2, 3, 4}, "Unexpected fold IDs")
    for group in np.unique(groups):
        require(len(np.unique(fold[groups == group])) == 1, f"Specimen occurs in multiple folds: {group}")
    dev, test = eligible & (fold != 0), eligible & (fold == 0)
    train_specimens, test_specimens = np.unique(groups[dev]), np.unique(groups[test])
    require(len(train_specimens) == 52 and len(test_specimens) == 12, "Unexpected train/test specimen counts")
    require(set(train_specimens).isdisjoint(test_specimens), "Development/test specimen overlap")
    require(int(dev.sum()) == run["development_rows"] and int(test.sum()) == run["test_rows"], "Run row counts differ")
    for design in protocol["development_cv"]:
        val = dev & (fold == design["validation_fold"])
        train = dev & (fold != design["validation_fold"])
        require(np.unique(groups[train]).tolist() == design["training_specimens"], "CV training specimens differ")
        require(np.unique(groups[val]).tolist() == design["validation_specimens"], "CV validation specimens differ")
        require(set(groups[train]).isdisjoint(groups[val]), "CV specimen overlap")

    oof = np.load(training / "development_oof_scores.npy", mmap_mode="r", allow_pickle=False)
    test_scores = np.load(training / "test_scores.npy", mmap_mode="r", allow_pickle=False)
    metadata = pd.read_csv(feature_dir / "metadata.csv")
    require(np.array_equal(metadata.catalog_row, catalog_row), "Metadata canonical rows differ")
    require(np.array_equal(metadata.candidate_y, target), "Metadata targets differ")
    require(np.array_equal(metadata.part_id, groups), "Metadata groups differ")
    require((metadata.label_validated == 0).all() and (metadata.coverage_validated == 0).all(), "Source validation flags changed")
    score_hashes = {}
    for phase, score_array, mask in (("development_oof", oof, dev), ("test", test_scores, test)):
        require(score_array.shape == (len(target), 5) and score_array.dtype == np.float32, f"{phase}: score shape/dtype differs")
        require(np.isfinite(score_array[mask]).all() and np.isnan(score_array[~mask]).all(), f"{phase}: scores include wrong rows")
        require(np.all((score_array[mask] >= 0) & (score_array[mask] <= 1)), f"{phase}: scores out of [0,1]")
        frame = pd.read_csv(training / f"{phase}_predictions.csv")
        require(len(frame) == int(mask.sum()), f"{phase}: prediction CSV row count differs")
        for field, actual in (("catalog_row", catalog_row[mask]), ("candidate_y", target[mask]),
                              ("part_id", groups[mask]), ("fold_id", fold[mask]),
                              ("sample_id", metadata.loc[mask, "sample_id"].to_numpy())):
            require(np.array_equal(frame[field].to_numpy(), actual), f"{phase}: prediction CSV {field} mismatch")
        require(np.array_equal(frame[METHODS].to_numpy(dtype=np.float32), score_array[mask]), f"{phase}: CSV/NPY score mismatch")
        for filename in (f"{phase}_predictions.csv", "development_oof_scores.npy" if phase == "development_oof" else "test_scores.npy"):
            score_hashes[filename] = digest(training / filename)

    # Metrics are recalculated only from the same saved predictions, never from
    # another fit or a new holdout pass. Ranking deltas are recorded explicitly:
    # trainer tables use float64 predict_proba; saved tensors are float32.
    differences, independent_fold_ap = [], {}
    fold_metrics = pd.read_csv(training / "development_fold_metrics.csv")
    dev_summary = pd.read_csv(training / "development_summary.csv")
    heldout_metrics = pd.read_csv(training / "test_metrics.csv")
    for index, name in enumerate(METHODS):
        independent_fold_ap[name] = []
        for val_fold in protocol["development_folds"]:
            mask = dev & (fold == val_fold)
            recorded = fold_metrics[(fold_metrics.method == name) & (fold_metrics.fold == val_fold)]
            require(len(recorded) == 1, "Missing or duplicated development metric row")
            metric = own_metrics(target[mask], oof[mask, index], threshold)
            compare_metrics(recorded.iloc[0], metric, f"development/fold_{val_fold}/{name}", differences)
            independent_fold_ap[name].append(metric["average_precision"])
        saved = dev_summary[dev_summary.method == name]
        require(len(saved) == 1, "Missing or duplicated development summary")
        compare_metrics(saved.iloc[0], own_metrics(target[dev], oof[dev, index], threshold), f"development/pooled/{name}", differences)
        require(abs(saved.iloc[0].mean_fold_ap - np.mean(independent_fold_ap[name])) <= RANK_METRIC_TOLERANCE, "Mean development AP differs")
        require(abs(saved.iloc[0].std_fold_ap - np.std(independent_fold_ap[name])) <= RANK_METRIC_TOLERANCE, "Development AP SD differs")
        saved_test = heldout_metrics[heldout_metrics.method == name]
        require(len(saved_test) == 1, "Missing or duplicated test metric row")
        compare_metrics(saved_test.iloc[0], own_metrics(target[test], test_scores[test, index], threshold), f"test/pooled/{name}", differences)
    for phase, mask, score_array, filename in (
        ("development", dev, oof, "development_per_specimen.csv"),
        ("test", test, test_scores, "test_per_specimen.csv"),
    ):
        table = pd.read_csv(training / filename)
        require(len(table) == len(METHODS) * len(np.unique(groups[mask])), f"{phase}: per-specimen row count differs")
        for index, name in enumerate(METHODS):
            for group in np.unique(groups[mask]):
                subset = mask & (groups == group)
                saved = table[(table.method == name) & (table.part_id == group)]
                require(len(saved) == 1, "Missing/duplicated per-specimen metric row")
                compare_metrics(saved.iloc[0], own_metrics(target[subset], score_array[subset, index], threshold), f"{phase}/specimen_{group}/{name}", differences)

    mean_ap = {name: float(dev_summary.loc[dev_summary.method == name, "mean_fold_ap"].iloc[0])
               for name in protocol["model_selection_candidates"]}
    best = max(mean_ap.values())
    expected_selection = next(name for name in protocol["simplicity_order"]
                              if best - mean_ap[name] <= protocol["selection_tie_tolerance"])
    require(selection["selected_primary_method"] == expected_selection == run["selected_primary_method"], "Selection does not follow frozen development rule")
    require(selection["selected_before_holdout_scoring"] is True, "Selection was not recorded as frozen")
    require(selection["decision_threshold"] == threshold, "Selection threshold changed")
    for name, saved_ap in selection["mean_development_ap"].items():
        require(abs(saved_ap - mean_ap[name]) <= RATE_TOLERANCE, "Selection AP differs from development table")

    # Fixed deterministic existing rows, chosen by index only, independent of
    # targets, scores, success or failure. No scoring of a new cohort occurs.
    test_indices = np.flatnonzero(test)
    sample_rows = test_indices[np.linspace(0, len(test_indices) - 1, 50, dtype=np.int64)]
    x_train64 = np.asarray(features[dev], dtype=np.float64)
    expected_mean, expected_var = x_train64.mean(axis=0), x_train64.var(axis=0, ddof=0)
    model_checks = {}
    for index, name in enumerate(METHODS):
        artifact = joblib.load(models / f"{name}.joblib")
        columns = protocol["feature_sets"][protocol["models"][name]["feature_set"]]
        require(artifact["feature_indices"] == columns, f"{name}: input column mismatch")
        require(artifact["feature_names"] == [names[i] for i in columns], f"{name}: feature name mismatch")
        require(artifact["training_specimens"] == train_specimens.tolist(), f"{name}: training specimens differ")
        require(artifact["protocol_sha256"] == run["protocol_sha256"] and artifact["selection_sha256"] == selection_hash, f"{name}: frozen provenance mismatch")
        require(artifact["decision_threshold"] == threshold and artifact["target_status"] == protocol["target_status"], f"{name}: status/threshold mismatch")
        model = artifact["estimator"]
        require(np.array_equal(model.classes_, [0, 1]), f"{name}: expected binary classes")
        if hasattr(model, "n_features_in_"):
            require(model.n_features_in_ == len(columns), f"{name}: fitted feature count differs")
        estimator = model[-1] if name.startswith("logistic_") else model
        for key, expected in protocol["models"][name]["params"].items():
            require(estimator.get_params()[key] == expected, f"{name}: fixed parameter differs: {key}")
        check = {"training_specimens": train_specimens.tolist(), "training_rows": int(dev.sum()),
                 "features": len(columns), "model_sha256": digest(models / f"{name}.joblib")}
        if name.startswith("logistic_"):
            scaler = model[0]
            require(int(scaler.n_samples_seen_) == int(dev.sum()), f"{name}: scaler fitted row count differs")
            np.testing.assert_allclose(scaler.mean_, expected_mean[columns], rtol=1e-12, atol=1e-14,
                                       err_msg=f"{name}: scaler means differ from development-only features")
            np.testing.assert_allclose(scaler.var_, expected_var[columns], rtol=1e-10, atol=1e-14,
                                       err_msg=f"{name}: scaler variances differ from development-only features")
            check["scaler"] = {"n_samples_seen": int(scaler.n_samples_seen_),
                               "max_mean_absolute_error": float(np.max(np.abs(scaler.mean_ - expected_mean[columns]))),
                               "max_variance_absolute_error": float(np.max(np.abs(scaler.var_ - expected_var[columns]))),
                               "statistics_match_development_rows_only": True}
        elif name == "dummy_prior":
            np.testing.assert_allclose(model.class_prior_, np.bincount(target[dev], minlength=2) / dev.sum(), rtol=0, atol=1e-15)
            check["class_prior_matches_development_targets_only"] = True
        elif hasattr(model, "_n_samples"):
            require(model._n_samples == int(dev.sum()), "Forest fitted row count differs")
            check["forest_fitted_samples"] = int(model._n_samples)
        with threadpool_limits(limits=2):
            loaded_scores = model.predict_proba(features[sample_rows][:, columns])[:, 1]
        delta = float(np.max(np.abs(loaded_scores - test_scores[sample_rows, index])))
        require(delta <= SCORE_TOLERANCE, f"{name}: reloaded model scores differ: {delta}")
        require(np.array_equal(loaded_scores >= threshold, test_scores[sample_rows, index] >= threshold), f"{name}: reloaded threshold predictions differ")
        check["reloaded_sample_score_max_absolute_error"] = delta
        model_checks[name] = check
    del x_train64

    # Include the prespecified evaluation-only sensitivities in reproducibility.
    sensitivity = pd.read_csv(training / "sensitivity_metrics.csv")
    constant = metadata.channel_2_constant.to_numpy() == 1
    event = metadata.quality_flags.fillna("").str.contains("author_layer_event_affected_region_requires_review", regex=False).to_numpy()
    exclusions = {"all_primary_rows": np.zeros(len(target), dtype=bool),
                  "exclude_constant_nir_evaluation_only": constant,
                  "exclude_author_event_evaluation_only": event}
    require(len(sensitivity) == 2 * len(METHODS) * len(exclusions), "Sensitivity row count differs")
    for phase, mask, scores in (("development_oof", dev, oof), ("test", test, test_scores)):
        for label, excluded in exclusions.items():
            subset = mask & ~excluded
            for index, name in enumerate(METHODS):
                saved = sensitivity[(sensitivity.phase == phase) & (sensitivity.subset == label) & (sensitivity.method == name)]
                require(len(saved) == 1, "Missing/duplicated sensitivity row")
                require(int(saved.iloc[0].excluded_rows) == int((mask & excluded).sum()), "Sensitivity exclusion count differs")
                compare_metrics(saved.iloc[0], own_metrics(target[subset], scores[subset, index], threshold), f"{phase}/sensitivity/{label}/{name}", differences)
    for name, expected in checked_hashes.items():
        require(digest(root / name) == expected, f"Artifact changed during verification: {name}")
    for name, expected in score_hashes.items():
        require(digest(training / name) == expected, f"Saved predictions changed during verification: {name}")
    maxima = {key: max(item["absolute_deltas"].get(key, 0) for item in differences)
              for key in own_metrics(target[test], test_scores[test, 0], threshold)}
    result = {
        "status": "passed", "created_utc": datetime.now(timezone.utc).isoformat(),
        "verification_script_sha256": digest(Path(__file__)), "python": platform.python_version(),
        "scope": "Reproducibility checks of the same frozen saved predictions and model artifacts; no refit, new evaluation cohort, search, threshold change, or holdout-based selection.",
        "target_status": protocol["target_status"], "unknown_rows_excluded": int((~eligible).sum()),
        "development_rows": int(dev.sum()), "test_rows": int(test.sum()),
        "development_specimens": train_specimens.tolist(), "test_specimens": test_specimens.tolist(),
        "specimen_overlap": [], "all_development_folds_group_disjoint": True,
        "selected_primary_method_follows_frozen_development_rule": expected_selection,
        "selection_sha256": selection_hash, "frozen_hashes_verified": checked_hashes,
        "saved_prediction_sha256": score_hashes, "saved_predictions_unchanged": True,
        "metric_comparisons": len(differences), "maximum_metric_absolute_deltas": maxima,
        "exact_confusion_counts_match": True,
        "precision_note": "Training development-fold and holdout tables use float64 predict_proba; saved prediction tensors/CSVs are float32. Development pooled and sensitivity tables already use float32. Ranking metric deltas may arise from float32 ties; exact threshold confusion counts are required to match.",
        "tolerances": {"average_precision_and_roc_auc": RANK_METRIC_TOLERANCE,
                       "other_rates": RATE_TOLERANCE, "counts": 0, "reloaded_scores_absolute": SCORE_TOLERANCE},
        "sample_reload_catalog_rows": sample_rows.tolist(), "model_checks": model_checks,
        "scaler_audit_scope": "Saved final logistic refits only; their sample counts and moments match eligible development features. CV scaler objects were not saved and cannot be independently reloaded.",
        "feature_descriptor_read_only_audit": {"result": "passed", "issues": [],
            "checked": ["sensor-only function inputs", "population standard deviation", "linear quantiles",
                        "x/y neighbor axes", "gradient RMS normalization", "entropy bin boundaries including 1",
                        "zero-count entropy terms", "all-zero/constant images", "empty batch", "unit-interval input guard"]},
        "validation_flags_remain_false": True,
        "metric_differences": differences,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write("\n")
    print(json.dumps({key: result[key] for key in ("status", "development_rows", "test_rows", "metric_comparisons", "maximum_metric_absolute_deltas")}, indent=2))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    verify(args.root, args.output or args.root / "results/baseline_v1_2026-11-08/verification.json")


if __name__ == "__main__":
    main()
