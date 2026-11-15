"""Run the bounded Snow audit to a new checkpoint; never train ML models.

This reproduces diagnostics and an unchanged provisional review package.
It does not approve or finalize physical registration, coverage or labels.
"""
from __future__ import annotations
import argparse
import importlib.metadata
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from verify_preservation import snapshot, verify


def save(path, data):
    with path.open("x", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--run-id", default=datetime.now().strftime("%Y-%m-%d_%H%M%S"))
    args = parser.parse_args()
    root = args.root.resolve(strict=True)
    if not re.fullmatch(r"[A-Za-z0-9_-]+", args.run_id):
        parser.error("Run ID may contain letters, digits, underscores and hyphens only")
    run = root / "results/data_quality" / args.run_id
    targets = [run, root/"data/review"/args.run_id, root/"reports/data_cleaning"/args.run_id]
    if any(path.exists() for path in targets):
        raise FileExistsError("A run/review/report destination exists; choose a new run ID")
    if not (root/"data/raw/2024-05-01 M2 AMMTO Fatigue Blanks 05.hdf5").is_file():
        raise FileNotFoundError("Local Snow HDF5 is unavailable; no upload or fallback is attempted")
    run.mkdir(parents=True)
    logs = run/"logs"
    logs.mkdir()
    baseline = snapshot(root)
    save(run/"protection_baseline.json", baseline)
    save(run/"environment_snapshot.json", {"python":sys.version,"executable":sys.executable,
        "packages":{name:importlib.metadata.version(name) for name in ("numpy","h5py","matplotlib","scipy","pandas","Pillow")}})
    scripts = root/"src/cleaning_pipeline"
    tasks = [
        ("registration", "inspect_registration.py", ["--project",str(root),"--output",str(run/"registration")]),
        ("pilot", "audit_pilot.py", ["--root",str(root),"--output",str(run/"pilot/final")]),
        ("spatial", "compare_spatial.py", ["--root",str(root),"--output",str(run/"spatial")]),
        ("review_package", "assemble_review.py", ["--root",str(root),"--run",str(run)]),
        ("review_figures", "make_review_figures.py", ["--root",str(root),"--run",str(run)]),
    ]
    commands=[]
    for name, script, arguments in tasks:
        command = [sys.executable,"-B",str(scripts/script),*arguments]
        print(f"Running {name}; log: {logs/name}.log", flush=True)
        with (logs/f"{name}.log").open("x",encoding="utf-8") as log:
            subprocess.run(command,cwd=root,stdout=log,stderr=subprocess.STDOUT,check=True)
        commands.append(command)
    preservation = verify(root,baseline)
    save(run/"protection_verification.json",preservation)
    if not preservation["all_protected_hashes_unchanged"] or not preservation["raw_size_and_mtime_unchanged"]:
        raise RuntimeError("Preservation failed; inspect evidence before continuing")
    command = [sys.executable,"-B",str(scripts/"write_report.py"),"--root",str(root),"--run",str(run)]
    with (logs/"report.log").open("x",encoding="utf-8") as log:
        subprocess.run(command,cwd=root,stdout=log,stderr=subprocess.STDOUT,check=True)
    commands.append(command)
    save(run/"commands.json",commands)
    print(f"Audit complete. Provisional labels only; no ML training. Report: {root/'reports/data_cleaning'/args.run_id/'report.md'}")


if __name__ == "__main__":
    main()
