# LPBF Monitoring Machine Learning Model

FYP research code for investigating whether visible-light and near-infrared process images from laser powder bed fusion relate to local XCT flaw annotations.

This repository preserves the original inspection scripts, source preparation, exploratory models, development diagnostics, and report-generation code. It also includes the latest [data and cleaning report](reports/FYP_Data_and_Cleaning_Update.pdf).

## Project status

- Prepared source scope: one Snow build, 64 fatigue specimens, layers 519-660 inclusive.
- Prepared catalogue: 329,828 three-channel 24 x 24 sensor patches.
- Provisional XCT statuses: 73,649 candidate 1, 249,631 candidate 0, and 6,548 unknown.
- Physical crop correspondence, measured XCT support and annotation meaning remain unresolved. The counts are not confirmed pore counts.
- The historical feature baseline and diagnostic code are included for completeness. Its pooled results do not establish validated physical-pore detection. The v1 test has already been inspected.

## Repository contents

| Path | Contents |
| --- | --- |
| `src/` | Original inspection and extraction scripts, cleaning pipeline, modelling and diagnostics |
| `work/` | Original report helpers, their subtree imports and historical preservation snapshot |
| `reporting/codex/` | Later report, figure, PDF QA and presentation authoring scripts, preserved by original workspace subfolder |
| `docs/` | Existing project handoff and workflow documentation |
| `config/` | Small historical scope/protocol snapshots |
| `data/README.md` | Where to obtain the source and how local data are arranged |
| `reports/` | Latest professor-facing data-cleaning PDF |
| `SOURCE_MANIFEST.csv` | File origin labels and checksums for the imported snapshot |
| `REPRODUCIBILITY.md` | Execution order, dependencies and limitations |

The original pilot scripts remain as historical code. Their exclusion from the professor-facing report did not remove them from the project archive.

## Set up Python

Use Python 3.11 or newer. Run from the repository root in PowerShell:

```powershell
py -3.11 -m venv .venv
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

For the PDF helpers, additionally install `requirements-reporting.txt`. The presentation scripts using `@oai/artifact-tool` require the original bundled authoring runtime; no substitute Node package or copied runtime is included here.

## Data-free checks

```powershell
& .\.venv\Scripts\python.exe -B -m unittest discover -s src/modeling -p 'test_*.py' -v
& .\.venv\Scripts\python.exe -B -m unittest discover -s src/cleaning_pipeline -p test_coordinate_policy.py -v
```

These fixture tests do not read the large experimental HDF5. Do not import all legacy scripts as a smoke test: some perform file I/O immediately on import.

## Data-backed execution

Read [REPRODUCIBILITY.md](REPRODUCIBILITY.md) before running producers. Data, prepared arrays, model binaries, saved results, the virtual environment and publisher PDFs are not included in Git. Some historical scripts retain absolute Windows paths, original run dates and exact input hashes. A fresh checkout is a code archive and a starting point for reproducing the workflow, not a self-contained dataset or pretrained model.

The active local FYP working folder was left unchanged when this repository snapshot was prepared.

## Sources

- Snow et al. dataset: https://doi.org/10.13139/ORNLNCCS/2524534
- Dinh, Muller and Quinsat (2021): https://doi.org/10.14733/cadaps.2021.1111-1118
- TomoPy: https://tomopy.readthedocs.io/en/stable/
- Algotom: https://algotom.readthedocs.io/en/latest/
- ASTRA: https://astra-toolbox.com/

This repository does not redistribute those external datasets, papers or software runtimes, and does not assign a new license to third-party material.
