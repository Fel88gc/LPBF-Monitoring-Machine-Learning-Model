"""Freeze Baseline v1 targets, specimen folds and protocol without fitting models.

Unknown candidates keep their specimen's fold but are never supervised. Fold 0 is
a held-out test set; folds 1-4 support development-only grouped validation.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import platform
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
import sklearn
from sklearn.model_selection import StratifiedGroupKFold

SEED = 20261108
STATS = ["mean", "std", "min", "max", "p10", "median", "p90", "p99", "zero_fraction",
         "one_fraction", "mean_abs_dx", "mean_abs_dy", "gradient_rms", "entropy16"]
CHANNELS = ["visible_melt", "visible_recoat", "nir_max"]


def digest(path):
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024**2), b""):
            value.update(block)
    return value.hexdigest()


def save_json(path, value):
    with path.open("x", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, allow_nan=False)
        handle.write("\n")


def save_csv(path, rows):
    with path.open("x", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True, help="NEW protocol directory inside project results")
    args = parser.parse_args()
    root, out = args.root.resolve(strict=True), args.output.resolve()
    if not out.is_relative_to(root / "results") or out == root / "results":
        raise ValueError("Protocol output must be a new directory beneath project results")
    if out.exists():
        raise FileExistsError(f"Refusing to overwrite frozen experiment: {out}")
    manifest = root / "data/cleaned/snow_source_preparation_v1/catalog/manifest.csv"
    summary_path = manifest.parent / "summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    manifest_hash = digest(manifest)
    expected_hash = summary["catalog_artifacts_sha256"]["manifest.csv"]
    if manifest_hash != expected_hash:
        raise ValueError("Canonical catalog manifest SHA256 differs from completed catalog record")
    if summary["ready_for_model_training"] or summary["final_y_exported"]:
        raise ValueError("Expected the explicitly provisional candidate catalog")
    n = summary["rows"]
    assert n == 329828, "Unexpected catalog version/row count"
    catalog_row = np.arange(n, dtype=np.int64)
    candidate_y = np.empty(n, dtype=np.int8)
    groups = np.empty(n, dtype=np.int32)
    count = 0
    with manifest.open(newline="", encoding="utf-8-sig") as handle:
        for index, row in enumerate(csv.DictReader(handle)):
            if index >= n or int(row["catalog_row"]) != index:
                raise ValueError("Catalog order differs from canonical sequential catalog_row")
            label = int(row["candidate_y"])
            if label not in (-1, 0, 1) or int(row["label_validated"]) or int(row["coverage_validated"]):
                raise ValueError("Unexpected target domain or validation status")
            candidate_y[index], groups[index] = label, int(row["part_id"])
            count += 1
    assert count == n
    eligible = np.isin(candidate_y, [0, 1])
    assert int(eligible.sum()) == 323280 and int((~eligible).sum()) == 6548
    assert int(np.count_nonzero(candidate_y == 1)) == 73649
    assert int(np.count_nonzero(candidate_y == 0)) == 249631
    all_groups, supervised_groups = set(map(int, np.unique(groups))), set(map(int, np.unique(groups[eligible])))
    assert len(all_groups) == 64 and all_groups == supervised_groups, "Every group needs eligible rows for stratification"

    splitter = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=SEED)
    eligible_indices = np.flatnonzero(eligible)
    group_fold = {}
    for fold, (train_indices, validation_indices) in enumerate(splitter.split(
            np.zeros((eligible_indices.size, 1), dtype=np.uint8), candidate_y[eligible], groups[eligible])):
        train_groups = set(map(int, groups[eligible_indices[train_indices]]))
        validation_groups = set(map(int, groups[eligible_indices[validation_indices]]))
        assert not train_groups & validation_groups
        for group in validation_groups:
            assert group not in group_fold
            group_fold[group] = fold
    assert set(group_fold) == all_groups
    fold_id = np.fromiter((group_fold[int(group)] for group in groups), dtype=np.int8, count=n)
    fold_counts, group_counts = [], []
    for fold in range(5):
        chosen = fold_id == fold
        supervised = chosen & eligible
        assert set(np.unique(candidate_y[supervised])) == {0, 1}, "Every evaluation fold must contain both classes"
        ids = sorted(int(group) for group, assigned in group_fold.items() if assigned == fold)
        fold_counts.append({"fold_id": fold, "role": "test" if fold == 0 else "development",
                            "specimen_count": len(ids), "specimen_ids": ";".join(map(str, ids)), "all_rows": int(chosen.sum()),
                            "eligible_rows": int(supervised.sum()), "candidate_zero": int(np.count_nonzero(chosen & (candidate_y == 0))),
                            "candidate_one": int(np.count_nonzero(chosen & (candidate_y == 1))), "candidate_unknown": int(np.count_nonzero(chosen & ~eligible))})
    for group in sorted(all_groups):
        chosen = groups == group
        assert np.unique(fold_id[chosen]).tolist() == [group_fold[group]]
        group_counts.append({"part_id": group, "fold_id": group_fold[group], "role": "test" if group_fold[group] == 0 else "development",
                             "all_rows": int(chosen.sum()), "eligible_rows": int(np.count_nonzero(chosen & eligible)),
                             "candidate_zero": int(np.count_nonzero(chosen & (candidate_y == 0))),
                             "candidate_one": int(np.count_nonzero(chosen & (candidate_y == 1))), "candidate_unknown": int(np.count_nonzero(chosen & ~eligible))})
    development_cv = []
    for validation_fold in [1, 2, 3, 4]:
        training_folds = [fold for fold in [1, 2, 3, 4] if fold != validation_fold]
        train_groups = {group for group, fold in group_fold.items() if fold in training_folds}
        validation_groups = {group for group, fold in group_fold.items() if fold == validation_fold}
        test_groups = {group for group, fold in group_fold.items() if fold == 0}
        assert not (train_groups & validation_groups or train_groups & test_groups or validation_groups & test_groups)
        development_cv.append({"validation_fold": validation_fold, "training_folds": training_folds,
                               "training_specimens": sorted(train_groups), "validation_specimens": sorted(validation_groups)})

    logistic_params = {"C": 1.0, "class_weight": "balanced", "solver": "lbfgs", "max_iter": 1000,
                       "tol": 1e-4, "random_state": SEED}
    rf_params = {"n_estimators": 100, "max_depth": 12, "min_samples_leaf": 20, "max_features": "sqrt",
                 "class_weight": "balanced_subsample", "bootstrap": True, "n_jobs": 2, "random_state": SEED}
    models = {"dummy_prior": {"estimator": "DummyClassifier", "params": {"strategy": "prior"}, "feature_set": "combined", "scaler": None},
              "logistic_combined": {"estimator": "LogisticRegression", "params": logistic_params.copy(), "feature_set": "combined", "scaler": "StandardScaler"},
              "random_forest_combined": {"estimator": "RandomForestClassifier", "params": rf_params, "feature_set": "combined", "scaler": None},
              "logistic_visible": {"estimator": "LogisticRegression", "params": logistic_params.copy(), "feature_set": "visible", "scaler": "StandardScaler"},
              "logistic_nir": {"estimator": "LogisticRegression", "params": logistic_params.copy(), "feature_set": "nir", "scaler": "StandardScaler"}}
    protocol = {
        "schema_version": 1, "created_utc": datetime.now(timezone.utc).isoformat(), "experiment": "baseline_v1_2026-11-08",
        "seed": SEED, "target_status": "provisional_candidates_exploratory", "unknown_excluded": 6548,
        "unknown_handling": "Retained in prepared data and split manifest with their specimen fold; excluded from all supervised fitting/scoring",
        "test_fold": 0, "development_folds": [1, 2, 3, 4], "primary_metric": "average_precision", "decision_threshold": .5,
        "selection_rule": "highest mean development AP among dummy_prior/logistic_combined/random_forest_combined; within 1e-4 prefer simpler dummy then logistic then RF",
        "model_selection_candidates": ["dummy_prior", "logistic_combined", "random_forest_combined"],
        "selection_tie_tolerance": 1e-4, "simplicity_order": ["dummy_prior", "logistic_combined", "random_forest_combined"],
        "feature_names": [f"{channel}_{stat}" for channel in CHANNELS for stat in STATS],
        "feature_sets": {"combined": list(range(42)), "visible": list(range(28)), "nir": list(range(28, 42))},
        "models": models, "development_cv": development_cv,
        "evaluation_flow": "Evaluate five predeclared methods in development folds; select the primary combined model using development AP only; freeze choice; refit each fixed method on all eligible development rows and evaluate held-out fold 0 once; no test-based retuning",
        "scaling_policy": "StandardScaler for logistic regression fitted only on the current training fold; refit on development rows before held-out test. No scaler fitted on test or unknown rows.",
        "quality_flags_policy": "Retain source-flagged eligible rows in primary fitting/evaluation; no automatic flag-based exclusions",
        "sensitivity_policy": {"stage": "evaluation_only", "refit": False,
                               "subsets": {"exclude_constant_nir": "exclude rows with channel_2_constant=1 from evaluation only",
                                           "exclude_author_event": "exclude rows bearing author_layer_event_affected_region_requires_review from evaluation only"},
                               "interpretation": "Separate prespecified robustness summaries on fixed predictions; no retraining, selection or threshold adjustment"},
        "prohibited_predictors": ["sample_id", "catalog_row", "part_id", "layer", "camera_y", "camera_x", "coords", "XCT crop bounds", "flaw pixels", "candidate_y", "coverage proxies", "sample template fields", "quality/provenance flags", "all other metadata or XCT fields"],
        "secondary_metrics": ["precision", "recall", "f1", "balanced_accuracy", "roc_auc", "confusion_matrix"],
        "stratification_note": "Eligible labels guide approximate class balance with nonoverlapping specimen groups. All unknown rows inherit their specimen fold; this is one build, not cross-build validation.",
        "no_model_training_by_freeze_step": True,
        "input_provenance": {"catalog_manifest": str(manifest.relative_to(root)), "catalog_manifest_sha256": manifest_hash,
                             "expected_catalog_manifest_sha256": expected_hash, "catalog_summary": str(summary_path.relative_to(root)),
                             "catalog_summary_sha256": digest(summary_path), "source_worker_sha256": summary["worker_sha256"],
                             "freeze_script_sha256": digest(Path(__file__))},
        "environment": {"python": platform.python_version(), "numpy": np.__version__, "scikit_learn": sklearn.__version__},
        "splitter": {"name": "StratifiedGroupKFold", "n_splits": 5, "shuffle": True, "random_state": SEED,
                     "reference": "https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.StratifiedGroupKFold.html"},
    }
    split_summary = {"all_rows": n, "eligible_rows": int(eligible.sum()), "unknown_rows": int((~eligible).sum()),
                     "specimen_count": len(all_groups), "group_overlap": False, "fold_counts": fold_counts,
                     "specimen_to_fold": {str(group): group_fold[group] for group in sorted(all_groups)},
                     "test_specimens": [row["part_id"] for row in group_counts if row["fold_id"] == 0],
                     "development_specimens": [row["part_id"] for row in group_counts if row["fold_id"] != 0],
                     "assertions_passed": ["canonical_row_order", "expected_329828_rows", "expected_323280_eligible_6548_unknown", "all_64_groups_assigned_once", "no_specimen_overlap", "both_classes_each_fold", "test_never_in_development_cv", "catalog_manifest_sha256_matches"]}
    out.mkdir(parents=True, exist_ok=False)
    with (out / "splits.npz").open("xb") as handle:
        np.savez_compressed(handle, fold_id=fold_id, eligible=eligible, candidate_y=candidate_y, groups=groups, catalog_row=catalog_row)
    save_csv(out / "grouped_counts.csv", group_counts)
    save_csv(out / "fold_counts.csv", fold_counts)
    save_json(out / "split_summary.json", split_summary)
    with manifest.open(newline="", encoding="utf-8-sig") as incoming, (out / "split_manifest.csv").open("x", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["sample_id", "catalog_row", "part_id", "candidate_y", "fold_id", "eligible", "role"])
        writer.writeheader()
        for index, row in enumerate(csv.DictReader(incoming)):
            assert int(row["catalog_row"]) == index and int(row["part_id"]) == groups[index] and int(row["candidate_y"]) == candidate_y[index]
            writer.writerow({"sample_id": row["sample_id"], "catalog_row": index, "part_id": int(groups[index]),
                             "candidate_y": int(candidate_y[index]), "fold_id": int(fold_id[index]), "eligible": int(eligible[index]),
                             "role": "unknown" if not eligible[index] else "test" if fold_id[index] == 0 else "dev"})
    if digest(manifest) != manifest_hash:
        raise RuntimeError("Catalog manifest changed while freezing experiment; do not use this protocol")
    save_json(out / "protocol.json", protocol)
    with (out / "README.md").open("x", encoding="utf-8") as handle:
        handle.write("# Frozen exploratory Baseline v1\n\nNo model is fitted by this step. The target is a provisional dataset annotation candidate. "
                     "Five fixed specimen folds are saved for every catalog row; unknown rows remain assigned to their specimen fold but are not supervised. "
                     "Fold 0 is reserved test. Folds 1-4 are development folds, with one held out at a time for four development validation runs. "
                     "Selection uses development average precision only among the three primary combined methods. Modality ablations are predeclared comparisons. "
                     "There is no test-based tuning or source-flag deletion. See protocol.json for parameters, features, leakage restrictions and evaluation-only sensitivities.\n")
    save_json(out / "artifact_hashes.json", {path.name: digest(path) for path in sorted(out.iterdir()) if path.is_file()})
    print(json.dumps({"output": str(out), **split_summary}, indent=2))


if __name__ == "__main__":
    main()
