"""Create source-cohort diagrams for the integrated FYP report.

Reads saved source catalogs and the completed baseline protocol only.
Does not open raw HDF5, train models, or change earlier report assets.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch
import numpy as np


BLUE, INK, SECONDARY = "#2464A1", "#20313F", "#536474"
PALE_BLUE, PALE_GRAY, LINE = "#EDF4FA", "#F0F3F6", "#C7D2DC"
FILES = ("workflow.png", "specimen_prevalence_grid.png", "baseline_split.png", "diagram_sources.json")


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def read_csv(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(fig, out: Path, name: str) -> None:
    fig.savefig(out / name, dpi=300, facecolor="white")
    plt.close(fig)


def workflow(out: Path, source: dict, split: dict) -> list[dict]:
    stages = [
        {"title": "Author-supplied data processing", "status": "Supplied", "detail": "Optical calibration and registration; XCT reconstruction,\nregistration and algorithmic flaw detection", "pending": False},
        {"title": "Declared source scope", "status": "Complete", "detail": "64 named fatigue bars; layers 519-660; 24 x 24 camera patches\nNominal gauge scope, not verified per-voxel coverage", "pending": False},
        {"title": "Sensor preparation and catalog", "status": "Complete", "detail": f"{int(source['rows']):,} traceable rows; fixed integer-range rescaling\nQuality flags retained; source and shard provenance recorded", "pending": False},
        {"title": "Working candidate targets", "status": "Provisional", "detail": "73,649 candidate 1; 249,631 candidate 0; 6,548 unknown\nGrid mapping, measured support and target meaning need review", "pending": True},
        {"title": "Grouped baseline v1", "status": "Complete", "detail": "52 development / 12 held-out specimens; no specimen overlap\nSelection on four development folds; fixed holdout suite once", "pending": False},
        {"title": "Next scientific checkpoint", "status": "Pending", "detail": "Resolve grid, support and target semantics; check local agreement\nImprove within-specimen discrimination; seek cross-build evidence", "pending": True},
    ]
    fig = plt.figure(figsize=(6.5, 8.3))
    fig.text(.07, .955, "Source preparation through exploratory baseline v1", fontsize=14, weight="bold", color=INK)
    fig.text(.07, .915, "Completed engineering work and remaining scientific questions", fontsize=10.5, color=SECONDARY)
    ys = [.785, .660, .535, .410, .285, .160]
    for index, (stage, y) in enumerate(zip(stages, ys)):
        box = FancyBboxPatch((.07, y), .86, .105, transform=fig.transFigure,
                             boxstyle="round,pad=0.007,rounding_size=0.01", facecolor="white",
                             edgecolor=SECONDARY if stage["pending"] else LINE,
                             linestyle="--" if stage["pending"] else "-", linewidth=1)
        fig.add_artist(box)
        fig.text(.095, y+.077, f"{index+1}. {stage['title']}", fontsize=11.5, weight="bold", color=INK, va="center")
        fig.text(.905, y+.077, stage["status"], fontsize=10, color=SECONDARY if stage["pending"] else BLUE, va="center", ha="right")
        fig.text(.095, y+.035, stage["detail"], fontsize=10, color=SECONDARY, va="center", linespacing=1.3)
        if index < len(stages)-1:
            fig.add_artist(FancyArrowPatch((.5, y-.009), (.5, ys[index+1]+.114), transform=fig.transFigure,
                                           arrowstyle="-|>", mutation_scale=12, linewidth=1, color="#9BAAB7"))
    fig.text(.07, .045, "Source preparation is complete for the declared scope. Candidate validity\nand cross-build generalization remain unresolved.", fontsize=10, color=SECONDARY, linespacing=1.3)
    save(fig, out, FILES[0])
    return stages


def specimen_grid(out: Path, rows: list[dict]) -> list[dict]:
    rows = sorted(rows, key=lambda row: int(row["part_id"]))
    if len(rows) != 64 or len({int(row["part_id"]) for row in rows}) != 64:
        raise ValueError("Expected all 64 source specimens once")
    data = []
    for row in rows:
        one, zero, unknown = (int(row[key]) for key in ("candidate_one", "candidate_zero", "candidate_unknown"))
        known = one + zero
        data.append({"part_id": int(row["part_id"]), "candidate_one": one, "candidate_zero": zero,
                     "candidate_unknown": unknown, "known_candidate_rows": known,
                     "candidate_one_percent_among_0_1": 100 * one / known if known else None})
    values = np.array([row["candidate_one_percent_among_0_1"] if row["known_candidate_rows"] else np.nan for row in data]).reshape(8, 8)
    fig = plt.figure(figsize=(6.5, 6.7))
    fig.text(.075, .95, "Candidate annotation prevalence by specimen", fontsize=14, weight="bold", color=INK)
    fig.text(.075, .895, "Candidate 1 as a percentage of candidate 0/1 rows in each specimen", fontsize=10.5, color=SECONDARY)
    fig.text(.075, .855, "Unknown candidates are excluded from each cell's denominator.", fontsize=10.5, color=SECONDARY)
    ax = fig.add_axes([.075, .19, .85, .62])
    image = ax.imshow(values, vmin=0, vmax=100, cmap="Blues", interpolation="nearest", aspect="auto")
    for index, row in enumerate(data):
        yy, xx = divmod(index, 8)
        percent = row["candidate_one_percent_among_0_1"]
        text = f"P{row['part_id']:02d}\n{percent:.1f}%" if percent is not None else f"P{row['part_id']:02d}\nUndefined"
        ax.text(xx, yy, text, ha="center", va="center", fontsize=11, color="white" if percent is not None and percent >= 55 else INK, linespacing=1.2)
    ax.set_xticks([]); ax.set_yticks([])
    ax.set_xticks(np.arange(-.5, 8, 1), minor=True); ax.set_yticks(np.arange(-.5, 8, 1), minor=True)
    ax.grid(which="minor", color="white", linewidth=2)
    ax.tick_params(which="minor", bottom=False, left=False)
    for spine in ax.spines.values():
        spine.set_visible(False)
    cb_ax = fig.add_axes([.18, .115, .64, .022])
    bar = fig.colorbar(image, cax=cb_ax, orientation="horizontal", ticks=[0, 25, 50, 75, 100])
    bar.ax.set_xticklabels(["0%", "25%", "50%", "75%", "100%"])
    bar.ax.tick_params(labelsize=10, length=2)
    fig.text(.075, .025, "Ordered specimen IDs; this is not a spatial build layout.\nOne build; candidate labels remain physically unvalidated.", fontsize=10, color=SECONDARY, linespacing=1.3)
    save(fig, out, FILES[1])
    return data


def baseline_split(out: Path, split: dict, protocol: dict) -> None:
    rows = sorted(split["fold_counts"], key=lambda row: int(row["fold_id"]))
    if [int(row["fold_id"]) for row in rows] != list(range(5)):
        raise ValueError("Expected five saved specimen folds")
    if [int(row["specimen_count"]) for row in rows] != [12, 14, 12, 14, 12]:
        raise ValueError("Saved group counts differ from declared baseline v1")
    if sum(int(row["eligible_rows"]) for row in rows) != int(split["eligible_rows"]):
        raise ValueError("Fold eligible counts do not reconcile")
    fig = plt.figure(figsize=(6.5, 6.0))
    fig.text(.065, .945, "Whole-specimen split and development validation", fontsize=14, weight="bold", color=INK)
    fig.text(.065, .895, "323,280 candidate 0/1 rows; 6,548 unknown rows stay unsupervised", fontsize=10.5, color=SECONDARY)
    xs = [.19 + .155 * index for index in range(5)]
    width = .145
    fig.text(.065, .745, "Frozen\nspecimen\nfolds", fontsize=10, color=SECONDARY, va="center", linespacing=1.3)
    for row, x in zip(rows, xs):
        ident = int(row["fold_id"])
        fig.add_artist(FancyBboxPatch((x, .65), width, .18, transform=fig.transFigure,
                                     boxstyle="round,pad=0.003,rounding_size=0.008", facecolor=PALE_GRAY if ident == 0 else PALE_BLUE,
                                     edgecolor=SECONDARY if ident == 0 else BLUE, linewidth=1))
        text = f"FOLD {ident}\n{'TEST' if ident == 0 else 'DEVELOP'}\nn = {int(row['specimen_count'])}\n{int(row['eligible_rows']):,} rows"
        fig.text(x+width/2, .74, text, fontsize=10, color=INK, ha="center", va="center", linespacing=1.4)
    fig.text(.19, .58, "Four development runs; fold 0 remains untouched", fontsize=10.5, color=SECONDARY)
    for run, y in enumerate((.48, .40, .32, .24), start=1):
        fig.text(.065, y+.032, f"Dev run {run}", fontsize=10, color=SECONDARY, va="center")
        for fold, x in enumerate(xs):
            label = "Not used" if fold == 0 else "Validate" if fold == run else "Train"
            color = PALE_GRAY if fold == 0 else "white" if fold == run else PALE_BLUE
            fig.add_artist(FancyBboxPatch((x, y), width, .06, transform=fig.transFigure,
                                         boxstyle="square,pad=0.002", facecolor=color,
                                         edgecolor=SECONDARY if fold == 0 else BLUE, linewidth=1))
            fig.text(x+width/2, y+.03, label, fontsize=10, color=SECONDARY if fold == 0 else BLUE,
                     ha="center", va="center", weight="bold" if fold == run else "normal")
    fig.text(.065, .07, "Select the primary model using mean development-fold average precision.\nRefit on all 52 development specimens; score the fixed suite on fold 0 once.\nLogistic scalers are fitted only on the current training rows.",
             fontsize=10, color=SECONDARY, linespacing=1.4)
    save(fig, out, FILES[2])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--replace", action="store_true", help="Replace only this script's named diagram assets")
    args = parser.parse_args()
    root = args.root.resolve(strict=True)
    out = root / "reports/fyp_integrated_2026-11-08/assets"
    out.mkdir(parents=True, exist_ok=True)
    for name in FILES:
        if (out / name).exists() and not args.replace:
            raise FileExistsError(f"Existing diagram asset protected: {out / name}")
    source_dir = root / "data/cleaned/snow_source_preparation_v1/catalog"
    protocol_dir = root / "results/baseline_v1_2026-11-08/protocol"
    training_dir = root / "results/baseline_v1_2026-11-08/training"
    source = read_json(source_dir / "summary.json")
    specimens = read_csv(source_dir / "per_specimen.csv")
    split = read_json(protocol_dir / "split_summary.json")
    protocol = read_json(protocol_dir / "protocol.json")
    record = read_json(training_dir / "run_record.json")
    if source["stage"] != "source_preparation_catalog_complete" or record["status"] != "complete":
        raise ValueError("Completed source preparation and baseline are required")
    if sha(protocol_dir / "protocol.json") != record["protocol_sha256"]:
        raise ValueError("Protocol no longer matches completed baseline")
    if source["rows"] != split["all_rows"] or split["all_rows"] != 329828 or split["eligible_rows"] != 323280 or split["unknown_rows"] != 6548:
        raise ValueError("Source/split cohort counts do not match")
    if len(split["development_specimens"]) != 52 or len(split["test_specimens"]) != 12 or split["group_overlap"]:
        raise ValueError("Specimen split membership does not match the frozen protocol")
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10.5, "text.color": INK,
                         "figure.facecolor": "white", "savefig.facecolor": "white", "axes.unicode_minus": False})
    stages = workflow(out, source, split)
    grid_data = specimen_grid(out, specimens)
    if sum(row["known_candidate_rows"] for row in grid_data) != split["eligible_rows"]:
        raise ValueError("Specimen grid denominators do not match candidate 0/1 cohort")
    baseline_split(out, split, protocol)
    source_paths = [source_dir / "summary.json", source_dir / "per_specimen.csv", protocol_dir / "protocol.json",
                    protocol_dir / "split_summary.json", protocol_dir / "fold_counts.csv", training_dir / "run_record.json",
                    root / "results/data_quality/2026-11-08_run01/sources/source_semantics.md"]
    provenance = {
        "sources": [{"path": str(path), "sha256": sha(path)} for path in source_paths],
        "figures": [{"filename": name, "sha256": sha(out / name)} for name in FILES[:-1]],
        "workflow": stages, "specimen_grid_values": grid_data,
        "specimen_grid_denominator": "Each specimen's candidate_one + candidate_zero; unknown excluded; not a physical porosity measurement",
        "specimen_grid_layout": "Ascending specimen IDs in 8 rows of 8; no spatial-coordinate interpretation",
        "fold_counts": split["fold_counts"], "development_validation": protocol["development_cv"],
        "scaling_policy": protocol["scaling_policy"], "evaluation_flow": protocol["evaluation_flow"],
        "scientific_status": "Prepared source features and exploratory baseline complete; target registration/support/semantics remain unvalidated; one build",
        "script_sha256": sha(Path(__file__)), "width_inches": 6.5, "dpi": 300,
    }
    (out / FILES[3]).write_text(json.dumps(provenance, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps({"assets": str(out), "figures": list(FILES[:-1])}, indent=2))


if __name__ == "__main__":
    main()
