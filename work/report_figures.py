"""Create inspected static figures for the FYP progress report from saved catalogs.

No raw HDF5 or feature arrays are opened. Existing pipeline files are unchanged.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Rectangle
from matplotlib.ticker import FuncFormatter
import numpy as np


COLORS = {"candidate_one": "#2464A1", "candidate_zero": "#B4BEC8", "candidate_unknown": "#D98A2B"}
INK, SECONDARY, GRID = "#20313F", "#536474", "#E6EBEF"
FIGURES = (
    "source_candidate_composition.png", "source_specimen_composition_P02_P33.png",
    "source_specimen_composition_P35_P66.png", "source_candidates_by_layer.png",
    "fyp_workflow_checkpoint.png",
)
DATA_FILES = ("figure_data_source_summary.json", "figure_data_per_specimen.csv", "figure_data_per_layer.csv", "figure_sources.json")


def read_csv(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def finish(fig, path: Path) -> None:
    fig.savefig(path, dpi=300, facecolor="white")
    plt.close(fig)


def caption(fig, text: str, y: float = .035) -> None:
    fig.text(.08, y, text, fontsize=10, color=SECONDARY, ha="left", va="bottom", linespacing=1.35)


def composition(summary: dict, out: Path) -> None:
    total = int(summary["rows"])
    fig = plt.figure(figsize=(6.5, 3.35))
    fig.text(.08, .925, "Prepared source patches: provisional target status", fontsize=14, weight="bold", color=INK)
    fig.text(.08, .835, f"{total:,} patches | 64 specimens | layers 519-660 | one build", fontsize=10.5, color=SECONDARY)
    ax = fig.add_axes([.08, .48, .86, .19])
    left = 0
    for key in COLORS:
        value = int(summary[key])
        ax.barh([0], [value], left=left, height=.6, color=COLORS[key], edgecolor="white", linewidth=1)
        left += value
    ax.set_xlim(0, total)
    ax.set_ylim(-.5, .5)
    ax.set_yticks([])
    ax.set_xticks(np.linspace(0, total, 5), ["0%", "25%", "50%", "75%", "100%"])
    ax.tick_params(axis="x", labelsize=10, colors=SECONDARY, length=0, pad=6)
    for spine in ax.spines.values():
        spine.set_visible(False)
    labels = [("candidate_one", "Candidate 1"), ("candidate_zero", "Candidate 0"), ("candidate_unknown", "Unknown (-1)")]
    for x, (key, label) in zip((.08, .37, .69), labels):
        fig.add_artist(Rectangle((x, .305), .025, .035, transform=fig.transFigure, facecolor=COLORS[key], edgecolor="none"))
        fig.text(x + .04, .337, label, fontsize=10.5, color=INK, va="top", weight="bold")
        count = int(summary[key])
        fig.text(x + .04, .253, f"{count:,} ({count / total:.1%})", fontsize=10.5, color=INK, va="top")
    caption(fig, "All candidates remain unvalidated. Unknown is retained as a separate status.\nThese patch fractions are not physical porosity measurements.")
    finish(fig, out / FIGURES[0])


def specimen_panel(rows: list[dict], name: str, out: Path) -> None:
    ids = [int(row["part_id"]) for row in rows]
    totals = np.array([int(row["rows"]) for row in rows])
    fig = plt.figure(figsize=(6.5, 8.4))
    fig.text(.08, .955, f"Prepared patches by specimen: P{ids[0]:02d}-P{ids[-1]:02d}", fontsize=14, weight="bold", color=INK)
    fig.text(.08, .918, "Share within each specimen; n = prepared patches", fontsize=10.5, color=SECONDARY)
    handles = [Rectangle((0, 0), 1, 1, facecolor=COLORS[key]) for key in COLORS]
    fig.legend(handles, ["Candidate 1", "Candidate 0", "Unknown (-1)"], loc="upper left", bbox_to_anchor=(.07, .896),
               ncol=3, frameon=False, fontsize=10, handlelength=1.1, columnspacing=1.25)
    ax = fig.add_axes([.115, .160, .70, .675])
    y = np.arange(len(rows))
    left = np.zeros(len(rows))
    for key in COLORS:
        values = np.array([int(row[key]) for row in rows]) / totals * 100
        ax.barh(y, values, left=left, height=.86, color=COLORS[key], edgecolor="white", linewidth=.4, zorder=3)
        if key == "candidate_one":
            for yy, value in enumerate(values):
                if value >= 10:
                    ax.text(value / 2, yy, f"{value:.0f}%", color="white", fontsize=10, ha="center", va="center", zorder=4)
        left += values
    ax.set_yticks(y, [f"P{ident:02d}" for ident in ids], fontsize=10.5, color=INK)
    ax.invert_yaxis()
    ax.set_xlim(0, 100)
    ax.set_xticks([0, 25, 50, 75, 100], ["0%", "25%", "50%", "75%", "100%"])
    ax.tick_params(axis="x", labelsize=10, colors=SECONDARY, length=0, pad=6)
    ax.tick_params(axis="y", length=0, pad=5)
    ax.xaxis.grid(True, color=GRID, linewidth=.7, zorder=0)
    ax.set_xlabel("Share of each specimen's prepared patches", fontsize=10.5, color=SECONDARY, labelpad=10)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    for yy, count in enumerate(totals):
        ax.text(1.025, yy, f"n={count:,}", transform=ax.get_yaxis_transform(), ha="left", va="center", fontsize=10, color=SECONDARY, clip_on=False)
    caption(fig, "One build; nominal gauge-layer scope. All targets remain provisional.\nThe bars show patch composition, not specimen porosity.", y=.025)
    finish(fig, out / name)


def layer_plot(rows: list[dict], out: Path) -> None:
    x = np.array([int(row["layer"]) for row in rows])
    fig = plt.figure(figsize=(6.5, 4.65))
    fig.text(.08, .94, "Prepared source patches across 142 layers", fontsize=14, weight="bold", color=INK)
    fig.text(.08, .88, "64 specimens; candidate counts and total prepared patches per layer", fontsize=10.5, color=SECONDARY)
    ax = fig.add_axes([.145, .205, .805, .56])
    for key, label, style in (("candidate_one", "Candidate 1", "-"), ("candidate_zero", "Candidate 0", "-"),
                              ("candidate_unknown", "Unknown (-1)", "--"), ("rows", "Total", ":")):
        color = COLORS.get(key, INK)
        if key == "candidate_zero":
            color = "#798996"
        ax.plot(x, [int(row[key]) for row in rows], label=label, color=color, linestyle=style, linewidth=1.5)
    ax.set_xlim(x[0], x[-1])
    ax.set_ylim(0, max(int(row["rows"]) for row in rows) * 1.055)
    ax.set_xticks([519, 540, 560, 580, 600, 620, 640, 660])
    ax.tick_params(labelsize=10, colors=SECONDARY)
    ax.yaxis.set_major_formatter(FuncFormatter(lambda value, _: f"{value:,.0f}"))
    ax.set_xlabel("Source layer index", fontsize=10.5, color=SECONDARY, labelpad=8)
    ax.set_ylabel("Prepared patches", fontsize=10.5, color=SECONDARY, labelpad=7)
    ax.yaxis.grid(True, color=GRID, linewidth=.7)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(GRID)
    fig.legend(*ax.get_legend_handles_labels(), loc="upper center", bbox_to_anchor=(.54, .835), ncol=4,
               frameon=False, fontsize=10, columnspacing=1.0, handlelength=1.5)
    caption(fig, "One build; nominal gauge-layer scope. Candidate labels remain unvalidated.")
    finish(fig, out / FIGURES[3])


def workflow(summary: dict, out: Path) -> list[dict]:
    stages = [
        {"title": "Preserved raw input", "status": "Complete", "detail": "127.8 GB Snow HDF5; opened read-only", "color": COLORS["candidate_one"]},
        {"title": "Pilot checked", "status": "Complete", "detail": "2,024 patches; exact source reproduction", "color": COLORS["candidate_one"]},
        {"title": "Source sensor features prepared", "status": "Complete", "detail": f"{int(summary['rows']):,} patches; 64 specimens; 142 layers", "color": COLORS["candidate_one"]},
        {"title": "Physical target validation", "status": "Pending evidence", "detail": "Exact grid mapping, measured XCT support\nand justified target / quality policy", "color": COLORS["candidate_unknown"]},
        {"title": "Future ML baseline", "status": "Not started", "detail": "Whole-specimen evaluation after label review", "color": "#7D8994"},
    ]
    fig = plt.figure(figsize=(6.5, 7.25))
    fig.text(.08, .952, "FYP workflow and current checkpoint", fontsize=14, weight="bold", color=INK)
    fig.text(.08, .91, "Source sensor preparation is complete; target validation is pending.", fontsize=10.5, color=SECONDARY)
    ax = fig.add_axes([0, .07, 1, .80])
    ax.set_axis_off()
    y_positions = [.83, .65, .47, .29, .11]
    for index, (stage, y) in enumerate(zip(stages, y_positions)):
        ax.add_patch(FancyBboxPatch((.08, y), .84, .135, boxstyle="round,pad=0.008,rounding_size=0.012",
                                   facecolor="white", edgecolor="#CCD6DE", linewidth=1.0))
        ax.add_patch(Rectangle((.08, y), .012, .135, facecolor=stage["color"], edgecolor="none"))
        ax.text(.118, y+.096, f"{index+1}. {stage['title']}", fontsize=11.5, weight="bold", color=INK, va="center")
        ax.text(.88, y+.095, stage["status"], fontsize=10, color=stage["color"], ha="right", va="center")
        ax.text(.118, y+.045, stage["detail"], fontsize=10.5, color=SECONDARY, va="center", linespacing=1.3)
        if index < len(stages)-1:
            ax.add_patch(FancyArrowPatch((.5, y-.01), (.5, y_positions[index+1]+.145), arrowstyle="-|>",
                                         mutation_scale=13, linewidth=1.0, color="#9BAAB7"))
    caption(fig, "Prepared features support inspection. No final target y, model training\nor performance evaluation has been produced.", y=.025)
    finish(fig, out / FIGURES[4])
    return stages


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--replace", action="store_true", help="Replace only this script's named report assets while revising figures")
    args = parser.parse_args()
    root = args.root.resolve(strict=True)
    catalog = root / "data/cleaned/snow_source_preparation_v1/catalog"
    out = root / "reports/fyp_progress_2026-11-08/assets"
    out.mkdir(parents=True, exist_ok=True)
    for name in (*FIGURES, *DATA_FILES):
        if (out / name).exists() and not args.replace:
            raise FileExistsError(f"Existing figure asset is protected; use --replace for this script's own assets: {out / name}")
    summary = json.loads((catalog / "summary.json").read_text(encoding="utf-8"))
    specimens, layers = read_csv(catalog / "per_specimen.csv"), read_csv(catalog / "per_layer.csv")
    specimens.sort(key=lambda row: int(row["part_id"]))
    layers.sort(key=lambda row: int(row["layer"]))
    assert int(summary["rows"]) == sum(int(row["rows"]) for row in specimens) == sum(int(row["rows"]) for row in layers)
    assert len(specimens) == 64 and len(layers) == 142
    for key in COLORS:
        assert int(summary[key]) == sum(int(row[key]) for row in specimens) == sum(int(row[key]) for row in layers)
    assert int(summary["candidate_one"]) == 73649 and int(summary["candidate_zero"]) == 249631 and int(summary["candidate_unknown"]) == 6548
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10.5, "axes.titleweight": "bold", "axes.labelcolor": SECONDARY,
                         "figure.facecolor": "white", "savefig.facecolor": "white", "text.color": INK, "axes.unicode_minus": False})
    composition(summary, out)
    specimen_panel(specimens[:32], FIGURES[1], out)
    specimen_panel(specimens[32:], FIGURES[2], out)
    layer_plot(layers, out)
    stages = workflow(summary, out)
    (out / DATA_FILES[0]).write_text(json.dumps(summary, indent=2), encoding="utf-8")
    shutil.copyfile(catalog / "per_specimen.csv", out / DATA_FILES[1])
    shutil.copyfile(catalog / "per_layer.csv", out / DATA_FILES[2])
    evidence = {
        "source_files": [{"path": str(catalog / name), "sha256": sha(catalog / name)} for name in ("summary.json", "per_specimen.csv", "per_layer.csv")],
        "figures": list(FIGURES), "palette": COLORS, "width_inches": 6.5, "export_dpi": 300,
        "denominator": "All prepared patches, including unknown candidates; per-specimen bars use each specimen's prepared rows",
        "scientific_status": "All source candidate labels remain unvalidated; one build; nominal gauge-layer scope; no porosity or performance claim",
        "workflow_stages": stages, "script_sha256": sha(Path(__file__)),
    }
    (out / DATA_FILES[3]).write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    print(json.dumps({"assets": str(out), "figures": list(FIGURES)}, indent=2))


if __name__ == "__main__":
    main()
