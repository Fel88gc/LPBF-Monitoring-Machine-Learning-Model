# Snow audit and provisional review pipeline

This workflow audits the existing pilot. It preserves original code/data and does not train an ML model or approve scientific labels.

Use the existing project environment from the project root:

```powershell
& '.\.venv\Scripts\python.exe' -B src/cleaning_pipeline/run_audit.py --root . --run-id a_new_unique_run
```

Choose a new run ID every time. The workflow refuses an existing audit, review or report destination. A partial failed run is kept for diagnosis; choose a new ID after repairing its cause.

The current source data are the 128 GB Snow HDF5 in `data/raw/`, the original pilot `data/processed/snow_pilot_patches.npz.npz`, and its CSV manifest. The double extension is intentional here: this is the actual original filename. Original scripts under `src/` are inspected, not imported or automatically rerun.

## Steps

1. Capture SHA-256 hashes for original scripts, processed pilot files and prior results, plus the raw HDF5 size and modification time. Do not scan all 128 GB just for a checksum.
2. `inspect_registration.py`: bounded HDF5 metadata, ID semantics, stored chunk information, selected small records, original-script inventory. Raw HDF5 mode is `r`.
3. `audit_pilot.py`: file consistency, duplicates, image quality, class distribution, threshold sensitivity and specimen-holdout planning. No threshold or split is selected.
4. `compare_spatial.py`: reproduce all pilot sensor patches/counts; compare three crop policies; save sample-template information and nine candidate alignment figures. No complete XCT layer or volume is loaded.
5. `assemble_review.py`: preserve the exact original X/y/groups/layers arrays and add review/provenance flags. Verify source hashes against the audit before packaging. No relabelling or exclusions.
6. `make_review_figures.py`: two traced P16 examples with the original round policy, and the crop-sensitive cases.
7. Verify protected sources again and write a Markdown report with data dictionary and status checklist.

Outputs are separated:

- `results/data_quality/<run>/`: JSON/CSV evidence and diagnostic figures.
- `data/review/<run>/`: unchanged provisional arrays, full review manifest and flags.
- `reports/data_cleaning/<run>/`: readable report, data dictionary, checklist and image assets.

The reusable audit is designed for this existing selected pilot, not as a general full-build extraction tool. Its expected shape is 2,024 × 3 × 24 × 24. Review the code and workload before extending it to a new population.

## Meaning of the checkpoint

`raw_features_reproduced=true` means the stored sensor values match the original HDF5 under the existing normalization. It does not establish physical registration.

`registration_validated=false` and `coverage_validated=false` mean the evidence is unresolved, not that every row is wrong. The nominal sample template and raw XCT > 0 are not independently verified measurement-coverage masks.

Keep `pilot_round` as the reproduction reference until registered-grid geometry and a scientific label policy are justified. Boundary-sensitive and constant-channel samples are flagged rather than silently removed. No final cleaned training dataset is produced by this audit workflow.

See `reports/data_cleaning/2026-11-08_run01/report.md` and the supervisor questions in the corresponding `results/data_quality` run. The initial source review used the official ORNL description and the downloaded Methods/README now copied into `references/`. A rerun does not independently re-review those publications or make the scientific choices automatically.

## Verification

```powershell
& '.\.venv\Scripts\python.exe' -B -m unittest discover -s src/cleaning_pipeline -p test_coordinate_policy.py -v
```

These regression tests protect the recorded crop conventions, including the known P16 example and adjacent half-open boundaries. They do not test physical registration. Independent rational-arithmetic and direct HDF5 spot-check evidence from the initial audit is saved under `results/data_quality/2026-11-08_run01/verification/`.

`requirements-audit.txt` records versions already installed in the working environment. No package installation was performed. Do not install ML or tomography packages just to run this audit.
