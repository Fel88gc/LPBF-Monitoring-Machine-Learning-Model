# Local experimental data

Obtain the Snow et al. release separately from https://doi.org/10.13139/ORNLNCCS/2524534 and follow its access and use terms.

The historical scripts expect the preserved source at:

```text
data/raw/2024-05-01 M2 AMMTO Fatigue Blanks 05.hdf5
```

The original file is approximately 128 GB. Keep it read-only. Derived layer shards and the catalogue belong under `data/cleaned/snow_source_preparation_v1/`; image descriptors belong under `data/features/`. These arrays are excluded from Git.

The configuration in `config/source_preparation_snapshot.json` records the historical scope. The indexer creates the active configuration in the selected new output directory. Do not copy a completion flag into an empty directory and treat it as prepared data.

Historical pilot inputs, if deliberately reproducing that stage, are also separate local artifacts. The recorded original filename has a double extension: `data/processed/snow_pilot_patches.npz.npz`.
