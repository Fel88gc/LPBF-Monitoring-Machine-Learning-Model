"""Index the full source for preparation; no image pixels are altered or read."""
import argparse
import csv
import json
from pathlib import Path
import h5py


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path.cwd())
    parser.add_argument('--output', type=Path, required=True)
    args=parser.parse_args()
    root,output=args.root.resolve(),args.output.resolve()
    if not output.is_relative_to(root/'data/cleaned'):
        raise ValueError('Source preparation must use a separate data/cleaned output directory')
    if output.exists():
        raise FileExistsError('Existing preparation output is protected')
    raw=root/'data/raw/2024-05-01 M2 AMMTO Fatigue Blanks 05.hdf5'
    paths=['/slices/camera_data/visible/0','/slices/camera_data/visible/1','/slices/camera_data/nir/1',
           '/slices/part_ids','/slices/sample_ids','/slices/registered_data/x-ray_ct_data',
           '/slices/registered_data/x-ray_ct_flaw']
    with h5py.File(raw,'r') as h5:
        shapes={path:list(h5[path].shape) for path in paths}
        layer_count=shapes[paths[0]][0]
        if any(shape[0]!=layer_count for shape in shapes.values()):
            raise ValueError('Source modality layer counts disagree')
        names=str(h5.attrs['parts/part_stl_filenames']).split(',')
        selected=[i for i,name in enumerate(names) if 'AMMTO Fatigue Bar' in name]
        notes={int(str(key).split('/')[-1]):str(value) for key,value in h5.attrs.items() if str(key).startswith('layer_notes/')}
    config={'stage':'source_preparation_in_progress','raw_source':str(raw.relative_to(root)),
            'shapes':shapes,'source_layer_count':layer_count,'specimen_ids':selected,'specimen_count':len(selected),
            'selection':'AMMTO Fatigue Bar geometries; spatter generators and default tensile bar are outside this extraction scope',
            'nominal_gauge_layer_start':519,'nominal_gauge_layer_end_inclusive':660,
            'scope_note':'Nominal gauge layers are a preparation scope, not a validated coverage mask',
            'patch_size':24,'minimum_part_fraction':.75,'candidate_mapping':'dimension_ratio_pilot_round',
            'preprocessing_divisors':[255,255,65535],
            'label_status':'candidate_only; mapping and measured support remain unvalidated',
            'known_quality_events':'Recorded as flags with source wording; no whole-layer exclusion is inferred',
            'ready_for_training':False}
    output.mkdir(parents=True)
    with (output/'source_config.json').open('x',encoding='utf-8') as handle:
        json.dump(config,handle,indent=2)
    with (output/'source_layers.csv').open('x',newline='',encoding='utf-8') as handle:
        fields=['layer','nominal_gauge_scope','visible_post_melt_available','visible_post_recoat_available','nir_max_available',
                'source_note','note_implication','coverage_status','processing_status']
        writer=csv.DictWriter(handle,fieldnames=fields)
        writer.writeheader()
        for layer in range(layer_count):
            note=notes.get(layer,'').strip()
            writer.writerow({'layer':layer,'nominal_gauge_scope':int(519<=layer<=660),
                'visible_post_melt_available':1,'visible_post_recoat_available':1,'nir_max_available':1,
                'source_note':note,'note_implication':'review documented event; affected channel/region not automatically excluded' if note else '',
                'coverage_status':'unknown_measured_support','processing_status':'indexed; image payload not yet screened'})
    with (output/'README.md').open('x',encoding='utf-8') as handle:
        handle.write('# Source dataset preparation\n\n'
            'This is the production preparation output, beyond the earlier eight-specimen pilot. '
            'source_layers.csv indexes all 1,117 source layers. The nominal gauge scope is layers 519–660 inclusive, across 64 fatigue-bar geometries. '
            'This range is a processing scope, not proof of usable XCT coverage.\n\n'
            'Layer shards contain standardized sensor inputs, candidate XCT-derived annotations, provenance and image-quality flags. '
            'Candidate labels remain separate from scientific validation status. Unknown support must not be treated as a confirmed negative. '
            'Source notes are preserved rather than turned into blanket layer exclusions.\n\n'
            'The raw HDF5 and existing pilot remain unchanged. This directory is not a claim that the full source has been cleaned or that final training labels are ready.\n')
    print(json.dumps({'output':str(output),'indexed_layers':layer_count,'nominal_gauge_layers':142,'fatigue_specimens':len(selected)},indent=2))


if __name__=='__main__':
    main()
