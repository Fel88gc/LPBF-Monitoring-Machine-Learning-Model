# Exploratory Baseline v1

This workflow predicts the current provisional XCT annotation candidates from sensor images. It does not validate the physical registration, coverage proxy, annotations or cross-build transfer. The source catalog's readiness and validation flags remain unchanged.

## Completed experiment

- Source: 329,828 patches, 64 fatigue specimens, layers 519-660 in one build.
- Image-only features: 14 fixed descriptors per sensor channel, 42 combined.
- Supervised rows: 323,280 provisional 0/1 candidates. The 6,548 unknowns are retained but excluded from training and scores.
- Frozen five-fold specimen partition, seed 20261108. Fold 0: 12 test specimens / 60,911 eligible rows. Folds 1-4: 52 development specimens / 262,369 rows, four development validations.
- Five fixed methods: dummy prior, logistic combined, random forest combined, logistic visible, logistic NIR.
- Primary model selection: mean development fold AP among dummy / logistic combined / forest combined; tie tolerance 0.0001 and simplicity preference. Fixed score threshold 0.5.
- Selected primary: random forest combined. Mean development fold AP 0.7120; held-out AP 0.7822. Dummy held-out AP 0.2515.
- Caveat: mean within-specimen ROC AUC 0.5761 and zero recall on P57/P65 at threshold 0.5. Pooled performance is insufficient evidence of useful local flaw detection.

## Artifacts

Project-relative paths below resolve from the FYP project root:

| Path | Content |
|---|---|
| `data/features/baseline_v1_2026-11-08/` | Features, dictionary, metadata, targets, groups and verified shard provenance |
| `results/baseline_v1_2026-11-08/protocol/` | Frozen parameters, feature order, specimen folds, split manifest and hashes |
| `results/baseline_v1_2026-11-08/training/` | Run log, development and held-out predictions, metrics, selection record and sensitivities |
| `results/baseline_v1_2026-11-08/verification.json` | Independent reproducibility checks; no refit |
| `models/baseline_v1_2026-11-08/` | Five development-only final refits, with input order and provenance |
| `reports/baseline_v1_2026-11-08/` | Results narrative, figures, gallery source rows and PDF addendum |

## Commands and output guards

Use the existing project `.venv`; no new dependency installation is required. All producers refuse existing output directories. The following commands describe the completed run; use a **new versioned output path** for any intentional new experiment. Re-running training on an inspected holdout does not restore its original untouched status.

```powershell
.\.venv\Scripts\python.exe src/modeling/freeze_experiment.py --root . --output results/baseline_v1_2026-11-08/protocol
.\.venv\Scripts\python.exe src/modeling/extract_features.py --root . --output data/features/baseline_v1_2026-11-08
.\.venv\Scripts\python.exe src/modeling/train_baselines.py --root .
.\.venv\Scripts\python.exe src/modeling/verify_results.py --root .
```

Metric and feature fixtures:

```powershell
.\.venv\Scripts\python.exe -B -m unittest discover -s src/modeling -p 'test_*.py' -v
```

`fit_and_score` fits the scaler within the current training partition. Model inputs are feature columns only. IDs, coordinates, layers, XCT counts, support proxies and flags are diagnostics, never predictors. Final models fit the 52 development specimens only; test specimens are absent from their fitted samples.

Model artifacts are dictionaries containing `estimator`, `feature_indices`, `feature_names`, target status, threshold, protocol/selection hashes and training specimens. Supply the feature indices in the documented order. Class-weighted model outputs are uncalibrated scores, not physical defect probabilities.

Tables use the original float64 estimator scores. Prediction tensors and their CSVs store float32 scores; independent verification found identical threshold counts and ranking differences below 2.5e-7. No performance conclusion depends on this storage rounding. All scores use the same prepared rows and fixed decision rule.

## Next research step

Review target geometry, usable XCT support and annotation meaning; build a documented visual audit; then investigate nuisance structure using development data. A CNN or tuned threshold should follow a declared Baseline v2 protocol and suitable new evaluation evidence. Fold 0 is now an inspected result. One build cannot establish cross-build generalisation.
