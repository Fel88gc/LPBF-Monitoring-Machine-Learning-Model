import json
import subprocess
import sys
from pathlib import Path
root=Path.cwd().resolve()
base=root/"data/cleaned/snow_source_preparation_v1"
worker=root/"src/cleaning_pipeline/prepare_source_layer.py"
for layer in range(620,661):
    target=base/"layers"/f"layer_{layer:04d}"
    if target.exists():
        continue
    stage=root/"work/source_preparation_ahead"/f"layer_{layer:04d}"
    if not stage.resolve().is_relative_to(root) or not target.resolve().is_relative_to(base):
        raise RuntimeError("Invalid workspace move boundary")
    stage.parent.mkdir(parents=True,exist_ok=True)
    log=stage.parent/f"layer_{layer:04d}.log"
    with log.open("x",encoding="utf-8") as handle:
        subprocess.run([sys.executable,"-B",str(worker),"--root",str(root),"--layer",str(layer),"--output",str(stage)],cwd=root,stdout=handle,stderr=subprocess.STDOUT,check=True)
    summary=json.loads((stage/"summary.json").read_text(encoding="utf-8"))
    if not summary["raw_size_and_mtime_unchanged"]:
        raise RuntimeError("Source changed")
    if target.exists():
        print(f"Main producer already reached {layer}; preserved staging output and stopped",flush=True)
        break
    try:
        stage.rename(target)
    except FileExistsError:
        print(f"Main producer won the target race at {layer}; preserved staging output and stopped",flush=True)
        break
    print(f"Prepared ahead layer {layer}: {summary['rows']} rows",flush=True)
