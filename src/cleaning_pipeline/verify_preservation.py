"""Verify protected small-file hashes and raw HDF5 stat against a baseline."""
import argparse
import hashlib
import json
from pathlib import Path


def snapshot(root):
    files = list((root / "src").glob("*.py"))
    files += list((root / "data/processed").glob("*"))
    files += [root/name for name in ("readme.md", "snow_structure.txt", "snow_target_audit.txt")]
    files += [p for p in (root/"results").rglob("*") if p.is_file() and "data_quality" not in p.relative_to(root/"results").parts]
    records = [{"path": str(p.relative_to(root)), "size": p.stat().st_size,
                "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
               for p in sorted(set(files)) if p.is_file()]
    raw = root / "data/raw/2024-05-01 M2 AMMTO Fatigue Blanks 05.hdf5"
    stat = raw.stat()
    return {"files": records, "raw": {"path": str(raw.relative_to(root)), "size": stat.st_size,
            "mtime_ns": stat.st_mtime_ns, "verification_scope": "stat only; no full raw-file checksum"}}


def verify(root, baseline):
    checks = []
    for item in baseline["files"]:
        path = root / item["path"]
        actual = hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None
        checks.append({"path": item["path"], "expected_sha256": item["sha256"],
                       "actual_sha256": actual, "unchanged": actual == item["sha256"]})
    raw = root / baseline["raw"]["path"]
    stat = raw.stat()
    raw_ok = stat.st_size == baseline["raw"]["size"] and stat.st_mtime_ns == baseline["raw"]["mtime_ns"]
    return {"protected_files_checked": len(checks), "all_protected_hashes_unchanged": all(c["unchanged"] for c in checks),
            "raw_size_and_mtime_unchanged": raw_ok, "raw_full_checksum_performed": False, "files": checks}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root, output = args.root.resolve(), args.output.resolve()
    if not output.is_relative_to(root / "results/data_quality"):
        raise ValueError("Verification output must stay in audit results")
    result = verify(root, json.loads(args.baseline.read_text(encoding="utf-8")))
    with output.open("x", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2)
    print(json.dumps({key:value for key,value in result.items() if key != "files"}, indent=2))
    if not result["all_protected_hashes_unchanged"] or not result["raw_size_and_mtime_unchanged"]:
        raise RuntimeError("Protected source preservation check failed")


if __name__ == "__main__":
    main()
