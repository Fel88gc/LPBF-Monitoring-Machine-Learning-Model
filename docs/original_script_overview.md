# What the existing scripts do

This is a static code review. Original scripts were not imported or bulk-run. All inspected HDF5 opens use read-only mode, but some scripts overwrite their own fixed output filenames.

| Original script in src/ | Function | Output behavior |
|---|---|---|
| inspect_snow.py | Bounded inventory of HDF5 groups, shapes, types, chunks, compression and attributes. | Prints only. |
| inspect_snow_stage2.py | Shallow HDF5 tree and a few example scan rows. | Prints only. |
| inspect_snow_stage3.py | Camera/XCT/ID metadata, fatigue-label availability, segmentation classes and scan-layer coverage. | Prints only. |
| inspect_snow_metadata.py | Selected root, image, XCT and ID coordinate/registration attributes. | Fixed results/snow_registration_metadata.txt. |
| find_snow_xct.py | Coarse grid search of small layer-500 XCT crops; visualize a sampled nonzero region. | Fixed search PNG if a region is found. |
| check_snow_xct_storage.py | XCT storage allocation and bounded stored-chunk tile samples. | Prints only. |
| visualize_snow.py | Independent central crops of visible, NIR, XCT and part IDs at layer500; not an alignment proof. | Fixed results/snow_layer_500_preview.png. |
| visualize_snow_xct.py | Raw XCT, flaw values and overlay for a selected layer-522 region. | Fixed results/snow_xct_layer_522_verified.png; filename does not itself establish physical validation. |
| verify_snow_alignment.py | Candidate scale mapping and a P16/layer600 comparison. | Fixed results/snow_alignment_P16_layer600.png. |
| audit_snow_ml_patches.py | P16/layer600 candidate 24×24 patches, raw-positive proxy and flaw counts. | Fixed results/snow_P16_layer600_patch_audit.csv. |
| build_snow_pilot_dataset.py | Three-channel patch extraction and provisional targets across selected specimens/layers. | Fixed NPZ/CSV paths in data/processed; do not rerun over the existing pilot. |
| export_snow_slide6_xct_masks.py | Known positive/negative P16 masks and XCT overlays with expected-count checks. | Four fixed PNGs plus an audit file. Still uses floor/floor, unlike the pilot. |
| check_snow_label_mapping.py | Three rounding/crop conventions for the two known P16 patches. | Prints only. |

The machine-readable inventory records source hashes and write-call line locations under `results/data_quality/2026-11-08_run01/registration/`.
