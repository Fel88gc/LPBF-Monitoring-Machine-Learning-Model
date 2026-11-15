"""Build the offline Markdown audit report from inspectable run evidence."""
from __future__ import annotations
import argparse
import csv
import json
import os
import shutil
from pathlib import Path


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(path, text):
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def link_from(folder, target):
    return Path(os.path.relpath(target, folder)).as_posix()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--run", type=Path, required=True)
    args = parser.parse_args()
    root, run = args.root.resolve(), args.run.resolve()
    if not run.is_relative_to(root / "results/data_quality"):
        raise ValueError("Run must be inside project audit results")
    pilot = load(run / "pilot/final/pilot_audit.json")
    spatial = load(run / "spatial/summary.json")
    registration = load(run / "registration/registration_metadata.json")
    review_path = root / "data/review" / run.name
    review = load(review_path / "review_status.json")
    protection_path = run / "protection_verification.json"
    protection = load(protection_path) if protection_path.exists() else None
    with (run / "spatial/label_disagreements.csv").open(newline="", encoding="utf-8") as handle:
        flips = list(csv.DictReader(handle))
    folder = root / "reports/data_cleaning" / run.name
    if folder.exists():
        raise FileExistsError(f"Refusing to overwrite report: {folder}")
    assets = folder / "assets"
    assets.mkdir(parents=True)
    image_paths = [run / "pilot/final" / name for name in (
        "pilot_label_distribution.png", "threshold_sensitivity.png", "channel_distributions.png")]
    image_paths += list((run / "spatial/review_figures").glob("*.png"))
    image_paths += [run / "spatial" / name for name in spatial["figures"]]
    for image in image_paths:
        target = assets / image.name
        with image.open("rb") as incoming, target.open("xb") as outgoing:
            shutil.copyfileobj(incoming, outgoing)
    methods = spatial["methods"]
    method_rows = "\n".join(
        f"| `{method}` | {item['positive_labels']} | {item['labels_changed_from_pilot']} | {item['flaw_counts_changed_from_pilot']} |"
        for method, item in methods.items())
    flip_rows = "\n".join(
        f"| {r['pilot_row']} | P{r['part_id']} | {r['layer']} | ({r['camera_y']}, {r['camera_x']}) | {r['pilot_round_flaw_pixels']} | {r['audit_floor_ceil_flaw_pixels']} | {r['export_floor_flaw_pixels']} |"
        for r in flips)
    specimen_rows = "\n".join(f"| P{r['part_id']} | {r['patches']} | {r['positive']} | {r['negative']} | {100*r['positive_fraction']:.1f}% |" for r in pilot["per_specimen"])
    threshold_rows = "\n".join(f"| {r['minimum_flaw_pixels']} | {r['positive']} | {r['negative']} | {r['label_changes_from_ge1']} |" for r in pilot["threshold_sensitivity"])
    protected_text = (f"SHA-256 hashes of all **{protection['protected_files_checked']} pre-existing protected files** match the baseline. "
                      "This covers original scripts, processed pilot files, prior results and the existing small project records. "
                      "The raw HDF5 was opened in read-only mode; its file size and modification time are unchanged. "
                      "A full 128 GB raw-file checksum was not computed."
                      if protection else "Preservation verification is recorded separately; inspect the run evidence before claiming a full preservation check.")
    evidence = lambda name: link_from(folder, run / name)
    questions_path = run / "sources/supervisor_questions.md"
    questions_link = f"[Supervisor questions]({link_from(folder, questions_path)})" if questions_path.exists() else "The four questions below"
    report = f"""# Pilot extraction reproduces exactly, but six labels depend on crop boundaries

**Run:** `{run.name}`. **Readiness: not ready for ML training.**

The audit reproduced every saved sensor patch and original flaw-pixel count from the raw Snow file. All {pilot['rows']:,} pilot rows remain available, with {pilot['positive']} provisional positive and {pilot['negative']:,} provisional negative labels. Internal consistency is strong, but the exact physical grid conversion and actual XCT observation coverage are not yet independently established.

Six patches change their current `>0` target under an alternate crop policy. One additional patch has an NIR channel entirely at its stored maximum. These seven local cases are flagged; **no label was changed and no sample was excluded**. Mapping and coverage remain unvalidated for the dataset as a whole, including the other rows.

## What the project is trying to establish

The working question is whether visible post-melt, visible post-recoat and integrated-max NIR images from an LPBF build can predict the presence of a **dataset-detected XCT flaw annotation** in the corresponding region. The input unit is one 24 by 24 camera patch at one specimen and layer, with three channels. The target is generated by this project from the released XCT flaw raster; Snow did not supply these ready-made binary patch labels.

XCT is a later measurement of the specimen's internal structure. It must be linked to the same physical region as the sensor patch. Reproducing the student's code verifies provenance; it does not by itself verify that physical correspondence.

## Completed work and preservation

- Established the existing `.venv` environment and saved its package versions. No packages were installed.
- Copied the supplied handoff and paper into `docs/` and `references/`, and preserved the locally downloaded author README and Methods there with verified hashes.
- Inspected the 13 original Python scripts statically, recording HDF5 modes, dependencies and write sites. Original scripts were not bulk-run or imported.
- Ran the pilot audit, bounded HDF5 registration audit and all-patch crop comparison using new scripts under `src/cleaning_pipeline/`.
- Created new diagnostic figures, the review dataset, data dictionary, trace examples and this report.

{protected_text}

All new products are in separate audit/report/review paths. The original `.npz.npz` filename was retained. The existing scripts often write fixed filenames, which is why the new workflow uses explicit, new output directories and refuses overwrites.

## The pilot is internally consistent and exactly reproducible

All **{pilot['checks_passed']} internal-consistency checks pass**. The pilot contains float32 `X=(2024,3,24,24)` and 2,024 matching labels, specimen IDs, layer IDs and manifest rows. There are no NaN/Inf values, wholly zero patches, wholly constant three-channel patches, duplicate coordinate keys or exact duplicate three-channel images. Labels agree with the stored `flaw_pixels > 0` rule.

The raw-data comparison covered all 2,024 records across eight specimens and seven selected layers. Visible inputs divided by 255 and NIR divided by 65,535 exactly reproduce the stored features, with maximum absolute difference **{spatial['raw_sensor_max_abs_error']}**. Re-reading XCT using the original `pilot_round` policy reproduces every stored flaw-pixel count ({spatial['pilot_count_mismatches']} mismatches).

This establishes that the pilot can be regenerated under its original rules. It does not establish that those rules are the correct scientific definition.

## Crop boundaries can change a patch's target

All three methods use the same candidate scale `13752 / 2844 = {spatial['mapping']['scale_y']:.12f}`. They differ only in how mapped pixel boundaries are rounded. Crops use Python's half-open `[start:stop]` convention.

| Candidate policy | Positive labels | Labels changed from pilot | Flaw counts changed from pilot |
|---|---:|---:|---:|
{method_rows}

The `export_floor` policy preserves the aggregate count of 948 positives while swapping three negatives to positive and three positives to negative. Aggregate class counts alone would miss that change. The union of affected records contains six rows ({100*spatial['label_disagreement_rows']/spatial['rows']:.3f}% of the pilot).

| Zero-based pilot row | Specimen | Layer | Camera (Y, X) | Pilot round count | Floor/ceil count | Floor count |
|---:|---|---:|---|---:|---:|---:|
{flip_rows}

![Flaw-pixel counts for six crop-sensitive records](assets/crop_sensitive_patches.png)

These are boundary-sensitive tiny annotations under the current `>0` rule, not proof that one method is scientifically preferable. Keep `pilot_round` as the reproduction reference. Do not select a policy to make a slide or future model score look better.

## Registration is documented, but the index conversion is still a candidate

The [official ORNL record](https://doi.ccs.ornl.gov/dataset/bc373c52-5cdd-50cd-bb81-dcc85799fe35) states that in-situ and XCT data were registered to build-plate coordinates, with XCT around fatigue gauge sections. The locally downloaded Methods describes camera calibration/homography and XCT registration using point-to-plane ICP with RANSAC. These author steps should not be blindly repeated on already processed images.

The HDF5 root describes a 245 by 245 mm camera field and bottom-left image origin, with X along the second image dimension and Y along the first. Camera grids are 2844 by 2844; XCT grids are 13752 by 13752. The inspected metadata and local supplements do not give the exact registered XCT outer extent, pixel-center convention, numeric affine transform or registration-error estimate needed to independently confirm the student's conversion.

Methods quotes a nominal acquisition spacing of 17.8 micrometres. If the released XCT grid spans exactly 245 mm, its spacing is 17.81559046 micrometres; 13,752 voxels at 17.8 micrometres span 244.7856 mm. That 0.2144 mm extent difference is an **unresolved convention/rounding/resampling ambiguity**, not a demonstrated spatial error or permission to switch transforms.

![Candidate alignment at P16 layer 600](assets/candidate_P16_layer600.png)

Blue outlines are part templates; orange outlines are sample templates. XCT is plotted through the candidate transform. A visually plausible overlay generated by that same transform is not independent proof of calibration. Nine figures cover P2/P16/P24 at layers 540/600/640.

## Nonzero grayscale does not establish experimental coverage

Every pilot crop has `mean(raw_XCT > 0)=1.0` under all three crop policies. This proxy therefore does not distinguish samples here. A blank flaw raster is insufficient to certify a known negative if usable XCT is missing or outside the measured support.

The sample-ID lookup describes nominal XCT gauge-section geometries; `sample_ids` is a template raster, not a documented measured-validity mask. Sample IDs differ from part IDs. Sample-template overlap in the pilot ranges from {spatial['sample_template_fraction_range'][0]:.4f} to {spatial['sample_template_fraction_range'][1]:.4f}. All logical chunks in both XCT arrays are allocated, so chunk allocation cannot provide an independent coverage mask either.

Author notes place the gauge section approximately between layers 519 and 660, which is consistent with the pilot's selected layers 540–640. This is supporting context, not per-pixel coverage validation. No coverage-based sample exclusion was applied.

## One NIR channel needs review, and the target threshold matters

Zero-based row 585 (P2, layer 580, camera Y=2279, X=357) has all 576 NIR pixels at normalized 1.0, corresponding to raw value 65,535; its two visible channels vary. The raw-data check reproduces this channel exactly, so it is inherited from the released sensor data rather than introduced by our normalization. It is flagged, not removed. A stored-maximum value alone does not prove physical saturation or dropped data.

Across the pilot's NIR pixels, {100*pilot['channel_stats'][2]['one_pixel_fraction']:.3f}% are at the stored maximum. There is no arbitrary saturation cutoff or new normalization. Root metadata records some sensor-quality events elsewhere; it does not establish this patch's cause.

| Minimum nonzero annotation pixels per crop | Positive patches | Negative patches | Changed from minimum 1 |
|---:|---:|---:|---:|
{threshold_rows}

![Sensitivity to the project-defined target threshold](assets/threshold_sensitivity.png)

The threshold is a project decision requiring a scientific justification. It was not optimized or changed. Methods describes algorithmic XCT flaw detection using a Laplacian-of-Gaussian response and thresholding/clustering. The sampled raster is not binary-valued; counting nonzero pixels does not count distinct physical pores or estimate build-wide porosity.

## The eight specimens require grouped evaluation later

| Specimen | Patches | Provisional positive | Provisional negative | Positive fraction |
|---|---:|---:|---:|---:|
{specimen_rows}

![Pilot target distribution by specimen](assets/pilot_label_distribution.png)

P2/P35/P43 contribute 730 of 948 positive patches (77.0%). These eight specimens and seven chosen layers form a selected pilot from one build. They do not establish build-wide defect prevalence or performance on another build. Repeated locations across selected layers also create dependence even when their image bytes differ.

The saved specimen-holdout inventory is **planning only**. No final train/validation/test assignment, learned scaling, model fitting, tuning or evaluation was performed. Later evaluation should hold out whole specimens; any learned preprocessing must be fitted only to training specimens.

## New presentation evidence and a traceable record

![Two P16 examples reproduced with the original pilot boundaries](assets/slide6_provisional_pilot_round.png)

The positive example at camera(Y=1997,X=1994) has XCT crop Y=9656:9772,X9642:9758 and 308 nonzero annotation pixels. The adjacent negative example at (Y=2021,X=1994) has zero. These are **provisional** targets. The figure is a new replacement candidate for Slide 6; the existing slide deck and old images were not edited.

The [record trace]({link_from(folder, review_path/'record_trace_P16_layer600.json')}) connects sensor paths, pilot row, coordinates, normalization, all three XCT crops and the derived label. The [data dictionary](data_dictionary.md) defines the original fields and new flags.

## Review package and decision checkpoint

The [provisional package]({link_from(folder, review_path/'README.md')}) contains all 2,024 original feature/label rows with exact array preservation, a richer manifest, six crop-sensitivity flags and one channel-review flag. It has **zero exclusions and zero label changes**. All rows explicitly have `registration_validated=false` and `coverage_validated=false`; these mean evidence is unresolved, not that every row is wrong.

Final scientific cleaning remains pending. The missing evidence cannot be supplied by approving a convenient rounding method. {questions_link} gives the concrete questions:

1. What exact registered-grid extent, spacing, origin, pixel-center/boundary and layer-index conventions should connect camera and XCT arrays?
2. What identifies actually reconstructed and usable XCT support, distinct from template geometry or nonzero intensity?
3. What do the flaw raster values encode, what detector limits apply, and what registration uncertainty should inform boundary-sensitive labels?
4. After those points are clarified, should tiny boundary annotations and the constant NIR channel be retained, assigned uncertainty or excluded under a documented policy?

**Current recommendation:** preserve the pilot as the reproducibility reference and use the new review package for inspection. Do not claim final validated labels, silently relabel/drop cases, or start ML training. No administrative permission is currently blocking local diagnostics. A scientific clarification is needed before finalizing a cleaned training dataset. No message was sent to a supervisor.

## Reproduce and inspect

From the project root, use a **new run ID** so earlier results are preserved:

```powershell
& '.\\.venv\\Scripts\\python.exe' -B src/cleaning_pipeline/run_audit.py --root . --run-id another_unique_run
```

The run performs bounded metadata inspection, pilot checks, crop comparison, provisional packaging, figures, preservation verification and report generation. It refuses an existing run/review/report destination. No original scripts are imported, and the HDF5 is always opened with mode `r`.

The spatial stage read approximately {spatial['logical_array_bytes_read']/1e6:.1f} MB of logical arrays in selected regions ({spatial['elapsed_seconds']:.1f}s for this run). HDF5 chunk decompression reads additional bytes, which were not separately measured. No complete XCT layer, full 3D volume or full 128 GB raw-file scan was loaded into memory. The metadata inventory contains {len(registration['metadata_objects'])} objects; truncation={registration['metadata_inventory_truncated']}.

Evidence:

- [Pilot checks and exact source hashes]({evidence('pilot/final/pilot_audit.json')})
- [All 2,024 crop comparisons]({evidence('spatial/candidate_crop_comparison.csv')})
- [Spatial summary]({evidence('spatial/summary.json')})
- [Full inspected metadata]({evidence('registration/registration_metadata.json')})
- [Original-script inventory]({evidence('registration/script_inventory.md')})
- [Source review from the initial audit]({link_from(folder, root/'results/data_quality/2026-11-08_run01/sources/source_semantics.md')})
- [Environment snapshot]({evidence('environment_snapshot.json')})
- [Preservation verification]({evidence('protection_verification.json')})

## Professor update draft

I audited the existing Snow pilot with a reproducible read-only workflow. I reproduced all 2,024 three-channel sensor patches and the original XCT annotation counts exactly. I found that alternative crop-boundary conventions change six patch labels, and I flagged one constant NIR channel. I preserved all original files and labels and prepared a review manifest and diagnostic figures. I am clarifying the exact registered-grid conversion, usable XCT support and flaw-mask semantics before finalizing the labels or beginning ML training.
"""
    write(folder / "report.md", report)
    dictionary = "# Snow pilot data dictionary\n\nOne row is a 24 × 24 camera patch from one specimen at one indexed layer. Targets are provisional project-derived annotations. Snow did not supply these ready-made binary labels.\n\n| Field / array | Unit / type | Meaning and limit |\n|---|---|---|\n| X | float32, N × 3 × 24 × 24 | Visible post-melt, visible post-recoat, integrated-max NIR. Existing divisors: 255, 255, 65535. Values in [0,1]; NIR is not calibrated temperature. |\n| y / original_label | uint8, 0 or 1 | Current pilot target: any nonzero XCT flaw annotation in the pilot_round crop. Physical registration and coverage remain unvalidated. |\n| groups / part_id | Integer ID | Specimen identifier. Use whole specimens for later holdouts. Part IDs and sample IDs use different lookups. |\n| layers / layer | Integer index | Released slice-axis index; not a physical Z distance or timestamp. |\n| camera_y, camera_x | Pixel boundary index | Array slice start (Y, X), with half-open stop = start + patch_size. Display uses origin='lower' per metadata; the exact physical transform is unvalidated. |\n| patch_size | Camera pixels | 24 on each axis in this pilot. |\n| part_fraction | Fraction | Fraction of the camera patch belonging to the selected part. Existing project heuristic: at least 0.75. |\n| ct_coverage | Fraction | Legacy mean(raw XCT > 0); not independently measured coverage. Existing project heuristic: at least 0.50. All pilot values are 1.0. |\n| flaw_pixels | XCT annotation pixels | Count of nonzero values in the candidate crop; not a pore count, porosity, or volume. |\n| sample_template_nonzero_fraction | Fraction | Camera-grid overlap with nonzero sample-template geometry; not experimentally verified XCT support. |\n| sample_template_ids | List of integer IDs | Template identifiers present; 0 is background. Use the HDF5 root lookup for specimen relationships. |\n| pilot_round_* | Boundaries, count, label | Reproduction policy: round each mapped boundary; integer crops use half-open indexing. |\n| audit_floor_ceil_* | Boundaries, count, label | Sensitivity alternative: floor start, ceil stop. |\n| export_floor_* | Boundaries, count, label | Sensitivity alternative: floor start, floor stop. |\n| raw_sensor_max_abs_error | Normalized units | Largest absolute difference between raw-derived sensor patch and saved X. Zero for all pilot rows in this run. |\n| crop_boundary_sensitive | Boolean array | Binary target changes under at least one alternate crop policy; 6 rows in this run. |\n| channel_review_flag | Boolean array | A sensor channel needs review; 1 constant NIR channel in this run. Not an automatic exclusion. |\n| registration_validated | Boolean | False for all rows: the exact physical mapping is not independently established. |\n| coverage_validated | Boolean | False for all rows: actual usable XCT support is not independently established. |\n| mapping_version | String | dimension_ratio_v0_candidate; no accepted physical correction was applied. |\n| source_hdf5 / source_pilot | Project-relative paths | Sources of the raw images, annotations and original pilot; raw HDF5 is read-only. |\n| visible_divisor / nir_divisor | Numeric | Existing normalization parameters 255 and 65535. |\n| dataset_status | String | provisional_review_only; no labels changed or samples excluded. Not ready for training. |\n\nFull modality paths:\n\n- /slices/camera_data/visible/0 — visible post-melt.\n- /slices/camera_data/visible/1 — visible post-recoat.\n- /slices/camera_data/nir/1 — integrated-max NIR.\n- /slices/registered_data/x-ray_ct_flaw — source XCT flaw annotation.\n- /slices/registered_data/x-ray_ct_data — registered XCT grayscale.\n\nSee report.md and the record-trace JSON for the exact crop bounds and current interpretation limits.\n"
    write(folder / "data_dictionary.md", dictionary)
    status = {"run": run.name, "phase_a_integrity": "complete",
              "phase_b_diagnostics": "complete", "physical_mapping_validation": "pending scientific evidence",
              "measured_xct_coverage_validation": "pending scientific evidence",
              "phase_c_review_package": "complete; unchanged features and labels",
              "phase_c_final_scientific_cleaning": "not performed; review required",
              "phase_d_report": "complete", "ready_for_model_training": False,
              "model_training_performed": False, "labels_changed": 0, "samples_excluded": 0}
    with (folder / "status.json").open("x", encoding="utf-8") as handle:
        json.dump(status, handle, indent=2)
    write(folder / "checklist.md", "# Data-cleaning checkpoint\n\n" + "\n".join(
        f"- [{'x' if value.startswith('complete') else ' '}] {key}: {value}" for key, value in status.items() if isinstance(value, str) and key != "run") + "\n\nNo ML model was trained. See report.md for evidence and review questions.\n")
    print(folder / "report.md")


if __name__ == "__main__":
    main()
