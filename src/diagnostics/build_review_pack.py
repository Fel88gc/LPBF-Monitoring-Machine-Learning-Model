"""Build a bounded, development-only physical review pack without model scores.

Source targets and prepared features are preserved. Machine reproducibility checks
are separate from human physical-validity judgments, which remain pending.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import random
from collections import Counter, defaultdict
from pathlib import Path

import h5py
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


STRATA = {"ordinary_positive": 6, "ordinary_zero": 6, "unknown": 6,
          "boundary": 6, "author_event": 4, "nir_constant": 4}
TITLES = {"ordinary_positive": "ordinary candidate 1", "ordinary_zero": "ordinary candidate 0",
          "unknown": "unknown candidate", "boundary": "part boundary", "author_event": "author event context",
          "nir_constant": "constant NIR", "nir_constant_fallback": "ordinary flag fallback"}
POLICIES = ("round", "floor_ceil", "floor")
FOOTER_LINES = (
    "Sensors: fixed 0-1; CT: fixed stored 0-65,535.",
    "Mask: nonzero annotation. Physical mapping, measured support",
    "and target semantics remain unvalidated.",
)


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024*1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path, value):
    with Path(path).open("x", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, allow_nan=False)


def write_csv(path, rows, fields=None):
    fields = list(rows[0]) if fields is None and rows else fields or []
    with Path(path).open("x", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader(); writer.writerows(rows)


def select_records(catalog, folds, seed):
    names = [*STRATA, "ordinary_flags"]
    pools, counts = {name: [] for name in names}, Counter()
    rngs = {name: random.Random(seed+137*(index+1)) for index, name in enumerate(names)}
    with catalog.open(newline="", encoding="utf-8-sig") as handle:
        header = next(csv.reader(handle))
    with catalog.open(newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            fold = int(folds[str(int(row["part_id"]))])
            if fold == 0:
                continue  # Do not use held-out references, flags or images for review selection.
            target, fraction = int(row["candidate_y"]), float(row["part_fraction"])
            flags = set(filter(None, row["quality_flags"].split(";")))
            constant = any(int(row[f"channel_{channel}_constant"]) for channel in range(3))
            event = "author_layer_event_affected_region_requires_review" in flags
            ordinary = target in (0, 1) and fraction > .90 and not constant and not event
            qualifies = {"ordinary_positive": ordinary and target == 1, "ordinary_zero": ordinary and target == 0,
                         "unknown": target == -1, "boundary": target in (0, 1) and .75 <= fraction <= .90,
                         "author_event": event, "nir_constant": int(row["channel_2_constant"]) == 1,
                         "ordinary_flags": ordinary and bool(flags)}
            compact = {field: row[field] for field in ("sample_id", "part_id", "layer", "catalog_row")}
            for name, match in qualifies.items():
                if not match:
                    continue
                counts[name] += 1
                pool = pools[name]
                if len(pool) < 1024:
                    pool.append(compact)
                else:
                    index = rngs[name].randrange(counts[name])
                    if index < 1024:
                        pool[index] = compact
    selected, used, diversity_log = {}, set(), []
    ordinary_parts, ordinary_layers = set(), set()

    def take(name, count, shared_parts=None, shared_layers=None):
        candidates = pools[name].copy()
        rngs[name].shuffle(candidates)
        parts = shared_parts if shared_parts is not None else set()
        layers = shared_layers if shared_layers is not None else set()
        chosen, relaxations = [], []
        for level in range(3):
            for item in candidates:
                ident, part, layer = item["sample_id"], int(item["part_id"]), int(item["layer"])
                if ident in used or (level == 0 and (part in parts or layer in layers)) or (level == 1 and part in parts):
                    continue
                chosen.append(item); used.add(ident); parts.add(part); layers.add(layer)
                if level:
                    relaxations.append({"sample_id": ident, "rule": "repeated layer permitted" if level == 1 else "repeated specimen/layer permitted for available stratum"})
                if len(chosen) == count:
                    break
            if len(chosen) == count:
                break
        diversity_log.append({"stratum": name, "available_development_rows": counts[name], "selected": len(chosen),
                              "distinct_selected_parts": len({int(item["part_id"]) for item in chosen}),
                              "distinct_selected_layers": len({int(item["layer"]) for item in chosen}), "relaxations": relaxations})
        return chosen

    # Reserve rare categories first so ordinary random examples cannot consume them.
    for name in ("nir_constant", "author_event", "boundary", "unknown", "ordinary_positive", "ordinary_zero"):
        requested = STRATA[name]
        selected[name] = take(name, requested, ordinary_parts if name.startswith("ordinary_") else None,
                              ordinary_layers if name.startswith("ordinary_") else None)
        for item in selected[name]:
            item.update(requested_stratum=name, selection_stratum=name, selection_reason="seeded reservoir plus specimen/layer diversity; no model outputs used")
        shortage = requested-len(selected[name])
        if shortage:
            if name != "nir_constant":
                raise ValueError(f"Not enough disjoint development examples for {name}")
            fallback = take("ordinary_flags", shortage)
            if len(fallback) != shortage:
                raise ValueError("Insufficient explicitly permitted ordinary flagged replacements")
            for item in fallback:
                item.update(requested_stratum=name, selection_stratum="nir_constant_fallback",
                            selection_reason=f"Only {counts[name]} development constant-NIR rows available; ordinary informational-flag example substituted")
            selected[name].extend(fallback)
    ordered = [item for name in STRATA for item in selected[name]]
    wanted = {item["sample_id"]: item for item in ordered}
    full = {}
    with catalog.open(newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            if row["sample_id"] in wanted:
                full[row["sample_id"]] = row
    records = []
    for index, item in enumerate(ordered, start=1):
        row = {**full[item["sample_id"]], **item, "review_id": f"R{index:02d}", "fold_id": int(folds[str(int(item["part_id"]))])}
        if row["fold_id"] not in (1, 2, 3, 4):
            raise ValueError("Protected test specimen reached review selection")
        records.append(row)
    if len(records) != 32 or len({row["sample_id"] for row in records}) != 32:
        raise ValueError("Expected 32 disjoint development review cases")
    return records, {"seed": seed, "available_development_rows": dict(counts), "diversity": diversity_log,
                     "selection_policy": "Uniform seeded reservoirs of up to1024 rows per requested stratum, followed by deterministic randomized specimen/layer diversity. Purposeful review sampling, not prevalence estimation.",
                     "ordinary_definition": "candidate0/1, part fraction>0.90, no constant channel or author-event flag; stored maxima alone are allowed",
                     "allocation_order": "rare constant/event categories reserved first; no model predictions, errors or metrics read",
                     "protected_test_fold": 0, "selected_fold_ids": sorted({row["fold_id"] for row in records}), "requested_strata": STRATA}


def prepared_images(root, records):
    by_shard, images, hashes = defaultdict(list), {}, {}
    for row in records:
        by_shard[row["feature_shard"]].append(row)
    for name, rows in by_shard.items():
        path = (root/name).resolve(strict=True)
        if not path.is_relative_to(root/"data/cleaned"):
            raise ValueError("Prepared sensor shard is outside source preparation")
        before = sha(path)
        provenance = read_json(path.parent/"shard_provenance.json")
        if before != provenance["files_sha256"]["features.npz"]:
            raise ValueError(f"Prepared image provenance mismatch: {path}")
        with np.load(path, allow_pickle=False) as archive:
            X = archive["X"]
            for row in rows:
                index = int(row["feature_row"])
                image = X[index].copy()
                if image.shape != (3, 24, 24) or not np.isfinite(image).all() or image.min() < 0 or image.max() > 1:
                    raise ValueError(f"Invalid prepared camera image: {row['sample_id']}")
                if int(archive["candidate_y"][index]) != int(row["candidate_y"]) or int(archive["groups"][index]) != int(row["part_id"]) or int(archive["layers"][index]) != int(row["layer"]):
                    raise ValueError("Prepared image/metadata identity mismatch")
                images[row["sample_id"]] = image
            del X
        hashes[name] = before
    return images, hashes


def bounds(row, sy, sx, policy):
    y, x, size = int(row["camera_y"]), int(row["camera_x"]), int(row["patch_size"])
    if policy == "round":
        start, stop = round, round
    elif policy == "floor_ceil":
        start, stop = math.floor, math.ceil
    else:
        start, stop = math.floor, math.floor
    return start(y*sy), stop((y+size)*sy), start(x*sx), stop((x+size)*sx)


def raw_diagnostics(root, records):
    source_names = {row["source_hdf5"] for row in records}
    if len(source_names) != 1:
        raise ValueError("Expected one protected raw source")
    raw = (root/source_names.pop()).resolve(strict=True)
    if not raw.is_relative_to(root/"data/raw"):
        raise ValueError("Raw source is outside immutable source directory")
    stat_before = raw.stat()
    displayed, results, logical_bytes = {}, [], 0
    with h5py.File(raw, "r", rdcc_nbytes=16*1024**2) as handle:
        ct, flaw = handle["/slices/registered_data/x-ray_ct_data"], handle["/slices/registered_data/x-ray_ct_flaw"]
        camera_shape = handle["/slices/part_ids"].shape
        sy, sx = ct.shape[1]/camera_shape[1], ct.shape[2]/camera_shape[2]
        if not np.issubdtype(ct.dtype, np.unsignedinteger):
            raise ValueError("CT display reference requires an explicitly documented range for nonunsigned storage")
        display = {"dtype": str(ct.dtype), "vmin": 0, "vmax": int(np.iinfo(ct.dtype).max),
                   "reference": "Common full stored unsigned integer range; not calibrated attenuation; no per-image percentile stretch"}
        for row in records:
            windows = {policy: bounds(row, sy, sx, policy) for policy in POLICIES}
            expected = tuple(int(row[key]) for key in ("xct_y0", "xct_y1", "xct_x0", "xct_x1"))
            if windows["round"] != expected:
                raise ValueError("Independent crop formula did not reproduce source manifest")
            valid = {policy: 0 <= box[0] < box[1] <= ct.shape[1] and 0 <= box[2] < box[3] <= ct.shape[2] for policy, box in windows.items()}
            actual = [box for policy, box in windows.items() if valid[policy]]
            uy0, uy1 = min(box[0] for box in actual), max(box[1] for box in actual)
            ux0, ux1 = min(box[2] for box in actual), max(box[3] for box in actual)
            if (uy1-uy0)*(ux1-ux0)*(ct.dtype.itemsize+flaw.dtype.itemsize) > 1024**2:
                raise ValueError("Bounded review tile exceeded1MiB")
            gray = ct[int(row["layer"]), uy0:uy1, ux0:ux1]
            mask = flaw[int(row["layer"]), uy0:uy1, ux0:ux1]
            logical_bytes += gray.nbytes+mask.nbytes
            for policy, (y0, y1, x0, x1) in windows.items():
                count, proxy, candidate = None, None, -1
                if valid[policy]:
                    g, m = gray[y0-uy0:y1-uy0, x0-ux0:x1-ux0], mask[y0-uy0:y1-uy0, x0-ux0:x1-ux0]
                    count, proxy = int(np.count_nonzero(m)), float(np.mean(g > 0))
                    if proxy >= .50:
                        candidate = int(count > 0)
                    if policy == "round":
                        if count != int(row["candidate_flaw_pixels"]) or not np.isclose(proxy, float(row["raw_xct_positive_proxy"]), rtol=0, atol=1e-12) or candidate != int(row["candidate_y"]):
                            raise ValueError("Read-only source reproduction check failed")
                        displayed[row["sample_id"]] = (g.copy(), (m != 0).astype(np.uint8))
                results.append({"review_id": row["review_id"], "sample_id": row["sample_id"], "fold_id": row["fold_id"], "policy": policy,
                                "xct_y0": y0, "xct_y1": y1, "xct_x0": x0, "xct_x1": x1,
                                "bounds_valid": valid[policy], "raw_xct_positive_proxy": proxy, "nonzero_annotation_pixels": count,
                                "candidate_y": candidate, "reference_candidate_y": int(row["candidate_y"]),
                                "candidate_changed_vs_round": candidate != int(row["candidate_y"]),
                                "count_changed_vs_round": count is not None and count != int(row["candidate_flaw_pixels"]),
                                "physical_mapping_status": "pending", "measured_coverage_status": "pending"})
    after = raw.stat()
    unchanged = (stat_before.st_size, stat_before.st_mtime_ns) == (after.st_size, after.st_mtime_ns)
    if not unchanged:
        raise RuntimeError("Protected raw source size/mtime changed")
    return displayed, results, {"raw_source": str(raw), "raw_open_mode": "r", "raw_size_bytes": stat_before.st_size,
                                "raw_mtime_ns": stat_before.st_mtime_ns, "raw_size_and_mtime_unchanged": unchanged,
                                "logical_array_bytes_read": logical_bytes, "hdf5_default_dataset_cache_bytes": 16*1024**2,
                                "io_note": "32 small union crops for CT and flaw rasters only; compressed chunks may read additional bytes; no whole CT layer or raw sensor images loaded",
                                "ct_display": display}


def figures(out, records, sensors, raw, display):
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "figure.facecolor": "white", "axes.unicode_minus": False})
    files = []
    for page in range(8):
        cases = records[page*4:(page+1)*4]
        fig = plt.figure(figsize=(6.5, 8.3))
        fig.text(.07, .957, f"Development review cases {cases[0]['review_id']}-{cases[-1]['review_id']}", fontsize=14, weight="bold", color="#20313F")
        fig.text(.07, .918, "Frozen development folds only; human physical review remains pending.", fontsize=10, color="#536474")
        for col, name in enumerate(("Visible melt", "Visible recoat", "NIR max", "XCT gray", "XCT mask")):
            fig.text(.16+.18*col, .868, name, ha="center", fontsize=10, color="#20313F")
        for index, row in enumerate(cases):
            top = .83-.184*index
            fig.text(.07, top, f"{row['review_id']} | {TITLES[row['selection_stratum']]} | P{int(row['part_id']):02d} L{row['layer']} Y{row['camera_y']} X{row['camera_x']} | fold{row['fold_id']}",
                     fontsize=10, weight="bold", va="top", color="#20313F")
            fig.text(.07, top-.024, f"candidate={row['candidate_y']}; part fraction={float(row['part_fraction']):.3f}; XCT proxy={float(row['raw_xct_positive_proxy']):.3f}; annotation pixels={row['candidate_flaw_pixels']}",
                     fontsize=10, va="top", color="#536474")
            gray, mask = raw[row["sample_id"]]
            arrays = [*sensors[row["sample_id"]], gray, mask]
            for col, array in enumerate(arrays):
                ax = fig.add_axes([.08+.18*col, .655-.184*index, .16, .16*6.5/8.3])
                ax.imshow(array, cmap="inferno" if col == 2 else "gray", origin="lower", interpolation="nearest",
                          vmin=display["vmin"] if col == 3 else 0, vmax=display["vmax"] if col == 3 else 1)
                ax.set_xticks([]); ax.set_yticks([])
        fig.text(.07, .025, "\n".join(FOOTER_LINES),
                 fontsize=10, color="#536474", linespacing=1.3)
        name = f"review_{page+1:02d}.png"
        path = out/name
        if path.exists():
            raise FileExistsError(f"Existing review figure protected: {path}")
        fig.savefig(path, dpi=300, facecolor="white"); plt.close(fig)
        files.append(path)
    return files


def repair_figure_footers(root):
    """Repair only owned chart annotations; never reopen sensor or XCT data."""
    from PIL import Image, ImageDraw, ImageFont
    from matplotlib.font_manager import findfont

    result = root/"results/development_diagnostics_v1_2026-11-08/review"
    assets = root/"reports/development_diagnostics_v1_2026-11-08/assets"
    provenance_path = result/"selection_provenance.json"
    provenance = read_json(provenance_path)
    repaired = []
    for index in range(1, 9):
        path = assets/f"review_{index:02d}.png"
        with Image.open(path) as source:
            image = source.copy()
        width, height = image.size
        strip_start = round(height*.919)  # Below every scientific panel and row label.
        panels_before = hashlib.sha256(image.crop((0, 0, width, strip_start)).tobytes()).hexdigest()
        draw = ImageDraw.Draw(image)
        draw.rectangle((0, strip_start, width, height), fill="white")
        font = ImageFont.truetype(findfont("DejaVu Sans"), round(10*300/72))
        left, top = round(width*.07), strip_start+20
        for line in FOOTER_LINES:
            box = draw.textbbox((left, top), line, font=font)
            if box[2] > width-left or box[3] > height-20:
                raise ValueError("Repaired footer would escape the report figure")
            draw.text((left, top), line, font=font, fill="#536474")
            top += round(font.size*1.3)
        panels_after = hashlib.sha256(image.crop((0, 0, width, strip_start)).tobytes()).hexdigest()
        if panels_before != panels_after:
            raise RuntimeError("Footer-only repair changed scientific panel pixels")
        image.save(path, dpi=(300, 300))
        repaired.append({"path": str(path.relative_to(root)), "panel_pixels_sha256_before": panels_before,
                         "panel_pixels_sha256_after": panels_after, "panel_pixels_unchanged": True})
    provenance["script_sha256"] = sha(Path(__file__))
    provenance["figures"] = [{"path": item["path"], "sha256": sha(root/item["path"])} for item in repaired]
    provenance["footer_repair"] = {"additional_raw_or_prepared_data_reads": 0,
                                    "method": "Own PNG footer-strip annotation repair only; every scientific panel pixel preserved",
                                    "figures": repaired}
    provenance_path.write_text(json.dumps(provenance, indent=2, allow_nan=False), encoding="utf-8")
    checks_path = result/"machine_checks.json"
    checks = read_json(checks_path)
    checks["ct_visualization_limit"] = "Common full stored uint16 display has low contrast; a dark rendering is not evidence of absent flaws or unusable support. Any additional common-window diagnostic must declare its display reference and must not alter source values or targets."
    checks_path.write_text(json.dumps(checks, indent=2, allow_nan=False), encoding="utf-8")
    readme = result/"README.md"
    note = "\nCT viewing limit: the common full stored uint16 range can render CT with little contrast. Dark appearance does not establish absence of flaws or measured support. A separately documented common-window visualization could assist review without changing measurements, annotations or target policy.\n"
    text = readme.read_text(encoding="utf-8")
    if "CT viewing limit:" not in text:
        readme.write_text(text+note, encoding="utf-8")
    print(json.dumps({"footer_repair_complete": True, "figures": len(repaired), "raw_or_prepared_data_reads": 0,
                      "all_scientific_panel_pixels_unchanged": True}, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--repair-figure-footers", action="store_true", help="Repair only this script's existing PNG footer text; no source data reads")
    args = parser.parse_args()
    root = args.root.resolve(strict=True)
    if args.repair_figure_footers:
        repair_figure_footers(root)
        return
    result = root/"results/development_diagnostics_v1_2026-11-08/review"
    assets = root/"reports/development_diagnostics_v1_2026-11-08/assets"
    if result.exists() or any((assets/f"review_{index:02d}.png").exists() for index in range(1, 9)):
        raise FileExistsError("Existing review output is protected")
    protocol_dir = root/"results/baseline_v1_2026-11-08/protocol"
    protocol, split = read_json(protocol_dir/"protocol.json"), read_json(protocol_dir/"split_summary.json")
    expected = read_json(protocol_dir/"artifact_hashes.json")
    for name in ("protocol.json", "split_summary.json", "splits.npz"):
        if sha(protocol_dir/name) != expected[name]:
            raise ValueError("Frozen protocol artifact changed")
    if protocol["test_fold"] != 0 or protocol["development_folds"] != [1, 2, 3, 4]:
        raise ValueError("Unexpected protected test/development folds")
    catalog = root/"data/cleaned/snow_source_preparation_v1/catalog/manifest.csv"
    inputs = [catalog, protocol_dir/"protocol.json", protocol_dir/"split_summary.json", protocol_dir/"splits.npz", protocol_dir/"artifact_hashes.json"]
    before = {str(path.relative_to(root)): sha(path) for path in inputs}
    if sha(catalog) != protocol["input_provenance"]["catalog_manifest_sha256"]:
        raise ValueError("Frozen source catalog changed")
    records, selection = select_records(catalog, split["specimen_to_fold"], int(protocol["seed"])+4001)
    sensors, shard_hashes = prepared_images(root, records)
    raw_images, sensitivity, checks = raw_diagnostics(root, records)
    after = {str(path.relative_to(root)): sha(path) for path in inputs}
    if before != after or any(sha(root/name) != digest for name, digest in shard_hashes.items()):
        raise RuntimeError("Read-only review input preservation check failed")
    result.mkdir(parents=True, exist_ok=False); assets.mkdir(parents=True, exist_ok=True)
    image_files = figures(assets, records, sensors, raw_images, checks["ct_display"])
    for index, row in enumerate(records):
        row["review_figure"] = str(image_files[index//4].relative_to(root))
    write_csv(result/"selected_catalog_records.csv", records)
    write_json(result/"selection_provenance.json", {**selection, "input_sha256_before": before, "input_sha256_after": after,
               "prepared_shards_sha256": shard_hashes, "selection_uses_model_outputs": False, "test_rows_selected": 0,
               "selected_specimen_ids": sorted({int(row["part_id"]) for row in records}),
               "script_sha256": sha(Path(__file__)), "figures": [{"path": str(path.relative_to(root)), "sha256": sha(path)} for path in image_files]})
    write_csv(result/"crop_policy_sensitivity.csv", sensitivity)
    policy_summary = {name: {"candidate_counts": dict(Counter(str(row["candidate_y"]) for row in sensitivity if row["policy"] == name)),
                            "candidate_changed_vs_round": sum(row["candidate_changed_vs_round"] for row in sensitivity if row["policy"] == name),
                            "counts_changed_vs_round": sum(row["count_changed_vs_round"] for row in sensitivity if row["policy"] == name)} for name in POLICIES}
    write_json(result/"machine_checks.json", {**checks, "cases": len(records), "source_sensor_metadata_checks_passed": True,
               "round_counts_and_proxy_reproduced": True, "input_hashes_unchanged": True,
               "selected_fold_ids": selection["selected_fold_ids"], "test_fold_selected": False,
               "policy_sensitivity": policy_summary, "human_review_status": "pending", "physical_validation_performed": False,
               "scientific_limit": "Sampling is purposeful; crop-sensitivity counts describe these32 selected cases only. No policy was selected, no source target was changed, and no final y was issued."})
    template = [{"review_id": row["review_id"], "sample_id": row["sample_id"], "selection_stratum": row["selection_stratum"],
                 "fold_id": row["fold_id"], "part_id": row["part_id"], "layer": row["layer"], "candidate_y": row["candidate_y"],
                 "review_figure": row["review_figure"], "human_review_status": "pending", "correspondence_assessment": "",
                 "usable_xct_support_assessment": "", "annotation_interpretation": "", "sensor_quality_assessment": "",
                 "boundary_uncertainty": "", "evidence_or_author_reference": "", "proposed_followup": "", "reviewer": "", "review_date": ""} for row in records]
    write_csv(result/"human_review_template.csv", template)
    text = """# Development-only physical review pack

32 disjoint cases were selected by frozen specimen folds and source strata, not
model scores/errors. Fold0 specimens were excluded before selection. This is a
purposeful review sample, not an estimate of full-cohort error or prevalence.
Only prepared sensor shards and small mapped raw XCT/annotation crops were read.

Machine checks establish reproduction under a candidate grid policy; they do not
establish physical correspondence, actual measured support or flaw truth. Human
status remains pending in every row. No source label or feature was changed and
no final y target was created. A low grayscale-positive proxy stays unknown under
each policy; the three policies are descriptive alternatives, not a competition.

Review questions:
1. Where an independent material/part edge or landmark is visible, do the sensor
   and reconstructed-CT regions plausibly correspond? What external calibration
   or known-coordinate evidence is needed, including exact grid-center convention?
2. Does the crop fall inside actually reconstructed usable CT support, rather
   than merely nominal sample geometry or nonzero grayscale intensity? If this
   cannot be determined, record unresolved support rather than asserting negative.
3. What do nonzero XCT raster values mean under the author's detector and limits?
   Are small/boundary annotations robust to location uncertainty? A binary mask
   display is not a pore count or manual confirmation.
4. Do constant NIR channels or author-event contexts need targeted investigation?
   A stored endpoint is not by itself proof of saturation; no generic denoising,
   exclusion or label change should be inferred from this review pack alone.

Use human_review_template.csv to record evidence and questions. Keep those human
judgments separate from machine_checks.json. Source selection and every figure
are traceable through selected_catalog_records.csv and selection_provenance.json.
"""
    with (result/"README.md").open("x", encoding="utf-8") as handle:
        handle.write(text)
    print(json.dumps({"output": str(result), "case_counts": dict(Counter(row["selection_stratum"] for row in records)),
                      "raw_diagnostics": checks, "policy_sensitivity": policy_summary}, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
