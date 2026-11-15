"""Bounded read-only Snow metadata and original-script inventory.

Writes only new audit products, refuses overwrite, never imports original scripts.
Do not interpret the array-size ratio as a verified physical transform.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import math
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import h5py
import numpy as np

MAX_OBJECTS = 5000
MAX_SMALL_BYTES = 262144
MAX_ATTRIBUTE_ELEMENTS = 16384
CT_PATHS = ("/slices/registered_data/x-ray_ct_data", "/slices/registered_data/x-ray_ct_flaw")


def serial(value):
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    if isinstance(value, np.ndarray):
        if value.size > MAX_ATTRIBUTE_ELEMENTS:
            return {"shape": list(value.shape), "dtype": str(value.dtype),
                    "preview": serial(value.ravel()[:MAX_ATTRIBUTE_ELEMENTS]), "truncated": True}
        return serial(value.tolist())
    if isinstance(value, np.generic):
        return serial(value.item())
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, (list, tuple)):
        return [serial(x) for x in value]
    if isinstance(value, dict):
        return {str(k): serial(v) for k, v in value.items()}
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return repr(value)


def dump(path, value):
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(serial(value), stream, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write("\n")


def metadata(obj):
    info = {"path": obj.name, "type": "group" if isinstance(obj, h5py.Group) else "dataset",
            "attributes": serial(dict(obj.attrs))}
    if isinstance(obj, h5py.Group):
        info["child_count"] = len(obj)
    else:
        info.update(shape=list(obj.shape), dtype=str(obj.dtype), chunks=serial(obj.chunks),
                    compression=obj.compression, compression_opts=serial(obj.compression_opts),
                    fillvalue=serial(obj.fillvalue))
        if obj.chunks:
            logical = math.prod(math.ceil(n / c) for n, c in zip(obj.shape, obj.chunks))
            info["logical_chunk_count"] = logical
            info["stored_chunk_count"] = int(obj.id.get_num_chunks())
            info["all_logical_chunks_allocated"] = info["stored_chunk_count"] == logical
            info["stored_bytes"] = int(obj.id.get_storage_size())
    return info


def original_scripts(project):
    records = []
    for path in sorted((project / "src").glob("*.py")):
        source = path.read_text(encoding="utf-8-sig")
        lines = source.splitlines()
        tree = ast.parse(source, filename=str(path))
        imports, modes, writes = set(), [], []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(x.name.split(".")[0] for x in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.add(node.module.split(".")[0])
            if not isinstance(node, ast.Call):
                continue
            call = ast.unparse(node.func)
            if call == "h5py.File":
                mode = node.args[1] if len(node.args) > 1 else next(
                    (kw.value for kw in node.keywords if kw.arg == "mode"), None)
                modes.append({"line": node.lineno,
                              "mode": ast.literal_eval(mode) if isinstance(mode, ast.Constant) else "unspecified"})
            writing = call.endswith((".savefig", ".save", ".write_text", ".write_bytes", ".to_csv", ".to_excel"))
            writing |= call in {"np.save", "np.savez", "np.savez_compressed"}
            if call == "open":
                literals = [arg.value for arg in node.args[1:2] if isinstance(arg, ast.Constant)]
                literals += [kw.value.value for kw in node.keywords if kw.arg == "mode" and isinstance(kw.value, ast.Constant)]
                writing |= any(isinstance(x, str) and any(ch in x for ch in "wax+") for x in literals)
            if writing:
                writes.append({"line": node.lineno, "call": call,
                               "source": "\n".join(lines[node.lineno - 1:min(node.end_lineno, node.lineno + 7)])})
        records.append({"path": str(path.relative_to(project)),
                        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                        "imports": sorted(imports), "hdf5_modes": modes, "write_calls": writes,
                        "has_main_guard": any(isinstance(n, ast.If) and "__name__" in ast.unparse(n.test) for n in tree.body),
                        "rerun_class": "writes_fixed_outputs_review_before_rerun" if writes else "stdout_only_inspection",
                        "absolute_project_path_present": "C:\\NUS\\FYP\\FYP Organized" in source})
    return records


def inspect(project, output):
    raw = project / "data/raw/2024-05-01 M2 AMMTO Fatigue Blanks 05.hdf5"
    before = raw.stat()
    names = ["registration_metadata.json", "registration_findings.md", "script_inventory.json", "script_inventory.md"]
    if any((output / name).exists() for name in names):
        raise FileExistsError("Audit products exist; preserve them and select a new run")
    output.mkdir(parents=True, exist_ok=True)
    report = {"schema_version": 1, "created_utc": datetime.now(timezone.utc).isoformat(),
              "raw_file": str(raw), "raw_mode": "r", "raw_size_bytes": before.st_size,
              "raw_mtime_ns": before.st_mtime_ns,
              "limits": {"metadata_objects": MAX_OBJECTS, "small_dataset_bytes": MAX_SMALL_BYTES,
                         "attribute_elements": MAX_ATTRIBUTE_ELEMENTS, "full_ct_layers_read": False,
                         "full_3d_volumes_read": False},
              "metadata_objects": [], "small_dataset_values": {}, "selected_rows": {}, "id_patch_samples": []}
    with h5py.File(raw, "r") as h5:
        assert h5.mode == "r"
        report["metadata_objects"].append(metadata(h5))

        def record(name, obj):
            if len(report["metadata_objects"]) >= MAX_OBJECTS:
                return True
            report["metadata_objects"].append(metadata(obj))
            return None

        h5.visititems(record)
        report["metadata_inventory_truncated"] = len(report["metadata_objects"]) >= MAX_OBJECTS
        # Always inspect the controlling image grids, even if unrelated points metadata exhausts the tree limit.
        direct_paths = ["/slices", "/slices/camera_data", "/slices/camera_data/visible/0",
                        "/slices/camera_data/visible/1", "/slices/camera_data/nir/1",
                        "/slices/registered_data", *CT_PATHS,
                        "/slices/part_ids", "/slices/sample_ids", "/parts", "/temporal"]
        recorded = {item["path"] for item in report["metadata_objects"]}
        for path in direct_paths:
            if path in h5 and path not in recorded:
                report["metadata_objects"].append(metadata(h5[path]))
        attrs = dict(h5.attrs)
        report["root_attributes"] = serial(attrs)
        for kind, key in [("sample", "samples/sample_stl_filenames"), ("part", "parts/part_stl_filenames")]:
            report[kind + "_id_name_lookup"] = [{kind + "_id": i, "label": label}
                                                for i, label in enumerate(str(attrs[key]).split(","))]
        for item in report["metadata_objects"]:
            path = item["path"]
            if item["type"] != "dataset" or not path.startswith(("/parts/", "/temporal/")):
                continue
            ds = h5[path]
            if ds.size * ds.dtype.itemsize <= MAX_SMALL_BYTES:
                value = ds[()]
                row = {"values": serial(value)}
                if np.issubdtype(ds.dtype, np.number):
                    row.update(finite_count=int(np.isfinite(value).sum()), nonfinite_count=int((~np.isfinite(value)).sum()))
                report["small_dataset_values"][path] = row
        for group_path in ["/scans", "/points/myna_thesis_depth", "/points/myna_thesis_length",
                           "/points/myna_thesis_width", "/points/myna_thesis_time"]:
            if group_path not in h5:
                report["selected_rows"][group_path] = {"status": "not_present"}
                continue
            group = h5[group_path]
            names = list(group.keys())
            chosen = [name for name in names if name in {"600_point", "600_line", "600"}] or names[:1]
            for name in chosen[:2]:
                ds = group[name]
                indices = sorted({0, ds.shape[0] // 2, ds.shape[0] - 1}) if ds.shape and ds.shape[0] else []
                report["selected_rows"][ds.name] = {"indices": indices, "rows": [serial(ds[i]) for i in indices],
                                                       "purpose": "schema/coordinate example; not global extent"}
        for y, x in [(1997, 1994), (2021, 1994)]:
            example = {"layer": 600, "camera_y": y, "camera_x": x, "patch_size": 24, "arrays": {}}
            for path in ["/slices/part_ids", "/slices/sample_ids"]:
                values, counts = np.unique(h5[path][600, y:y + 24, x:x + 24], return_counts=True)
                example["arrays"][path] = [{"value": int(v), "count": int(n)} for v, n in zip(values, counts)]
            report["id_patch_samples"].append(example)
        camera, ct = h5["/slices/part_ids"], h5[CT_PATHS[0]]
        ratio = [ct.shape[i] / camera.shape[i] for i in [1, 2]]
        image_attrs = [item for item in report["metadata_objects"] if item["path"].startswith(
            ("/slices/camera_data", "/slices/registered_data", "/slices/part_ids", "/slices/sample_ids"))]
        report["mapping_evidence"] = {
            "camera_shape": list(camera.shape), "ct_shape": list(ct.shape), "shape_ratio_yx": ratio,
            "root_camera_dimensions_xy": [int(attrs["printer/x_camera_dimension"]), int(attrs["printer/y_camera_dimension"])],
            "root_physical_dimensions_xy_mm": [float(attrs["printer/x_real_dimension"]), float(attrs["printer/y_real_dimension"])],
            "camera_mm_per_pixel_if_outer_edges": [float(attrs["printer/y_real_dimension"]) / camera.shape[1], float(attrs["printer/x_real_dimension"]) / camera.shape[2]],
            "ct_mm_per_pixel_if_same_outer_edges_assumed": [float(attrs["printer/y_real_dimension"]) / ct.shape[1], float(attrs["printer/x_real_dimension"]) / ct.shape[2]],
            "endpoint_center_ratio_yx_if_first_and_last_centers_aligned": [(ct.shape[i] - 1) / (camera.shape[i] - 1) for i in [1, 2]],
            "image_object_attributes": {item["path"]: item["attributes"] for item in image_attrs},
            "status": "shared-coordinate metadata supports a candidate; exact numeric transform/center convention unverified",
            "limitations": ["Printer245mm is not an explicit XCT array extent.",
                            "Root slices/z-axis prose says third dimension; actual exports have layer axis first.",
                            "Prior registration history and registered_data naming are evidence of author processing, not an independent calibration."]}
        report["registration_log_lines"] = [line for line in str(attrs.get("core/change_log", "")).splitlines()
            if re.search(r"register(?:ing|ed) x-ray ct|calibration file|deleted the extant sample geometries|sample component geometry files", line, re.I)]
        report["coverage_evidence"] = {"ct_allocation": [metadata(h5[path]) for path in CT_PATHS],
            "sample_mask_semantics": "Lookup labels name 64 XCT gage geometries; geometric support does not prove measured validity at every voxel.",
            "raw_positive_proxy_limit": "Raw CT > 0 is a proxy: zero may be background, pore or absent data.",
            "flaw_zero_limit": "Zero flaw alone does not distinguish defect-negative material from absent/background data.",
            "layer_notes": {key: serial(value) for key, value in attrs.items() if key.startswith("layer_notes/")},
            "chunk_allocation_limit": "All logical XCT chunks allocated; allocation cannot be a measurement-coverage mask."}
        report["unresolved"] = ["No explicit XCT pitch, outer extent, affine transform or pixel-center convention in inspected metadata.",
            "Sample template masks do not independently prove experimental validity at each voxel.",
            "Review Methods/source definitions before finalizing one crop convention and scientific label validity."]
    after = raw.stat()
    report["raw_stat_unchanged"] = (before.st_size, before.st_mtime_ns) == (after.st_size, after.st_mtime_ns)
    if not report["raw_stat_unchanged"]:
        raise RuntimeError("Raw stat changed during read-only audit")
    scripts = original_scripts(project)
    dump(output / "registration_metadata.json", report)
    dump(output / "script_inventory.json", scripts)
    notes = ["# Snow registration metadata audit", "",
        "Raw opened strictly read-only. Original scripts were neither imported nor executed. No raw/pilot writes.", "",
        f"Inspected {len(report['metadata_objects'])} metadata objects; truncated={report['metadata_inventory_truncated']}. Preserved {len(attrs)} complete root attributes including change history and notes.", "",
        "## Coordinates", "",
        "Root describes a 245 x 245 mm camera field, 2844 x 2844 camera pixels and a bottom-left slice origin, x along the second image dimension and y along the first.",
        "Camera/ID shapes (1117,2844,2844); XCT shape (1117,13752,13752).",
        f"Candidate dimension ratio = {ratio[0]:.12f}. No explicit numeric XCT affine/pitch/outer extent/pixel-center convention found.",
        "The nominal printer/camera field is not an explicit CT extent. Consult Methods before approving physical mapping.",
        "Root z-axis prose and layer-first export shape differ; treat prose and storage ordering separately.", "",
        "## Coverage and identity", "",
        "Sample lookup names 64 XCT gage geometries, distinct from part IDs. Use the supplied lookup rather than sample_id == part_id.",
        "All logical XCT chunks are allocated, so allocation cannot determine measured coverage. Raw CT > 0 is only a proxy; flaw zero alone cannot verify a negative.",
        "Author layer notes identify approximate XCT gage start 519, end 660, top 702. Complete notes include NIR/camera issues on layers 40,41,42,200,478,602.", ""]
    for example in report["id_patch_samples"]:
        notes.append(f"- Layer 600 y={example['camera_y']} x={example['camera_x']}: {json.dumps(example['arrays'])}")
    notes.extend(["", "## Unresolved", ""] + ["- " + x for x in report["unresolved"]])
    notes.extend(["", f"Raw size/mtime unchanged = {report['raw_stat_unchanged']}. No full CT layer or 3D volume read.",
                  "Only small parts/temporal arrays, selected 3 rows per example points/scans dataset and two 24 x 24 ID patches read.", ""])
    with (output / "registration_findings.md").open("x", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(notes))
    inventory = ["# Original-script inventory", "", "Static AST inspection only; no original scripts imported/executed.", "",
                 "| Script | HDF5 modes | Writes outputs | Main guard |", "|---|---|---|---|"]
    for item in scripts:
        inventory.append(f"| {item['path']} | {','.join(str(x['mode']) for x in item['hdf5_modes'])} | {bool(item['write_calls'])} | {item['has_main_guard']} |")
    inventory.extend(["", "Fixed output filenames may overwrite prior results. JSON includes imports, hashes, write calls and line numbers.", ""])
    with (output / "script_inventory.md").open("x", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(inventory))
    print(json.dumps({"output": str(output), "objects": len(report['metadata_objects']),
                      "scripts": len(scripts), "raw_stat_unchanged": report['raw_stat_unchanged']}))


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    project, output = args.project.resolve(), args.output.resolve()
    approved = project / "results/data_quality"
    if not output.is_relative_to(approved.resolve()) or output == approved.resolve():
        parser.error("Audit output must be a new subdirectory of results/data_quality")
    inspect(project, output)


if __name__ == "__main__":
    main()
