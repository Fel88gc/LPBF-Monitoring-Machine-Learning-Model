"""Resume source preparation over the declared nominal XCT gauge-layer scope."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import uuid
from collections import Counter
from pathlib import Path


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def atomic_json(path, value):
    temporary=path.with_name(path.name+'.'+uuid.uuid4().hex+'.tmp')
    with temporary.open('x',encoding='utf-8') as handle:
        json.dump(value,handle,indent=2,allow_nan=False)
    os.replace(temporary,path)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=Path.cwd())
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--resume',action='store_true')
    args=parser.parse_args()
    root,out=args.root.resolve(),args.output.resolve()
    if not out.is_relative_to(root/'data/cleaned'):
        raise ValueError('Use an isolated source-preparation directory under data/cleaned')
    config=read(out/'source_config.json')
    progress_path=out/'production_progress.json'
    if progress_path.exists() and not args.resume:
        raise FileExistsError('Existing progress is protected; explicitly use --resume')
    if (out/'production_summary.json').exists():
        raise FileExistsError('Production job is already complete; preserve it')
    raw=root/config['raw_source']
    before=raw.stat()
    worker=root/'src/cleaning_pipeline/prepare_source_layer.py'
    worker_hash=hashlib.sha256(worker.read_bytes()).hexdigest()
    layers=range(config['nominal_gauge_layer_start'],config['nominal_gauge_layer_end_inclusive']+1)
    logs=out/'logs'
    logs.mkdir(exist_ok=True)
    begun=time.monotonic()
    completed=[]
    summaries=[]
    for layer in layers:
        target=out/'layers'/f'layer_{layer:04d}'
        if target.exists():
            if not args.resume or not (target/'summary.json').is_file():
                raise FileExistsError(f'Existing/incomplete shard is protected: {target}')
            summary=read(target/'summary.json')
        else:
            if shutil.disk_usage(out).free < 5*1024**3:
                raise RuntimeError('Stopping before free space falls below 5 GiB; completed shards are preserved')
            log=logs/f'layer_{layer:04d}.log'
            with log.open('x',encoding='utf-8') as handle:
                try:
                    subprocess.run([sys.executable,'-B',str(worker),'--root',str(root),'--layer',str(layer),'--output',str(target)],
                                   cwd=root,stdout=handle,stderr=subprocess.STDOUT,check=True)
                except subprocess.CalledProcessError:
                    # A parallel producer may publish a completed shard after our existence check.
                    # Reuse it only through the full provenance/status checks below; never replace it.
                    if not (target/'summary.json').is_file():
                        raise
                    print(f'Found concurrently completed layer {layer}; verifying it instead of overwriting',flush=True)
            summary=read(target/'summary.json')
        if summary['script_sha256']!=worker_hash:
            raise RuntimeError('Worker code changed between shards; do not mix pipeline versions')
        if not summary['raw_size_and_mtime_unchanged'] or summary['source_size_bytes']!=before.st_size or summary['source_mtime_ns']!=before.st_mtime_ns:
            raise RuntimeError('Source preservation mismatch; stop before using this shard')
        if summary['layer']!=layer or summary['ready_for_model_training'] or summary['final_y_exported']:
            raise RuntimeError('Shard identity or provisional-status check failed')
        provenance_path=target/'shard_provenance.json'
        hashes={name:hashlib.sha256((target/name).read_bytes()).hexdigest() for name in ('features.npz','manifest.csv')}
        if provenance_path.exists():
            if read(provenance_path)['files_sha256']!=hashes:
                raise RuntimeError('Completed shard hash mismatch; refusing reuse')
        else:
            with provenance_path.open('x',encoding='utf-8') as handle:
                json.dump({'files_sha256':hashes,'worker_sha256':worker_hash},handle,indent=2)
        completed.append(layer)
        summaries.append(summary)
        progress={'stage':'source_preparation_running','completed_layers':completed,'total_layers':len(layers),
                  'prepared_patches':sum(item['rows'] for item in summaries),'quarantined_patches':sum(item['quarantined'] for item in summaries),
                  'elapsed_seconds_this_invocation':round(time.monotonic()-begun,2),
                  'last_completed_layer':layer,'ready_for_model_training':False}
        atomic_json(progress_path,progress)
        print(f"Prepared {len(completed)}/{len(layers)} layers; {progress['prepared_patches']} patches; latest {layer}",flush=True)
    raw_after=raw.stat()
    if (before.st_size,before.st_mtime_ns)!=(raw_after.st_size,raw_after.st_mtime_ns):
        raise RuntimeError('Raw size/mtime changed over the production run')
    candidates=Counter()
    flags=Counter()
    for summary in summaries:
        candidates.update(summary['candidate_label_counts'])
        flags.update(summary['quality_flag_counts'])
    result={'stage':'source_sensor_preparation_complete','layer_start':layers.start,'layer_end_inclusive':layers.stop-1,
            'layers_prepared':len(completed),'research_specimens_in_scope':config['specimen_count'],
            'prepared_patches':sum(s['rows'] for s in summaries),'quarantined_patches':sum(s['quarantined'] for s in summaries),
            'geometry_scope_excluded':sum(s['geometry_scope_excluded'] for s in summaries),
            'candidate_label_counts':dict(candidates),'quality_flag_counts':dict(flags),
            'logical_array_bytes_read':sum(s['logical_array_bytes_read'] for s in summaries),
            'sum_layer_elapsed_seconds':round(sum(s['elapsed_seconds'] for s in summaries),2),
            'total_output_bytes':sum(p.stat().st_size for p in out.rglob('*') if p.is_file()),
            'raw_size_and_mtime_unchanged':True,'raw_mode':'r','worker_sha256':worker_hash,
            'ready_for_model_training':False,'final_y_exported':False,
            'coverage_scope':'Nominal gauge-section layer range; not independently validated measured XCT support',
            'label_status':'candidate labels only; -1 means unknown proxy/bounds, 0/1 remain unvalidated',
            'source_layers_outside_scope_not_prepared':config['source_layer_count']-len(layers)}
    with (out/'production_summary.json').open('x',encoding='utf-8') as handle:
        json.dump(result,handle,indent=2)
    atomic_json(progress_path,{**progress,'stage':'source_sensor_preparation_complete'})
    print(json.dumps(result,indent=2))


if __name__=='__main__':
    main()
