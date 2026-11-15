"""Summarize completed source preparation without claiming validated targets."""
import argparse
import csv
import json
import os
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=Path.cwd())
    parser.add_argument('--source',type=Path,required=True)
    args=parser.parse_args()
    root=args.root.resolve()
    source=args.source.resolve()
    if not source.is_relative_to(root/'data/cleaned'):
        raise ValueError('Expected separate cleaned-source preparation output')
    production=json.loads((source/'production_summary.json').read_text(encoding='utf-8'))
    catalog=json.loads((source/'catalog/summary.json').read_text(encoding='utf-8'))
    folder=root/'reports/data_cleaning/source_preparation_v1'
    folder.mkdir(parents=True,exist_ok=False)
    assets=folder/'assets'
    assets.mkdir()
    with (source/'catalog/per_layer.csv').open(newline='',encoding='utf-8') as handle:
        rows=list(csv.DictReader(handle))
    layers=[int(r['layer']) for r in rows]
    fig,ax=plt.subplots(figsize=(12,5),layout='constrained')
    for field,label,color,style in [('rows','Prepared sensor patches','#495057','-'),
                                    ('candidate_one','Provisional annotation-positive candidates','#1864ab','-'),
                                    ('candidate_unknown','Unknown proxy/bounds candidates','#d17b00','--')]:
        ax.plot(layers,[int(r[field]) for r in rows],label=label,color=color,linestyle=style,linewidth=1.8)
    ax.set_xlim(layers[0],layers[-1])
    ax.set_ylim(bottom=0)
    ax.set_xticks([519,540,560,580,600,620,640,660])
    ax.set_xlabel('Source layer index')
    ax.set_ylabel('Patches per layer')
    ax.set_title('Prepared inputs and provisional annotation candidates across the declared scope')
    ax.spines[['top','right']].set_visible(False)
    ax.legend(loc='center left',bbox_to_anchor=(1.02,.5),fontsize=9)
    fig.savefig(assets/'prepared_counts_by_layer.png',dpi=180,facecolor='white')
    plt.close(fig)
    link=lambda p:Path(os.path.relpath(p,folder)).as_posix()
    flags='\n'.join(f'| `{name}` | {count:,} |' for name,count in catalog['source_quality_flag_counts'].items())
    c=catalog['candidate_label_counts']
    text=f'''# Source preparation now covers 64 specimens and 142 nominal gauge layers

The source preparation and quality-screening run is complete for its declared scope: **{catalog['rows']:,} prepared sensor patches** across **{catalog['specimens_with_rows']} specimens** and layers **519–660 inclusive**. This moves beyond the original eight-specimen pilot. The rest of the 1,117-layer source remains unchanged and outside this preparation scope.

**Status:** sensor inputs prepared; candidate targets remain scientifically unvalidated. No model was trained and no final `y` target was exported.

## Why the pilot was used

The pilot was a small test of extraction, source coordinates and normalization before applying the workflow more broadly. It is a regression reference. The new layer-600 all-specimen batch reproduced all 264 overlapping pilot records exactly. It did not require another scientific approval before routine source preparation could proceed.

## What the cleaner did

- Extracted the three sensor channels and standardized them using the existing float32 normalization.
- Screened every extracted patch for structural, finite-value and wholly empty-image problems; preserved any quarantined cases separately.
- Retained constant-channel, stored-maximum and exact-duplicate observations as flags rather than imposing unjustified exclusions.
- Preserved layer-specific author notes and scoped acquisition-event flags without assuming every patch in the noted layer is unusable.
- Kept candidate XCT annotations separate from final scientific targets. Insufficient intensity proxy or invalid crop bounds gives candidate `-1` (unknown), rather than a negative.
- Preserved specimen, layer, coordinates, crop bounds, source paths and checksums. The original HDF5 was read-only, and prior scripts/pilot files were not overwritten.

## Results

| Measure | Count |
|---|---:|
| Prepared sensor patches | {catalog['rows']:,} |
| Structurally invalid/nonfinite/wholly empty patches quarantined | {catalog['quarantined_patches_from_producer']:,} |
| Unique sample identities | {catalog['unique_sample_ids']:,} |
| Later exact-image-content duplicates retained and flagged | {catalog['exact_duplicate_rows']:,} |
| Duplicate-content rows whose first occurrence was on another layer | {catalog['exact_duplicate_rows_across_layers']:,} |
| Candidate annotation-positive (`1`) | {c['1']:,} |
| Candidate annotation-negative (`0`), still unvalidated | {c['0']:,} |
| Unknown intensity-proxy/bounds candidate (`-1`) | {c['-1']:,} |
| Candidate grid positions outside the inherited part-geometry selection | {catalog['geometry_scope_excluded_from_producer']:,} |

Geometry-scope counts concern candidate positions outside the existing 0.75 part-fraction selection, not confirmed corrupt images. The nominal gauge-layer range is an extraction scope, not a measured-validity mask. All {catalog['rows']:,} retained rows still have false label/coverage validation flags.

![Prepared inputs and provisional candidates by layer](assets/prepared_counts_by_layer.png)

These counts describe prepared patches and candidate annotations. They do not count physical pores or measure build-wide porosity. This is one build; generalisation to another build has not been tested.

## Review flags

| Informational or review flag | Patch occurrences |
|---|---:|
{flags}

One row can have several flags, so these counts must not be summed as a count of bad rows. A stored-maximum endpoint is not proof of physical saturation. Duplicates are retained with links to their first occurrence. Author-event flags identify context requiring review, not confirmed failure of every flagged patch.

## Where to find the data

- [Canonical catalog and usage notes]({link(source/'catalog/README.md')}).
- [Full prepared-source manifest]({link(source/'catalog/manifest.csv')}).
- [Per-specimen summary]({link(source/'catalog/per_specimen.csv')}).
- [Per-layer summary]({link(source/'catalog/per_layer.csv')}).
- [Catalog integrity and totals]({link(source/'catalog/summary.json')}).
- [Production completion record]({link(source/'production_summary.json')}).
- [Independent raw-data spot checks]({link(source/'qa/independent_source_sample_checks.json')}).
- [Pipeline description]({link(root/'docs/source_cleaning_workflow.md')}).

Each layer has a separate compressed feature shard. The canonical manifest identifies its shard and feature-row position; the data need not be loaded as one giant array. Catalog consolidation verified every shard's feature/manifest hash and array headers, checked globally unique sample IDs, and searched exact content identity across the complete prepared set.

## What remains

Routine source preparation did not need to wait for all scientific questions. Final target validation still needs a defensible camera-to-XCT grid convention, usable XCT support definition and annotation interpretation. Candidate 0/1 values must not be silently promoted to verified ground truth, and unknowns must not be forced into class 0.

The [supervisor brief]({link(root/'reports/data_cleaning/2026-11-08_run01/supervisor_validation_brief.md')}) remains useful for those specific questions. It does not block the mechanical preparation that is now complete.
'''
    with (folder/'report.md').open('x',encoding='utf-8') as handle:
        handle.write(text)
    print(folder/'report.md')


if __name__=='__main__':
    main()
