# NUS FYP — Codex Handoff and Automated Data-Cleaning Brief

**Prepared for:** Felix (NUS Mechanical Engineering FYP)  
**Status:** Data exploration and preliminary pilot extraction completed; data quality and spatial registration **not yet scientifically validated**.  
**Scope of this Codex task:** Audit, repair, and document the data preparation process. **Stop before training any machine-learning model.**

> **To Codex:** Treat this as the primary context and execution brief for this task. The student is new to Python/ML and wants you to make safe, steady progress autonomously, explaining the purpose of major steps in plain language. Do not simply produce a plan and stop: inspect the actual project, perform read-only diagnostics, implement reproducible validation utilities, run them where access permits, and deliver an evidence-backed cleaning report. Pause when a consequential scientific decision or access/permission approval is required.

## 1. Project context and research objective

- Student: Felix; supervisors: Prof. Swee Leong (Prof Sing) and Prof. Mehdi.
- Field: laser powder bed fusion (LPBF) process monitoring using machine learning.
- **Working research question:** Can in-situ visible-light and NIR sensor images acquired during LPBF printing predict the presence of internal flaws identified subsequently by X-ray computed tomography (XCT)?
- The immediate research task is **not** defect prediction yet. First, establish a **correct, reproducible mapping** between sensor-image regions and XCT annotations, and produce trustworthy labelled data suitable for later ML evaluation.
- Aim for a feasible FYP. Do not introduce a large 3D tomography reconstruction, novel CNN architecture, or fatigue-prediction task without a demonstrated need and supervisor approval.
- The student's key conceptual distinction: **sensor images are potential model inputs; XCT flaw annotations are source data from which the project generates provisional 0/1 patch targets**. These binary patch targets were **not** directly supplied as a ready-made dataset by Snow et al.

## 2. Snow dataset: primary source and what exists

Dataset: Snow et al. (2025), *In situ Visible Light and Thermal Imaging Data from a Laser Powder Bed Fusion Additive Manufacturing Process Co-Registered to X-ray Computed Tomography and Fatigue Data*, Oak Ridge National Laboratory (ORNL).  
Official dataset DOI: https://doi.org/10.13139/ORNLNCCS/2524534  
ORNL landing page: https://doi.ccs.ornl.gov/dataset/bc373c52-5cdd-50cd-bb81-dcc85799fe35

- This is one LPBF experimental build containing **64 stainless-steel 316H cylinders**; **60** of the cylinders were later fatigue tested. Do **not** misstate this as 60 separate printing builds.
- Modalities include high-resolution layerwise visible imagery, integrated near-infrared (NIR) sensing, scan-path information, registered XCT measurements/flaw annotations, and fatigue results.
- The ORNL description says the in-situ and XCT data were co-registered to the build-plate coordinate system. **Do not assume the student-written coordinate conversion has implemented that registration correctly.** Investigate the actual HDF5 axes/origin, pixel spacing, and available metadata.
- The local raw file is approximately 128 GB and resides on the student's Windows PC at:

  `C:\NUS\FYP\FYP Organized\data\raw\2024-05-01 M2 AMMTO Fatigue Blanks 05.hdf5`

- **Open this file read-only with `h5py.File(path, "r")`. Never copy, re-compress, rewrite, or load the full 128 GB file into RAM.** Use small HDF5 slices and chunk-aware processing.
- Relevant paths already observed in the file:

  | HDF5 path | Role |
  |---|---|
  | `/slices/camera_data/visible/0` | Visible post-melt image input |
  | `/slices/camera_data/visible/1` | Visible post-recoat image input |
  | `/slices/camera_data/nir/1` | NIR integrated-max image input used by current scripts |
  | `/slices/registered_data/x-ray_ct_data` | Reconstructed/registered grayscale XCT data |
  | `/slices/registered_data/x-ray_ct_flaw` | XCT flaw-annotation image |
  | `/slices/part_ids` | Specimen-ID raster |
  | `/slices/sample_ids` | Sample/coverage-related raster; investigate semantics in metadata |

- Prior HDF5 audits found `1117` indexed slices (indices `0–1116`); the XCT datasets have shape `(1117, 13752, 13752)`, while the part-ID camera-resolution map has shape `(1117, 2844, 2844)`. Some XCT gauge-section coverage is limited to selected layers/regions; zero flaw pixels must **not** be confused with absent XCT coverage.
- Existing metadata report indicated: `slices/indexing` starts at `0`, the slice origin corresponds to the printer's physical origin, array X runs along the second dimension and Y along the first; carefully check plotting origins and Y-axis direction.

## 3. Existing local project and scripts

Project root on the student's PC:

`C:\NUS\FYP\FYP Organized`

Inside `src/`, the student has:

```text
audit_snow_ml_patches.py
build_snow_pilot_dataset.py
check_snow_xct_storage.py
export_snow_slide6_xct_masks.py
find_snow_xct.py
inspect_snow_metadata.py
inspect_snow_stage2.py
inspect_snow_stage3.py
inspect_snow.py
verify_snow_alignment.py
visualize_snow_xct.py
visualize_snow.py
```

Priority: **read these files before adding new code**, particularly `build_snow_pilot_dataset.py`, `audit_snow_ml_patches.py`, `verify_snow_alignment.py`, and `export_snow_slide6_xct_masks.py`. Inspect any new diagnostic file the student has since added, such as `check_snow_label_mapping.py`.

Existing derived files, normally under `data/processed/`:

```text
snow_pilot_patches.npz
snow_pilot_manifest.csv
```

The existing pilot builder script has these characteristics:

- Selected specimen IDs: `2, 9, 16, 24, 35, 43, 52, 60`.
- Selected layer indices: `540, 560, 580, 600, 620, 638, 640`.
- Camera patch size: `24 × 24` pixels, with three channels: visible post-melt, visible post-recoat, NIR integrated max.
- Candidate camera-to-XCT scale: `ct_shape / part_id_shape` independently in Y and X.
- Patch inclusion rules: at least `0.75` of camera patch is labelled as the chosen specimen (`part_fraction`); at least `0.50` of selected XCT crop has `raw_XCT > 0` (`ct_coverage`). These are **project-defined heuristics**, not validated dataset-author criteria.
- Binary target: `label = int(np.count_nonzero(XCT_flaw_crop) > 0)`. This extreme `> 0` threshold is provisional and needs sensitivity analysis.
- Visible inputs are converted to float32 and divided by `255`; NIR by `65535`. Verify input HDF5 datatypes/ranges and physical interpretation before standardising any additional preprocessing.
- Saves arrays `X`, `y`, `groups` (specimen IDs), `layers` in `.npz`; CSV includes coordinates and flaw-pixel counts.

## 4. Established pilot results (do not mistake for validated scientific labels)

- `X.shape = (2024, 3, 24, 24)`; `y.shape = (2024,)`.
- 2,024 candidate patches total; 948 labelled positive (`1`), 1,076 labelled negative (`0`).
- 253 patches per selected specimen.

  | Specimen | Pilot patches | Label 1 |
  |---|---:|---:|
  | P2 | 253 | 246 |
  | P9 | 253 | 104 |
  | P16 | 253 | 60 |
  | P24 | 253 | 19 |
  | P35 | 253 | 237 |
  | P43 | 253 | 247 |
  | P52 | 253 | 22 |
  | P60 | 253 | 13 |

- About 77% of the *positive pilot patches* come from P2, P35, and P43; this does **not** represent build-wide porosity percentage or number of physical pores.
- Prior programmatic audit of the existing `.npz` and CSV found:
  - exactly 2,024 rows, correct array shapes and matching `y`/specimen/layer values across files;
  - no `NaN`/`Inf` input values, no completely zero image patches, no duplicate coordinate keys, no **exact** duplicate 3-channel image content;
  - all CSV labels agree with their stored `flaw_pixels > 0` rule;
  - all stored `ct_coverage` values happened to equal `1.0`, which makes that threshold non-discriminating within this pilot; determine whether the metric actually establishes coverage rather than just nonzero grayscale intensity.
  - These checks indicate **internal data consistency**, not proven physical registration or correctness of every target.
- Positive labels were sensitive to chosen threshold: the same manifest had 948 patches for `flaw_pixels >= 1`, but only 727 for `>= 50`. **Do not arbitrarily choose a threshold**; document its effect and scientific justification.

## 5. Specific discrepancy already diagnosed: 308 vs 317

For **P16, layer 600**, an example camera patch begins at `(Y, X) = (1997, 1994)`; adjacent negative example at `(2021, 1994)`.

The student ran a read-only check against the local HDF5 file and obtained:

| Cropping method | Positive XCT crop (Y, X) | Positive nonzero flaw pixels | Negative nonzero flaw pixels |
|---|---|---:|---:|
| Pilot builder `round` on each boundary | `9656:9772, 9642:9758` | **308** | **0** |
| Audit script `floor` starting / `ceil` ending | `9656:9773, 9641:9758` | **317** | **0** |
| Later slide-export `floor` on each boundary | `9656:9772, 9641:9757` | **317** | **0** |

**Interpretation:** Different rounding conventions select slightly different XCT pixels. This explains the *count discrepancy*. All conventions give the same 1/0 labels for these **two** examples, but **this does not establish** that all 2,024 labels are unchanged or that any mapping is physically correct.

- The original pilot dataset reports `308` and used the `round` method. Keep that as a reproducibility reference; do **not** automatically anoint it as the scientifically correct registration.
- Never alter original counts merely to make them match a slide.
- Investigate the physically appropriate pixel-center/boundary mapping from HDF5 metadata and registered coordinate system; choose one precise transformation and one boundary policy after validation; report its rationale.
- Regenerate all affected derived labels and images **into new versioned outputs**, compare label changes and record any disagreements.

## 6. Scientific and engineering risks to resolve BEFORE ML

1. **Physical alignment:** Camera and XCT rasters have different resolutions, potentially different extents/origins/axes. Size ratio alone is not proof of correct mapping. Confirm orientation and effective field of view using metadata and independent landmarks/sample IDs, not just a nice-looking overlay.
2. **XCT observation coverage:** A blank flaw mask does not necessarily mean "flaw-free" if CT data are unavailable, outside the gauge section, or masked. Distinguish known negatives from missing/uncertain coverage using actual dataset semantics.
3. **Flaw-mask semantics:** Nonzero mask pixels are not separate defects or pores. Inspect mask values/labels and whether they describe actual defects, algorithmic detections, or categories. Verify units and any preprocessing already applied by dataset authors.
4. **Weak label rule:** `> 0` annotated pixels per patch may be noise-/boundary-sensitive. Investigate several thresholds **as a sensitivity analysis**, not as an excuse to optimize labels until model performance improves.
5. **Sample dependence and leakage:** Nearby patches/layers from the same specimen are correlated. Never use a random patch-level train/test split as proof of generalisation. Later evaluate on whole held-out specimens (`groups` already exist). Train/test scaling statistics must be fit only on training groups.
6. **Representativeness:** Eight specimens and seven intentionally selected layers form a pilot, not a random sample of the whole build; do not infer physical build-wide defect rates.
7. **Preserve provenance:** Changes in clipping, scaling, registration, thresholds, masking, or filtering can change labels. Keep original outputs, audit logs, exact parameters and counts.

## 7. Professor-provided resources: evaluate, do not force

The professors supplied these three tomography-software references:

- **TomoPy:** https://tomopy.readthedocs.io/en/stable/ — tomography reconstruction and processing from projections; unlikely to be a priority because Snow provides reconstructed registered XCT slices.
- **Algotom:** https://algotom.readthedocs.io/en/latest/ — tomography preprocessing, reconstruction, and *post-processing*; potentially useful for inspecting/reslicing/diagnosing XCT artifacts if a specific need arises. Do not modify official XCT labels without a validated justification.
- **ASTRA Toolbox:** https://astra-toolbox.com/ — GPU-accelerated projection/reconstruction; unlikely needed unless raw projection measurements and an explicit reconstruction objective exist.

Professor-provided paper:

**Dinh, Duc M.; Muller, Nicolas; Quinsat, Yann (2021),** *Layering Defects Detection in Laser Powder Bed Fusion using Embedded Vision System*, **Computer-Aided Design & Applications** 18(5), pp. 1111–1118. DOI: https://doi.org/10.14733/cadaps.2021.1111-1118. A PDF was supplied in the earlier ChatGPT conversation; if absent locally, ask the student to copy it into `references/` rather than pretending it is accessible.

The paper analyses LPBF post-layering/post-melting images using homography correction, Gaussian filtering, adaptive thresholding and Sobel edge detection, then combines potential defect areas across layers and compares against CT. Its Figures 2–4 are useful conceptual references for **registration and basic optical anomaly processing**. The study's image-derived potential-defect fraction (~0.77%) was materially different from XCT porosity (~0.11–0.13%), illustrating why surface anomalies cannot be equated automatically with internal pores. **Do not force reproduction of its entire voxel/3D reconstruction pipeline.** Consider a simpler conventional image-processing baseline later only if relevant to the agreed FYP scope.

## 8. Requested autonomous execution plan (in order)

### Phase A — Inspect and audit existing data [safe to proceed]

1. Confirm that Codex is working in the **local** Windows project and can read the original HDF5; if only a cloud container is attached, stop and ask the student to attach the local folder rather than attempting to upload a 128 GB file.
2. Inspect the existing code, README, environment, `.npz`, CSV, HDF5 group shapes/dtypes/metadata, and previous results. Summarise what each original script actually does.
3. Run bounded, read-only checks for shapes, finite values, saturation/constant or empty patches, coordinate uniqueness, exact duplicates, correlated near-duplicates where useful, group/layer balance, HDF5 mask values, and CT availability.
4. Record findings in a small human-readable audit file and reproducible machine-readable summaries. Distinguish pass / fail / not yet tested.

### Phase B — Validate spatial mapping and labels [proceed with diagnostics; pause on ambiguous scientific choices]

1. Investigate registration metadata including origin, axis directions, pixel scale, sample/part masks and gauge-section coverage.
2. Compare *pilot round* vs *audit floor/ceil* vs *export floor* on multiple actual patches and quantify which labels and flaw-pixel counts change.
3. Generate a **small selection** of independent sensor/XCT/flaw-mask overlays across several specimens and layers; include axes, part outlines and mask provenance. Avoid relying on only P16 layer600.
4. Clearly explain what can be independently verified and what remains an assumption. If ambiguity persists, give the student/Prof Sing a small set of concrete evidence-backed questions and request a decision.
5. Document one candidate mapping and labelling rule, with code-level tests for coverage and exact coordinate conventions.

### Phase C — Implement cleaned-data pipeline [only after adequate validation/approval]

1. Implement new reusable scripts under `src/cleaning_pipeline/` without modifying original raw data or destroying user-authored scripts.
2. Save a **new version** of cleaned `.npz` and manifest under `data/cleaned/`; do not overwrite `data/processed/snow_pilot_patches.npz` or `snow_pilot_manifest.csv`.
3. Preserve group/specimen IDs, layer indices, camera coordinates, XCT crop bounds, mapping version, flaw-pixel count, label, coverage/uncertainty flags, source file and preprocessing parameters per sample.
4. Produce a summary of included/excluded/uncertain samples, changes in positive/negative labels, sensitivity to thresholds, and per-specimen class prevalence. Do not claim labels are validated if important spatial uncertainties remain.
5. Prepare specimen-aware train/validation/test *planning* only; **do not train, tune or evaluate an ML model in this task.**

### Phase D — Final report and checkpoint [stop]

Create `reports/data_cleaning_report.md` or similarly named report with:

- beginner-friendly FYP objective and how sensor images become tentative XCT-derived labels;
- files inspected, checks run, findings, evidence, severity and fixes;
- before/after dataset counts and versioned output paths;
- representative labelled images with **clear provisional/validated captions**;
- remaining risks, supervisor questions, and a final **ready / not-ready for model training** assessment;
- exact commands needed to reproduce the audit and cleaning;
- a concise professor-update summary suitable for presentation.

**Then stop. Do not begin Random Forest, XGBoost, SVM, CNN, fatigue prediction, or large-scale 3D reconstruction until Felix explicitly authorises a subsequent task.**

## 9. Safety and collaboration requirements

- **Raw HDF5 is immutable:** always open in read-only mode. Do not delete, rename, compress, reformat, rewrite or upload it elsewhere.
- Do not overwrite existing original scripts, pilot `.npz` or manifests. Prefer new isolated paths and versioned outputs.
- Do not use dangerous recursive deletion/reset commands or broad filesystem targets. Do not install large packages or perform multi-hour full-volume operations unless necessary and approved.
- Do not assume that every code comment or previous presentation claim is correct; inspect actual source arrays and reconcile evidence.
- Avoid loading full XCT arrays in RAM. Use chunked/minimal reads and report estimated workload before a potentially expensive scan.
- Work autonomously through **safe and reversible** diagnostics and implementation, but pause for permission blocks, substantial data mutations, and scientifically consequential labelling judgments. Do not ask for confirmation on every mechanical step.
- Communicate major findings in plain English and define terms. The user is unfamiliar with ML and HDF5 and wants to **understand what the code is doing**, not merely receive a pile of terminal output.
- For research communication, phrase the student's own accomplishments in first person ("I"), not "we". Distinguish *completed pipeline work* from *scientifically verified results*.
- Keep a brief task checklist with completed, in-progress and blocked stages; make sustained progress until the designated **data-cleaning checkpoint**.

## 10. Immediate first action

Confirm the project root and raw HDF5 availability; inspect the three scripts below **before changing any code**:

1. `src/build_snow_pilot_dataset.py`
2. `src/audit_snow_ml_patches.py`
3. `src/verify_snow_alignment.py`

Review the already confirmed rounding discrepancy and pilot audit results above. Start with **Phase A**, then proceed into safe **Phase B** tests. If the original HDF5 is accessible, use it read-only to test several specific spatial correspondences. Stop for review only if a genuine scientific or permission decision is required; otherwise continue to the stated data-cleaning checkpoint and report evidence.
