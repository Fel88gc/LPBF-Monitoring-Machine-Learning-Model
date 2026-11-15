# Cleaning the source data after the pilot

The old pilot is a regression reference, not the full dataset. It established that the extraction and normalization reproduce the original source. Production preparation now uses the same mechanically tested rules across the source fatigue specimens.

## Processing scope

- All 64 source geometries named `AMMTO Fatigue Bar`.
- Layers 519–660 inclusive: 142 layers in the documented nominal XCT gauge range.
- Three sensor channels per 24 × 24 patch: visible post-melt, visible post-recoat and integrated-max NIR.
- Auxiliary spatter generators and the default tensile bar are outside this research scope.
- Other source layers are indexed but not included in this preparation run. The nominal gauge range does not establish measured XCT validity for every pixel.

## What the production cleaner does

1. Reads the original HDF5 in mode `r`, using bounded tiles and small per-dataset caches.
2. Extracts patches belonging to the selected fatigue-bar geometries, retaining the existing minimum part fraction of 0.75.
3. Standardizes the three channels to float32 using the original divisors 255, 255 and 65535.
4. Quarantines structurally invalid, nonfinite or wholly zero three-channel patches into a separate record rather than losing their provenance.
5. Flags constant channels, stored-maximum values and duplicate image content. These observations are not automatically treated as unusable data.
6. Records source acquisition notes. A layer event flags a need for review; it does not establish that every patch in the layer is affected.
7. Records the rounded candidate XCT crop, annotation-pixel count and raw-positive intensity proxy. It never treats that proxy as proven measured coverage.
8. Saves `candidate_y=-1` when the intensity proxy is insufficient or crop bounds are invalid. Candidate 0/1 targets remain explicitly unvalidated; no final `y` target is exported.
9. Writes independent layer shards with stable sample IDs, manifests, checksums and a checkpoint. Existing completed output cannot be overwritten.

These steps can proceed without resolving every scientific label question first. Final training labels still require a justified mapping and coverage interpretation.

## Files

- [Source preparation directory](../data/cleaned/snow_source_preparation_v1/README.md).
- `source_config.json`: declared scope and reproducible parameters.
- `source_layers.csv`: index of all 1,117 source layers.
- `layers/layer_NNNN/`: prepared features, candidate targets, full provenance and quality records.
- `production_progress.json`: resumable progress.
- `production_summary.json`: completion record, created only after the declared scope finishes.
- `qa/`: independent sample and preservation checks.
- `catalog/`: canonical manifest and aggregate quality records, created after all shards complete.

The production job is run from the project root:

```powershell
& '.\.venv\Scripts\python.exe' -B src/cleaning_pipeline/prepare_source_dataset.py --root . --output data/cleaned/snow_source_preparation_v1 --resume
```

A completed job refuses reuse. If an interrupted layer lacks a completion record, the workflow preserves it for diagnosis rather than silently replacing it. Keep the source file, pipeline version and parameters fixed across a resumable run.

The initial all-specimen layer-600 batch produced 2,112 patches. Its 264 records overlapping the old pilot matched the original feature bytes and annotation counts exactly. Independent direct-source spot checks on additional specimens and layers also passed. These are engineering checks, not proof of physical registration.
