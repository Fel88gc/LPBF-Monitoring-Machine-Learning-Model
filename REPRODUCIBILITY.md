# Repository dependency and reproducibility review

Read-only review completed 15 November 2026. Source: `C:/NUS/FYP/FYP Organized/src/` and `work/`, including historical pilot scripts, all cleaning/model/diagnostic modules, and all PDF/report helpers. No source script, raw HDF5, Git state, model, or original output was modified or executed. The package version check queried installed distribution metadata only.

## Inventory and direct dependencies

All **48 Python files** in `src/` and `work/` parsed successfully. No notebooks, MATLAB, JavaScript, shell, PowerShell or batch source files were found outside the excluded environment/data trees in this review.

| Install name | Import name | Role | Verified project-venv version |
|---|---|---|---|
| numpy | numpy | Sensor arrays, feature extraction, metrics | 2.4.6 |
| h5py | h5py | Read source HDF5 and inspect datasets | 3.16.0 |
| matplotlib | matplotlib | Scientific plots and review figures | 3.11.2 |
| scipy | scipy | Distribution normal references | 1.17.1 |
| pandas | pandas | Metadata/results tables and plotting | 3.1.0 |
| Pillow | PIL | Image export and report asset sizing | 13.0.0 |
| scikit-learn | sklearn | Frozen grouped split, baseline/control models, metrics | 1.9.1 |
| joblib | joblib | Save/load baseline models | 1.6.0 |
| threadpoolctl | threadpoolctl | Limit numerical threads in model work | 3.7.0 |
| reportlab | reportlab | PDF report builders in `work/` | Not installed in the project venv; earlier PDF builds used the bundled document runtime |

The existing `src/cleaning_pipeline/requirements-audit.txt` is accurately described as a historical six-package environment snapshot. It covers NumPy, h5py, Matplotlib, SciPy, pandas and Pillow; it does **not** cover the complete modeling/PDF code.

For a compact source-repository dependency arrangement, use the nine verified packages above in the main requirements file and `reportlab` in an optional report requirements file, or include all ten in one full requirements file. If pinning ReportLab, first record the actual report runtime version; this review did not invent one. Joblib/threadpoolctl are scikit-learn dependencies but should remain explicit because the code imports them directly.

The recorded scientific stack requires **Python 3.11 or newer** (confirmed `Requires-Python` metadata for NumPy, Matplotlib, SciPy, pandas, Pillow and scikit-learn). The original experiment used Python **3.11.4**. A compatible newer interpreter is not a promise of byte-identical historical model output.

No checked-in Python imports PyTorch, TensorFlow, OpenCV, scikit-image, TomoPy, Algotom or ASTRA. The report discusses tomography packages; it does not use them. `pypdf`, `pdfplumber`, Poppler, `python-docx`, pytest, Jupyter and Node are **not core runtime dependencies** of these 48 Python files. PDF rendering/QA tools may be separately useful, but should not be presented as prerequisites for model fixtures.

## Suggested README setup and first commands

Use a fresh environment; do not copy `.venv` into Git. Run commands from the cloned repository root. Example Windows PowerShell setup, assuming the repository's main requirements file has been created:

```powershell
py -3.11 -m venv .venv
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

The data-free analytical fixtures are the most sensible first execution. They check feature mathematics, evaluation behavior and recorded crop conventions without opening the experimental HDF5:

```powershell
& .\.venv\Scripts\python.exe -B -m unittest discover -s src/modeling -p 'test_*.py' -v
& .\.venv\Scripts\python.exe -B -m unittest discover -s src/cleaning_pipeline -p test_coordinate_policy.py -v
```

These commands were inspected, not rerun by this review. The source uses `unittest`; pytest is unnecessary. Avoid `python -m unittest discover` from the root as the only instruction, because the repository's directory layout and local imports are handled by the explicit discovery directories above.

For a new source metadata inventory, `src/inspect_snow.py` is the portable early entry point: it accepts the HDF5 path as a positional argument. The other top-level `src/inspect_snow_*` files are historical scripts with more fixed assumptions.

## Data prerequisites and pipeline order

This is a preserved research workflow, not a code-only one-command reproduction. The HDF5 is approximately 128 GB and is not a Python dependency. Explain how to obtain the Snow release separately and preserve the expected filename:

`data/raw/2024-05-01 M2 AMMTO Fatigue Blanks 05.hdf5`

The source DOI already documented in the project is `10.13139/ORNLNCCS/2524534`. Source/references, prepared arrays, frozen results and model files are separate prerequisites when an artifact is omitted from Git. Source code alone does not contain trained models, input arrays or the historical review population.

The main source-preparation sequence, with **new/nonexistent destinations**, is:

```powershell
& .\.venv\Scripts\python.exe -B src/cleaning_pipeline/index_source_layers.py --root . --output data/cleaned/snow_source_preparation_v1
& .\.venv\Scripts\python.exe -B src/cleaning_pipeline/prepare_source_dataset.py --root . --output data/cleaned/snow_source_preparation_v1
& .\.venv\Scripts\python.exe -B src/cleaning_pipeline/consolidate_source_preparation.py --root . --source data/cleaned/snow_source_preparation_v1 --output data/cleaned/snow_source_preparation_v1/catalog
```

`index_source_layers.py` must precede `prepare_source_dataset.py`, because it creates the required configuration. Interrupted production uses `prepare_source_dataset.py ... --resume`; completed production is protected and cannot simply be resumed again. The single-layer worker is `prepare_source_layer.py --root . --layer 600 --output <new-shard-directory>`.

After restoring/creating the expected catalog, the frozen-baseline entry points are:

```powershell
& .\.venv\Scripts\python.exe -B src/modeling/freeze_experiment.py --root . --output results/baseline_v1_2026-11-08/protocol
& .\.venv\Scripts\python.exe -B src/modeling/extract_features.py --root . --output data/features/baseline_v1_2026-11-08
& .\.venv\Scripts\python.exe -B src/modeling/train_baselines.py --root .
& .\.venv\Scripts\python.exe -B src/modeling/verify_results.py --root .
```

**Important:** These are the historical command sequence, not a promise that a fresh checkout can execute all four unchanged. The trainer additionally requires `work/baseline_2026-11-08_run01.json`, the original files listed by that preservation snapshot, and the expected raw-source size/modification time. It checks a fixed catalog SHA, fixed row counts and named versioned paths. A newly downloaded file may have a different filesystem modification time. Preserve the historical snapshot when reproducing it, or design a separate documented new-run procedure rather than disabling guards or silently treating changed inputs as the original experiment.

The fixed historical cohort is 329,828 patches, 64 specimens and layers 519-660. Features and target candidates remain separate; unknown `-1` rows are retained but excluded from supervised fitting. The baseline is exploratory agreement with provisional XCT-derived candidates, not physically validated pore detection. Fold 0 has already been inspected; rerunning it does not produce a new untouched test.

Development-only follow-up entry points are:

```powershell
& .\.venv\Scripts\python.exe -B src/diagnostics/audit_training_split.py
& .\.venv\Scripts\python.exe -B src/diagnostics/distribution_diagnostics.py --root .
& .\.venv\Scripts\python.exe -B src/diagnostics/nuisance_audit.py --root .
& .\.venv\Scripts\python.exe -B src/diagnostics/build_review_pack.py --root .
```

They expect the original fixed feature/protocol/result paths. The nuisance audit requires the saved development OOF scores and baseline verification; it does not need the original held-out score file. The physical review pack additionally needs prepared feature shards and bounded read-only HDF5 crops. Each producer protects its existing named output, so these examples belong under an explicit historical/reproduction section rather than an unconditional quick-start.

## Keep the pilot code and explain its scope

The user's earlier exclusion of pilot material concerned a report, not deletion of historical code. Retain the original top-level extraction/inspection scripts and `src/cleaning_pipeline/` audit workflow.

The existing cleaning README is specific to the **2,024-row historical pilot** and correctly says it is not a full-build extraction tool. Its recorded original archive is `data/processed/snow_pilot_patches.npz.npz`; the double extension is intentional. The reusable pilot-audit command is:

```powershell
& .\.venv\Scripts\python.exe -B src/cleaning_pipeline/run_audit.py --root . --run-id a_new_unique_run
```

It requires the pilot archive, manifest and raw source; it preserves those files and does not train a model. Keep this explanation distinct from the later 64-specimen source-preparation and modeling pipelines.

## Portability and import-time behavior

- Many legacy top-level `src/*.py` scripts hardcode `C:\NUS\FYP\FYP Organized\data\raw`; `export_snow_slide6_xct_masks.py` hardcodes the entire project root. They are archival entry points to inspect/adapt intentionally, not portable default commands.
- Most newer pipeline/model scripts accept `--root` and support relocation within the expected directory structure. `audit_training_split.py` derives the project root from its own path. Several report helpers instead use `Path.cwd()`, so they must run from the repository root.
- Historical scripts without a main guard can perform data access or writes when imported: `audit_snow_ml_patches.py`, `build_snow_pilot_dataset.py`, `check_snow_label_mapping.py`, `check_snow_xct_storage.py`, `export_snow_slide6_xct_masks.py`, `find_snow_xct.py`, `inspect_snow_metadata.py`, `inspect_snow_stage3.py`, `verify_snow_alignment.py`, `visualize_snow.py`, `visualize_snow_xct.py`, and `work/prepare_ahead.py`. Do not smoke-test the repository by importing every module or passing `--help` to these scripts. `src/modeling/evaluation.py` also has no main guard but is a definitions-only helper, not a data-producing script.
- `work/prepare_ahead.py` is a one-off staging/parallel-production helper fixed to layers 620-660. It should be preserved as history, not advertised as the normal workflow.
- The project layout is script-oriented, with local sibling imports such as `evaluation` and `compare_spatial`. Use the recorded direct script commands/discovery directories; it is not currently an installable Python package with a CLI entry point.
- Frozen JSON/CSV provenance was generated on Windows and can contain backslash paths. Restoring those artifacts on Linux is not equivalent to generating fresh POSIX paths; `Path` does not reinterpret all Windows separators on another OS. Several scripts also compare exact source/manifest bytes and hashes. Avoid an unsupported claim of complete cross-platform reproducibility.
- Byte-sensitive provenance means Git line-ending normalization can matter for existing script hashes. A `.gitattributes` policy that preserves imported snapshot bytes, and a documented distinction between historical and future runs, are preferable to silently changing line endings and claiming original-hash identity. Mixed original CRLF/new LF source exists in the project.

## Report helper dependencies and order

Keep **all** report helpers under `work/`, including its `integrated_report/` subtree. `build_development_diagnostics_brief.py` imports `work/integrated_report/build_integrated_report.py` as its layout module, so flattening those folders would break it.

PDF builders (`work/build_fyp_progress_report.py`, `work/build_baseline_report.py`, `work/integrated_report/build_integrated_report.py`, and the development brief through its import) load **Arial TTF files from `C:/Windows/Fonts` at import time**. Installing ReportLab alone does not make those builders portable. A Linux user would need a deliberate configurable-font adaptation; no such refactor was performed in this review.

Figure/report stages expect saved analysis artifacts and often existing assets from earlier report stages:

1. `work/report_figures.py --root .`: figures from source catalog tables.
2. `src/modeling/plot_results.py --root .`: baseline-result figures; gallery uses saved shard patches. `--skip-gallery` omits that gallery only.
3. `src/reporting/make_integrated_diagrams.py --root .`: conceptual report diagrams.
4. `work/integrated_report/make_source_examples.py`: three bounded source/XCT examples and copied prior source/baseline figures.
5. `work/integrated_report/build_integrated_report.py`: the integrated PDF using those assets and saved results.
6. `work/build_development_diagnostics_brief.py`: later development findings and pending-review PDFs after diagnostic outputs/assets exist.

Some builders offer `--replace` for their own generated artifacts during layout revision; that is not a general permission to overwrite input data. Existing PDF/page-count assertions are report-specific. Report helpers and historical figures are useful for reproducibility, but do not represent new model training or an automatic universal report generator.

## Recommended short README wording

> This repository preserves the FYP research code: original Snow dataset inspection and pilot scripts, source-data preparation, an exploratory image-feature baseline, development-only diagnostics, and report-generation helpers. Start with the data-free unit tests. Reproducing data-backed stages requires the separately obtained Snow HDF5 and the documented historical artifacts/layout; the repository is not a self-contained dataset or pretrained-model package. The pipeline keeps provisional candidate annotations separate from physical validation and keeps whole specimens together during evaluation. Several archived scripts retain Windows paths and fixed research-run assumptions, documented below.

No Git commands, pushes, secret-file reads, dependency installation, training or raw HDF5 reads were performed for this review.
