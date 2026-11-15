"""Plot completed exploratory baselines against provisional candidate labels.

No training or raw HDF5 reads. A completed run and frozen pre-holdout selection
are required. The optional gallery reads only selected prepared sensor shards.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import Normalize
from matplotlib.cm import ScalarMappable
import numpy as np
import pandas as pd
from sklearn.metrics import precision_recall_curve


METHODS = ["dummy_prior", "logistic_combined", "random_forest_combined", "logistic_visible", "logistic_nir"]
SHORT = {"dummy_prior": "Prior-only\ndummy", "logistic_combined": "Logistic\n3 channels",
         "random_forest_combined": "Random forest\n3 channels", "logistic_visible": "Logistic\nvisible only", "logistic_nir": "Logistic\nNIR only"}
NAMES = {"dummy_prior": "Prior-only dummy", "logistic_combined": "Logistic: 3 channels",
         "random_forest_combined": "Random forest: 3 channels", "logistic_visible": "Logistic: visible only", "logistic_nir": "Logistic: NIR only"}
PALETTE = {"dummy_prior": "#7D8994", "logistic_combined": "#2464A1", "random_forest_combined": "#A16B16",
           "logistic_visible": "#6C7A2B", "logistic_nir": "#A35E7D"}
BLUE, GRAY, ORANGE, INK, SECONDARY, GRID = "#2464A1", "#7D8994", "#D98A2B", "#20313F", "#536474", "#E6EBEF"
FIGURES = ["model_ap_comparison.png", "heldout_precision_recall.png", "selected_primary_confusion.png",
           "selected_primary_per_specimen_ap.png", "selected_primary_error_gallery.png"]
DATA = ["model_comparison.csv", "selected_per_specimen_metrics.csv", "gallery_samples.csv", "gallery_selection.json", "plotting_sources.json"]


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def read_rows(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def number(value) -> float | None:
    if value is None or str(value).strip().lower() in {"", "none", "nan", "null"}:
        return None
    value = float(value)
    if not np.isfinite(value):
        raise ValueError("Nonfinite plotted metric")
    return value


def csv_out(path: Path, rows: list[dict], fields=None) -> None:
    if fields is None:
        fields = list(rows[0]) if rows else []
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def axes_style(ax) -> None:
    ax.set_axisbelow(True)
    ax.tick_params(labelsize=10, colors=SECONDARY)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(GRID)


def foot(fig, text: str, y=.025) -> None:
    fig.text(.075, y, text, fontsize=10, color=SECONDARY, va="bottom", linespacing=1.25)


def finish(fig, out: Path, name: str) -> None:
    fig.savefig(out / name, dpi=300, facecolor="white")
    plt.close(fig)


def compare_models(development: dict, test: dict, selected: str, out: Path) -> list[dict]:
    fig = plt.figure(figsize=(6.5, 4.4))
    fig.text(.075, .95, "Agreement with provisional candidate annotations", fontsize=14, weight="bold", color=INK)
    fig.text(.075, .89, "Four development folds; one final whole-specimen holdout", fontsize=10.5, color=SECONDARY)
    dev_ax = fig.add_axes([.30, .245, .275, .515])
    test_ax = fig.add_axes([.65, .245, .275, .515], sharey=dev_ax)
    rows = []
    for index, method in enumerate(METHODS):
        mean, sd, heldout = number(development[method]["mean_fold_ap"]), number(development[method]["std_fold_ap"]), number(test[method]["average_precision"])
        color = BLUE if method == selected else GRAY
        if mean is not None:
            dev_ax.errorbar(mean, index, xerr=sd or 0., fmt="D" if method == selected else "o", color=color,
                            markersize=6, capsize=3, linewidth=1.4)
        if heldout is not None:
            test_ax.plot(heldout, index, "D" if method == selected else "o", color=color, markersize=6)
            test_ax.text(heldout + .035 if heldout < .78 else heldout - .035, index - .19, f"{heldout:.3f}",
                         fontsize=10, ha="left" if heldout < .78 else "right", color=color)
        rows.append({"method": method, "selected_primary": method == selected, "development_mean_fold_ap": mean,
                     "development_fold_sd_population": sd, "heldout_pooled_ap": heldout,
                     "heldout_prevalence": number(test[method]["prevalence"])})
    prevalence = number(test[selected]["prevalence"])
    if prevalence is not None:
        test_ax.axvline(prevalence, color=ORANGE, linestyle="--", linewidth=1)
    dev_ax.set_yticks(range(len(METHODS)), [SHORT[method] for method in METHODS], fontsize=10)
    test_ax.tick_params(axis="y", left=False, labelleft=False)
    for ax, title in ((dev_ax, "Development\nmean fold AP +/- SD"), (test_ax, "Held-out specimens\npooled patch AP")):
        ax.set_title(title, fontsize=10.5, pad=10)
        ax.set_ylim(len(METHODS)-.5, -.5)
        ax.set_xlim(0, 1)
        ax.set_xticks([0, .5, 1])
        ax.set_xlabel("Average precision", fontsize=10)
        ax.xaxis.grid(True, color=GRID, linewidth=.7)
        axes_style(ax)
    foot(fig, "Blue diamond: primary selected using development folds only.\nError bars are fold SD, not confidence intervals. Dashed: holdout prevalence.")
    finish(fig, out, FIGURES[0])
    return rows


def precision_recall(predictions: pd.DataFrame, test: dict, selected: str, out: Path) -> None:
    y = predictions.candidate_y.to_numpy(dtype=np.uint8)
    fig = plt.figure(figsize=(6.5, 4.8))
    fig.text(.075, .95, "Held-out precision-recall: candidate targets", fontsize=14, weight="bold", color=INK)
    fig.text(.075, .89, "Curves from saved scores; all five methods were predeclared", fontsize=10.5, color=SECONDARY)
    ax = fig.add_axes([.12, .20, .83, .500])
    for method in METHODS:
        precision, recall, _ = precision_recall_curve(y, predictions[method].to_numpy(), drop_intermediate=True)
        ap = number(test[method]["average_precision"])
        label = f"{NAMES[method]} (AP {ap:.3f})" if ap is not None else f"{NAMES[method]} (AP undefined)"
        ax.step(recall, precision, where="post", color=PALETTE[method], linewidth=2.2 if method == selected else 1.25,
                linestyle=":" if method == "dummy_prior" else "-", label=label)
    prevalence = float(y.mean())
    ax.axhline(prevalence, color=INK, linewidth=1, linestyle="--", label=f"Holdout prevalence ({prevalence:.3f})")
    ax.set(xlim=(0, 1), ylim=(0, 1), xlabel="Recall of candidate 1", ylabel="Precision for candidate 1")
    axes_style(ax)
    fig.legend(*ax.get_legend_handles_labels(), loc="upper center", bbox_to_anchor=(.54, .855), ncol=2,
               frameon=False, fontsize=10, handlelength=1.65, columnspacing=1.0, labelspacing=.35)
    foot(fig, "Candidate-label agreement within one build; scores are not calibrated\nphysical-defect probabilities. Primary model was selected before this holdout.")
    finish(fig, out, FIGURES[1])


def confusion(test: dict, selected: str, threshold: float, out: Path) -> None:
    row = test[selected]
    counts = np.array([[int(row["tn"]), int(row["fp"])], [int(row["fn"]), int(row["tp"])]])
    totals = counts.sum(axis=1)
    shares = np.divide(counts, totals[:, None], out=np.zeros_like(counts, dtype=float), where=totals[:, None] != 0)
    fig = plt.figure(figsize=(6.5, 4.5))
    fig.text(.075, .95, "Selected primary: held-out confusion counts", fontsize=14, weight="bold", color=INK)
    fig.text(.075, .89, f"{NAMES[selected]} | fixed score threshold {threshold:g}", fontsize=10.5, color=SECONDARY)
    ax = fig.add_axes([.255, .255, .41, .54])
    im = ax.imshow(shares, vmin=0, vmax=1, cmap="Blues", interpolation="nearest")
    for yy in range(2):
        for xx in range(2):
            percent = f"{shares[yy, xx]:.1%}" if totals[yy] else "Undefined"
            ax.text(xx, yy, f"{counts[yy, xx]:,}\n{percent}", ha="center", va="center", fontsize=13,
                    color="white" if shares[yy, xx] >= .55 else INK)
    ax.set_xticks([0, 1], ["0", "1"], fontsize=11)
    ax.set_yticks([0, 1], ["0", "1"], fontsize=11)
    ax.set_xlabel("Predicted candidate", fontsize=10.5, labelpad=8)
    ax.set_ylabel("Reference candidate", fontsize=10.5, labelpad=9)
    ax.tick_params(length=0)
    colorbar_ax = fig.add_axes([.73, .255, .025, .54])
    colorbar = fig.colorbar(im, cax=colorbar_ax, ticks=[0, .5, 1])
    colorbar.ax.set_yticklabels(["0%", "50%", "100%"])
    colorbar.ax.tick_params(labelsize=10)
    colorbar.set_label("Share within reference-class row", fontsize=10)
    foot(fig, "Counts and row percentages use provisional references, not verified pores.\nThe threshold was fixed before holdout scoring; no holdout tuning was done.")
    finish(fig, out, FIGURES[2])


def specimen_plot(group_rows: list[dict], test: dict, selected: str, out: Path) -> list[dict]:
    rows = sorted([row for row in group_rows if row["method"] == selected], key=lambda row: int(row["part_id"]))
    if not rows:
        raise ValueError("Selected primary has no held-out specimen metrics")
    fig = plt.figure(figsize=(6.5, max(4.65, 1.7+.245*len(rows))))
    fig.text(.075, .95, "Selected primary: held-out specimen agreement", fontsize=14, weight="bold", color=INK)
    fig.text(.075, .89, f"{NAMES[selected]} | separate AP and candidate prevalence", fontsize=10.5, color=SECONDARY)
    ax = fig.add_axes([.265, .235, .67, .505])
    for index, row in enumerate(rows):
        prevalence, ap = number(row["prevalence"]), number(row["average_precision"])
        if ap is not None:
            ax.plot(ap, index, "o", color=BLUE, markersize=6, label="Specimen AP" if index == 0 else None)
        else:
            ax.text(.98, index, "AP undefined", ha="right", va="center", fontsize=10, color=SECONDARY)
        if prevalence is not None:
            ax.plot(prevalence, index, "s", markerfacecolor="white", markeredgecolor=GRAY, markersize=5.5,
                    label="Specimen prevalence" if index == 0 else None)
    pooled = number(test[selected]["average_precision"])
    if pooled is not None:
        ax.axvline(pooled, color=BLUE, linestyle="--", linewidth=1.2, label=f"Pooled patch AP ({pooled:.3f})")
    ax.set_yticks(range(len(rows)), [f"P{int(row['part_id']):02d} (n={int(row['n']):,})" for row in rows], fontsize=10)
    ax.set_ylim(len(rows)-.5, -.5)
    ax.set_xlim(0, 1)
    ax.set_xlabel("Average precision / candidate 1 prevalence", fontsize=10)
    ax.xaxis.grid(True, color=GRID, linewidth=.7)
    axes_style(ax)
    fig.legend(*ax.get_legend_handles_labels(), loc="upper center", bbox_to_anchor=(.55, .845), ncol=2,
               frameon=False, fontsize=10, labelspacing=.35)
    foot(fig, "Pooled patch agreement can hide weak within-specimen discrimination.\nAll reference labels remain provisional; no cross-build evidence is provided.")
    finish(fig, out, FIGURES[3])
    return rows


def gallery(predictions: pd.DataFrame, selected: str, threshold: float, metadata_path: Path,
            root: Path, out: Path) -> dict:
    frame = predictions.copy()
    frame["predicted_candidate"] = (frame[selected] >= threshold).astype(np.uint8)
    categories = [("TP", 1, 1, 1, False), ("TN", 0, 0, 1, True), ("FP", 0, 1, 2, False), ("FN", 1, 0, 2, True)]
    chosen, availability = [], []
    for label, reference, prediction, wanted, ascending in categories:
        subset = frame[(frame.candidate_y == reference) & (frame.predicted_candidate == prediction)]
        sample = subset.sort_values([selected, "sample_id"], ascending=[ascending, True], kind="stable").head(wanted)
        availability.append({"category": label, "available": int(len(subset)), "requested": wanted, "selected": int(len(sample))})
        for _, row in sample.iterrows():
            chosen.append({"category": label, "sample_id": str(row.sample_id), "catalog_row": int(row.catalog_row),
                           "part_id": int(row.part_id), "layer": int(row.layer), "camera_y": int(row.camera_y), "camera_x": int(row.camera_x),
                           "candidate_y": int(row.candidate_y), "predicted_candidate": int(row.predicted_candidate), "score": float(row[selected])})
    needed = {row["catalog_row"]: row for row in chosen}
    metadata = {}
    with metadata_path.open(newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            ident = int(row["catalog_row"])
            if ident in needed:
                expected = needed[ident]
                for field in ("sample_id", "part_id", "layer", "camera_y", "camera_x"):
                    if str(row[field]) != str(expected[field]):
                        raise ValueError(f"Gallery metadata disagrees for {expected['sample_id']}: {field}")
                metadata[ident] = row
                if len(metadata) == len(needed):
                    break
    if len(metadata) != len(needed):
        raise ValueError("Gallery selected samples are missing from prepared metadata")
    by_shard = defaultdict(list)
    for row in chosen:
        meta = metadata[row["catalog_row"]]
        row.update(feature_shard=meta["feature_shard"], feature_row=int(meta["feature_row"]))
        by_shard[row["feature_shard"]].append(row)
    images, source_hashes = {}, {}
    for shard_name, selections in by_shard.items():
        shard = (root / shard_name).resolve(strict=True)
        if not shard.is_relative_to(root / "data/cleaned") or shard.suffix != ".npz":
            raise ValueError("Gallery source must be a prepared feature shard")
        actual_hash = sha(shard)
        if actual_hash != read_json(shard.parent / "shard_provenance.json")["files_sha256"]["features.npz"]:
            raise ValueError(f"Gallery shard provenance failed: {shard}")
        source_hashes[shard_name] = actual_hash
        with np.load(shard, allow_pickle=False) as archive:
            X = archive["X"]
            if X.shape[1:] != (3, 24, 24):
                raise ValueError("Gallery expected three 24x24 prepared sensor channels")
            for row in selections:
                image = X[row["feature_row"]].copy()
                if not np.isfinite(image).all() or image.min() < 0 or image.max() > 1:
                    raise ValueError("Invalid gallery normalized image values")
                images[row["sample_id"]] = image
            del X
    if chosen:
        fig = plt.figure(figsize=(6.5, 8.0))
        fig.text(.06, .96, "Selected held-out agreements and disagreements", fontsize=13.5, weight="bold", color=INK)
        fig.text(.06, .915, f"{NAMES[selected]} | deterministic extreme-score examples", fontsize=10.5, color=SECONDARY)
        grid = fig.add_gridspec(len(chosen), 4, left=.06, right=.96, top=.855, bottom=.155,
                               width_ratios=[1.9, 1, 1, 1], wspace=.16, hspace=.20)
        image_axes = []
        for index, row in enumerate(chosen):
            label_ax = fig.add_subplot(grid[index, 0])
            label_ax.set_axis_off()
            label_ax.text(0, .85, f"{row['category']} | P{row['part_id']:02d} | L{row['layer']}", fontsize=10.5, weight="bold", va="top", color=INK)
            label_ax.text(0, .58, f"candidate={row['candidate_y']}; pred={row['predicted_candidate']}\nscore={row['score']:.3f}\nY={row['camera_y']}; X={row['camera_x']}",
                          fontsize=10, va="top", color=SECONDARY, linespacing=1.25)
            row_axes = []
            for channel in range(3):
                ax = fig.add_subplot(grid[index, channel+1])
                ax.imshow(images[row["sample_id"]][channel], cmap="inferno" if channel == 2 else "gray", vmin=0, vmax=1,
                          interpolation="nearest", origin="lower")
                ax.set_xticks([]); ax.set_yticks([])
                if index == 0:
                    ax.set_title(["Visible\npost-melt", "Visible\npost-recoat", "NIR\nintegrated max"][channel], fontsize=10, pad=8)
                row_axes.append(ax)
            image_axes.append(row_axes)
        first, second, nir = [ax.get_position() for ax in image_axes[-1]]
        for left, width, cmap in ((first.x0, second.x1-first.x0, "gray"), (nir.x0, nir.width, "inferno")):
            colorbar_ax = fig.add_axes([left, .085, width, .012])
            bar = fig.colorbar(ScalarMappable(norm=Normalize(0, 1), cmap=cmap), cax=colorbar_ax, orientation="horizontal", ticks=[0, 1])
            bar.ax.tick_params(labelsize=10, length=2)
        fig.text(.06, .088, "Stored 0-1 display", fontsize=10, color=SECONDARY)
        foot(fig, "Errors are relative to candidate annotations. Fixed display; no per-patch stretch.", y=.02)
        finish(fig, out, FIGURES[4])
    fields = ["category", "sample_id", "catalog_row", "part_id", "layer", "camera_y", "camera_x", "candidate_y", "predicted_candidate", "score", "feature_shard", "feature_row"]
    csv_out(out / "gallery_samples.csv", chosen, fields)
    record = {"selected_primary": selected, "threshold": threshold, "category_availability": availability,
              "selection_rule": "TP highest score 1; TN lowest score 1; FP highest score 2; FN lowest score 2; ties by sample_id ascending",
              "selection_status": "Descriptive extreme cases, not a random or representative sample; missing categories are not fabricated",
              "reference_status": "provisional candidate annotations; no physical-error claim", "prepared_shard_sha256": source_hashes,
              "display": "Fixed normalized range [0,1]; visible gray; NIR inferno; local array origin lower"}
    (out / "gallery_selection.json").write_text(json.dumps(record, indent=2, allow_nan=False), encoding="utf-8")
    return record


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--results", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--skip-gallery", action="store_true")
    parser.add_argument("--replace", action="store_true", help="Replace only this script's own named report assets")
    args = parser.parse_args()
    root = args.root.resolve(strict=True)
    training = (args.results or root / "results/baseline_v1_2026-11-08/training").resolve()
    out = (args.output or root / "reports/baseline_v1_2026-11-08/assets").resolve()
    if not training.is_relative_to(root / "results") or not out.is_relative_to(root / "reports"):
        raise ValueError("Use saved project results and a separate reports asset directory")
    record = read_json(training / "run_record.json")
    if record.get("status") != "complete":
        raise ValueError("Training is not complete; do not inspect partial holdout outputs")
    results = read_json(training / "results_summary.json")
    selection = read_json(training / "selection_before_holdout.json")
    if not selection.get("selected_before_holdout_scoring") or not record.get("all_input_hashes_unchanged"):
        raise ValueError("Frozen selection or input-preservation verification is missing")
    if record["selection_sha256"] != sha(training / "selection_before_holdout.json"):
        raise ValueError("Frozen selection checksum changed")
    selected = selection["selected_primary_method"]
    if selected != record["selected_primary_method"] or selected != results["selection"]["selected_primary_method"]:
        raise ValueError("Selected-primary metadata disagrees")
    if results["target_status"] != "provisional_candidates_exploratory":
        raise ValueError("Expected provisional candidate-label experiment")
    threshold = float(selection["decision_threshold"])
    development = {row["method"]: row for row in read_rows(training / "development_summary.csv")}
    test = {row["method"]: row for row in read_rows(training / "test_metrics.csv")}
    if set(development) != set(METHODS) or set(test) != set(METHODS):
        raise ValueError("Complete five-method results are required")
    predictions = pd.read_csv(training / "test_predictions.csv")
    if len(predictions) != int(record["test_rows"]) or not predictions.candidate_y.isin([0, 1]).all():
        raise ValueError("Holdout row count or target status mismatch")
    if not np.isfinite(predictions[METHODS].to_numpy()).all() or not (predictions.fold_id == 0).all():
        raise ValueError("Invalid held-out scores or fold assignment")
    for method in METHODS:
        if int(test[method]["n"]) != len(predictions) or not np.isclose(number(test[method]["prevalence"]), predictions.candidate_y.mean(), rtol=0, atol=1e-12):
            raise ValueError("Held-out plotted population disagrees with saved metrics")
        reference, predicted = predictions.candidate_y == 1, predictions[method] >= threshold
        counts = {"tn": int((~reference & ~predicted).sum()), "fp": int((~reference & predicted).sum()),
                  "fn": int((reference & ~predicted).sum()), "tp": int((reference & predicted).sum())}
        if any(count != int(test[method][name]) for name, count in counts.items()):
            raise ValueError("Saved-score thresholding disagrees with reported confusion counts")
    out.mkdir(parents=True, exist_ok=True)
    for name in FIGURES + DATA:
        if (out / name).exists() and not args.replace:
            raise FileExistsError(f"Existing plot asset protected: {out / name}")
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10.5, "text.color": INK, "axes.labelcolor": SECONDARY,
                         "figure.facecolor": "white", "savefig.facecolor": "white", "axes.unicode_minus": False})
    comparison = compare_models(development, test, selected, out)
    precision_recall(predictions, test, selected, out)
    confusion(test, selected, threshold, out)
    group_rows = specimen_plot(read_rows(training / "test_per_specimen.csv"), test, selected, out)
    csv_out(out / "model_comparison.csv", comparison)
    csv_out(out / "selected_per_specimen_metrics.csv", group_rows)
    gallery_record = None
    metadata = root / "data/features/baseline_v1_2026-11-08/metadata.csv"
    if not args.skip_gallery:
        gallery_record = gallery(predictions, selected, threshold, metadata, root, out)
    source_names = ["run_record.json", "results_summary.json", "selection_before_holdout.json", "development_summary.csv",
                    "test_metrics.csv", "test_predictions.csv", "test_per_specimen.csv"]
    sources = {"source_files": [{"path": str(training / name), "sha256": sha(training / name)} for name in source_names],
               "protocol_sha256": record["protocol_sha256"], "selected_primary": selected, "decision_threshold": threshold,
               "development_measure": "Unweighted mean of four fold AP values; SD uses ddof=0; variability, not a confidence interval",
               "heldout_measure": "Pooled patch average precision; a whole-specimen holdout from one build",
               "reference_status": "All supplied binary reference targets remain provisional and physically unvalidated",
               "prediction_interpretation": "Class-weighted model scores; not calibrated physical-defect probabilities",
               "gallery": gallery_record, "palette": PALETTE, "script_sha256": sha(Path(__file__)),
               "figures": [{"filename": name, "sha256": sha(out / name)} for name in FIGURES if (out / name).is_file()]}
    (out / "plotting_sources.json").write_text(json.dumps(sources, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps({"output": str(out), "selected_primary": selected, "figures": [name for name in FIGURES if (out / name).is_file()]}, indent=2))


if __name__ == "__main__":
    main()
