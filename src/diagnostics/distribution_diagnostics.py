"""Describe frozen development-only sensor features, without changing any model.

Normal curves and Q-Q lines are descriptive moment-matched references. No
normality hypothesis test, transformation, filtering, refit or test-feature
summary is performed. All candidate annotations remain provisional.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import platform
import time
from datetime import datetime, timezone
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import scipy
from scipy.stats import norm


CHANNELS = ("visible_melt", "visible_recoat", "nir_max")
CHANNEL_LABELS = ("Visible after melting", "Visible after recoating", "NIR integrated maximum")
STATISTICS = ("mean", "std", "min", "max", "p10", "median", "p90", "p99",
              "zero_fraction", "one_fraction", "mean_abs_dx", "mean_abs_dy", "gradient_rms", "entropy16")
EXPECTED_NAMES = [f"{channel}_{stat}" for channel in CHANNELS for stat in STATISTICS]
FIGURE_NAMES = [f"distribution_{name}.png" for name in
                ("channel_means", "shape_features", "normal_qq", "specimen_means", "variance_components")]
BLUE = "#2468A2"
GOLD = "#B87912"
DARK = "#33414E"
LIGHT_BLUE = "#97BDD9"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path, value):
    with Path(path).open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write("\n")


def write_csv(path, rows):
    require(bool(rows), f"No rows for {path}")
    with Path(path).open("x", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def describe(values):
    """Population moments, linear quantiles, exact endpoints and unique values."""
    values = np.asarray(values, dtype=np.float64)
    require(values.ndim == 1 and len(values) > 0 and np.isfinite(values).all(), "Invalid descriptive input")
    n = len(values)
    average = float(np.mean(values))
    variance = float(np.mean((values - average) ** 2))
    sd = float(np.sqrt(variance))
    quantiles = np.quantile(values, (0.01, 0.10, 0.50, 0.90, 0.99), method="linear")
    if sd:
        z = (values - average) / sd
        skewness, kurtosis = float(np.mean(z ** 3)), float(np.mean(z ** 4) - 3)
    else:
        skewness = kurtosis = None
    return {"n": n, "mean": average, "std_population": sd,
            "min": float(values.min()), "p01": float(quantiles[0]), "p10": float(quantiles[1]),
            "median": float(quantiles[2]), "p90": float(quantiles[3]), "p99": float(quantiles[4]),
            "max": float(values.max()), "skew_population": skewness,
            "excess_kurtosis_population": kurtosis,
            "zero_fraction": float(np.mean(values == 0)), "one_fraction": float(np.mean(values == 1)),
            "unique_values": int(len(np.unique(values)))}


def style():
    plt.rcParams.update({
        "font.family": "DejaVu Sans", "font.size": 10.5, "axes.titlesize": 12,
        "axes.labelsize": 10.5, "xtick.labelsize": 9, "ytick.labelsize": 9,
        "axes.spines.top": False, "axes.spines.right": False,
        "axes.edgecolor": "#89939B", "axes.linewidth": 0.8,
        "figure.facecolor": "white", "axes.facecolor": "white",
        "savefig.facecolor": "white", "grid.color": "#DCE2E7", "grid.linewidth": 0.6,
    })


def save_figure(fig, path):
    require(not path.exists(), f"Refusing to overwrite figure: {path}")
    fig.savefig(path, dpi=220, bbox_inches="tight", pad_inches=0.18)
    plt.close(fig)


def draw_histogram(ax, values, target, bins, normal_reference=False):
    for mask, label, color, width in (
        (np.ones(len(values), dtype=bool), "All development patches", DARK, 1.8),
        (target == 0, "Candidate 0", BLUE, 1.4),
        (target == 1, "Candidate 1", GOLD, 1.4),
    ):
        density, edges = np.histogram(values[mask], bins=bins, density=True)
        ax.stairs(density, edges, label=label, color=color, linewidth=width)
    if normal_reference:
        mu, sigma = float(values.mean()), float(values.std(ddof=0))
        if sigma:
            grid = np.linspace(bins[0], bins[-1], 600)
            ax.plot(grid, norm.pdf(grid, loc=mu, scale=sigma), linestyle="--", color="black",
                    linewidth=1.5, label="Normal reference (pooled moments)")
    ax.set_xlim(bins[0], bins[-1])
    ax.set_ylim(bottom=0)
    ax.grid(axis="y", alpha=0.7)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    args = parser.parse_args()
    run(args.root)


def run(root):
    started = time.perf_counter()
    root = Path(root).resolve()
    output = root / "results/development_diagnostics_v1_2026-11-08/distributions"
    assets = root / "reports/development_diagnostics_v1_2026-11-08/assets"
    require(not output.exists(), "Refusing existing distribution diagnostics")
    require(not any((assets / name).exists() for name in FIGURE_NAMES), "A distribution figure already exists")
    feature_dir = root / "data/features/baseline_v1_2026-11-08"
    protocol_dir = root / "results/baseline_v1_2026-11-08/protocol"
    protocol = load_json(protocol_dir / "protocol.json")
    feature_summary = load_json(feature_dir / "summary.json")
    frozen_hashes = load_json(protocol_dir / "artifact_hashes.json")
    verified_hashes = {}
    for directory, entries in ((protocol_dir, frozen_hashes),
                               (feature_dir, feature_summary["artifacts_sha256"])):
        for name, expected in entries.items():
            path = directory / name
            actual = sha256_file(path)
            require(actual == expected, f"Frozen source checksum mismatch: {path}")
            verified_hashes[path.relative_to(root).as_posix()] = actual
    feature_summary_hash = sha256_file(feature_dir / "summary.json")
    names = load_json(feature_dir / "feature_names.json")
    require(names == EXPECTED_NAMES == protocol["feature_names"], "Sensor-only feature names/order differ")
    metadata = pd.read_csv(feature_dir / "metadata.csv")
    target = np.load(feature_dir / "candidate_y.npy", allow_pickle=False)
    groups = np.load(feature_dir / "groups.npy", allow_pickle=False)
    rows = np.load(feature_dir / "catalog_row.npy", allow_pickle=False)
    with np.load(protocol_dir / "splits.npz", allow_pickle=False) as arrays:
        fold = arrays["fold_id"].copy()
        eligible = arrays["eligible"].copy()
        for name, actual in (("candidate_y", target), ("groups", groups), ("catalog_row", rows)):
            require(np.array_equal(arrays[name], actual), f"Frozen split alignment failed: {name}")
    require(np.array_equal(rows, np.arange(len(target))), "Noncanonical row order")
    for column, expected in (("catalog_row", rows), ("candidate_y", target), ("part_id", groups)):
        require(np.array_equal(metadata[column].to_numpy(), expected), f"Metadata row alignment failed: {column}")
    require((metadata.label_validated == 0).all() and (metadata.coverage_validated == 0).all(), "Source validation flags changed")
    require(np.array_equal(eligible, np.isin(target, (0, 1))), "Unknown eligibility differs")
    require(protocol["test_fold"] == 0 and protocol["development_folds"] == [1, 2, 3, 4], "Unexpected frozen split design")
    mask = eligible & (fold != 0)
    selected_rows = np.flatnonzero(mask)
    dev_groups = np.unique(groups[mask])
    excluded_test_groups = np.unique(groups[fold == 0])
    require(mask.sum() == 262369 and len(dev_groups) == 52 and len(excluded_test_groups) == 12, "Unexpected development scope")
    require(set(dev_groups).isdisjoint(excluded_test_groups), "Development/test group overlap")
    require(np.all(fold[selected_rows] != 0) and np.isin(target[selected_rows], (0, 1)).all(), "Wrong rows selected")
    features = np.load(feature_dir / "features.npy", mmap_mode="r", allow_pickle=False)
    require(features.shape == (329828, 42) and features.dtype == np.float32, "Feature array shape/dtype mismatch")
    # This is the only feature row selection. No fold-0 feature values enter any
    # statistic, plot, normal reference, Q-Q sample or finite/range summary.
    x = np.asarray(features[selected_rows], dtype=np.float64)
    y, g = target[selected_rows], groups[selected_rows]
    require(np.isfinite(x).all() and np.all((x >= 0) & (x <= 1)), "Selected features must be finite and in [0,1]")
    del features
    print(f"Frozen inputs verified; describing {len(x):,} eligible development rows / {len(dev_groups)} specimens only.", flush=True)
    output.mkdir(parents=True, exist_ok=False)
    assets.mkdir(parents=True, exist_ok=True)
    np.save(output / "development_mask.npy", mask, allow_pickle=False)
    np.save(output / "development_catalog_rows.npy", selected_rows, allow_pickle=False)
    pooled_rows, class_rows, specimen_rows, variance_rows = [], [], [], []
    for index, name in enumerate(names):
        values = x[:, index]
        pooled = describe(values)
        pooled_rows.append({"feature": name, **pooled})
        for candidate in (0, 1):
            class_rows.append({"feature": name, "candidate_y": candidate, **describe(values[y == candidate])})
        within, between = 0.0, 0.0
        for group in dev_groups:
            subset = values[g == group]
            part_stats = describe(subset)
            specimen_rows.append({"feature": name, "part_id": int(group), **part_stats})
            weight = len(subset) / len(values)
            within += weight * part_stats["std_population"] ** 2
            between += weight * (part_stats["mean"] - pooled["mean"]) ** 2
        total = pooled["std_population"] ** 2
        require(np.isclose(total, within + between, rtol=1e-10, atol=1e-14), f"Variance decomposition failed: {name}")
        variance_rows.append({"feature": name, "n": len(values), "specimens": len(dev_groups),
                              "total_variance_population": total, "weighted_within_specimen_variance": within,
                              "weighted_between_specimen_mean_variance": between,
                              "within_fraction": within / total if total else None,
                              "between_fraction": between / total if total else None,
                              "additive_residual": total - within - between})
    write_csv(output / "feature_summary.csv", pooled_rows)
    write_csv(output / "feature_by_candidate.csv", class_rows)
    write_csv(output / "feature_by_specimen.csv", specimen_rows)
    write_csv(output / "variance_decomposition.csv", variance_rows)
    print("42 pooled, 84 candidate-class and 2,184 specimen feature summaries complete.", flush=True)

    # The same 200 evenly spaced eligible rows from each development specimen
    # are used for all three Q-Q plots. This is systematic group-balanced display
    # sampling, not an IID sample, class balancing, inferential test or model fit.
    qq_local_indices, sample_records = [], []
    for group in dev_groups:
        local = np.flatnonzero(g == group)
        sample_positions = np.linspace(0, len(local) - 1, min(200, len(local)), dtype=np.int64)
        chosen = local[sample_positions]
        require(len(np.unique(chosen)) == len(chosen), "Q-Q sample repeats a row")
        qq_local_indices.extend(chosen.tolist())
        for position, local_index in zip(sample_positions, chosen):
            catalog_index = int(selected_rows[local_index])
            sample_records.append({"catalog_row": catalog_index, "sample_id": metadata.iloc[catalog_index].sample_id,
                                   "part_id": int(group), "candidate_y": int(y[local_index]),
                                   "fold_id": int(fold[catalog_index]), "layer": int(metadata.iloc[catalog_index].layer),
                                   "position_within_eligible_specimen": int(position), "eligible_rows_in_specimen": len(local)})
    qq_local_indices = np.asarray(qq_local_indices, dtype=np.int64)
    require(np.all(fold[selected_rows[qq_local_indices]] != 0), "Held-out rows reached Q-Q display")
    write_csv(output / "qq_sample_manifest.csv", sample_records)
    normal_refs, qq_rows, histogram_rows = [], [], []
    bins = np.linspace(0, 1, 81)
    for channel in range(3):
        index = channel * 14
        values = x[:, index]
        mu, sigma = float(values.mean()), float(values.std(ddof=0))
        require(sigma > 0, "A channel-mean normal reference is undefined")
        normal_refs.append({"feature": names[index], "population": "all_eligible_development_patches",
                            "n": len(values), "mean": mu, "std_population": sigma,
                            "normal_probability_outside_unit_interval": float(norm.cdf(0, mu, sigma) + norm.sf(1, mu, sigma))})
        qq_values = np.sort(x[qq_local_indices, index])
        qq_mu, qq_sigma = float(qq_values.mean()), float(qq_values.std(ddof=0))
        normal_refs.append({"feature": names[index], "population": "systematic_group_balanced_qq_subset",
                            "n": len(qq_values), "mean": qq_mu, "std_population": qq_sigma,
                            "normal_probability_outside_unit_interval": float(norm.cdf(0, qq_mu, qq_sigma) + norm.sf(1, qq_mu, qq_sigma))})
        p = (np.arange(len(qq_values), dtype=np.float64) + 0.5) / len(qq_values)
        theoretical = norm.ppf(p, loc=qq_mu, scale=qq_sigma)
        qq_rows.extend({"feature": names[index], "rank": i + 1, "plotting_probability": float(p[i]),
                        "normal_reference_quantile": float(theoretical[i]), "observed_subset_quantile": float(qq_values[i])}
                       for i in range(len(qq_values)))
        for candidate, subset in (("pooled", values), ("0", values[y == 0]), ("1", values[y == 1])):
            counts, edges = np.histogram(subset, bins=bins)
            require(int(counts.sum()) == len(subset), "Histogram does not reconcile")
            histogram_rows.extend({"feature": names[index], "candidate_y": candidate,
                                   "bin_index": i, "bin_left": float(edges[i]), "bin_right": float(edges[i + 1]),
                                   "last_bin_includes_right_edge": int(i == len(counts) - 1),
                                   "count": int(counts[i]), "population_n": len(subset),
                                   "density": float(counts[i] / len(subset) / (edges[i + 1] - edges[i]))}
                                  for i in range(len(counts)))
    write_csv(output / "normal_reference_moments.csv", normal_refs)
    write_csv(output / "qq_plot_values.csv", qq_rows)
    write_csv(output / "mean_histogram_bins.csv", histogram_rows)

    style()
    fig, axes = plt.subplots(1, 3, figsize=(14.5, 4.9))
    for channel, ax in enumerate(axes):
        values = x[:, channel * 14]
        draw_histogram(ax, values, y, bins, normal_reference=True)
        ax.set_title(CHANNEL_LABELS[channel])
        ax.set_xlabel("Patch mean intensity (stored normalized scale)")
    axes[0].set_ylabel("Density within each displayed population")
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=4, frameon=False, bbox_to_anchor=(0.5, 0.91), fontsize=9)
    fig.suptitle("Development sensor means: pooled and provisional candidate classes", fontsize=14, y=1.01)
    fig.text(0.5, -0.025, "262,369 patches; 52 specimens. Each histogram integrates to 1. Normal curves use pooled moments, are untruncated, and are descriptive only.", ha="center", fontsize=9)
    fig.tight_layout(rect=(0, 0.02, 1, 0.87))
    save_figure(fig, assets / FIGURE_NAMES[0])

    fig, axes = plt.subplots(3, 3, figsize=(14.5, 10))
    for row_index, (offset, label, maximum) in enumerate(((1, "Population standard deviation", 0.5), (12, "Gradient RMS", 1), (13, "Normalized 16-bin entropy", 1))):
        for channel in range(3):
            ax = axes[row_index, channel]
            draw_histogram(ax, x[:, channel * 14 + offset], y, np.linspace(0, maximum, 81))
            ax.set_title(f"{CHANNEL_LABELS[channel]}\n{label}")
            ax.set_xlabel("Feature value")
            if channel == 0:
                ax.set_ylabel("Within-population density")
    fig.legend(*axes[0, 0].get_legend_handles_labels(), loc="upper center", ncol=3, frameon=False, bbox_to_anchor=(0.5, 0.97))
    fig.suptitle("Development texture summaries: spread, local differences and entropy", fontsize=14, y=1.01)
    fig.text(0.5, -0.018, "Candidate 0/1 are unvalidated annotations. All 262,369 development rows retained; no smoothing, outlier removal or distribution transformation.", ha="center", fontsize=9)
    fig.tight_layout(rect=(0, 0.01, 1, 0.94), h_pad=2)
    save_figure(fig, assets / FIGURE_NAMES[1])

    fig, axes = plt.subplots(1, 3, figsize=(14.5, 5.7))
    for channel, ax in enumerate(axes):
        values = np.sort(x[qq_local_indices, channel * 14])
        theoretical = norm.ppf((np.arange(len(values)) + 0.5) / len(values), loc=values.mean(), scale=values.std(ddof=0))
        limits = (min(float(values.min()), float(theoretical.min())), max(float(values.max()), float(theoretical.max())))
        ax.plot(theoretical, values, color=BLUE, linewidth=1.3, label="Observed quantile")
        ax.plot(limits, limits, linestyle="--", color=DARK, linewidth=1.2, label="Normal-reference line")
        ax.set_xlim(limits)
        ax.set_ylim(limits)
        ax.set_title(CHANNEL_LABELS[channel])
        ax.set_xlabel("Normal quantile (subset mean and SD)")
        ax.set_ylabel("Observed patch-mean quantile")
        ax.set_aspect("equal", adjustable="box")
        ax.grid(alpha=0.6)
    fig.legend(*axes[0].get_legend_handles_labels(), loc="upper center", ncol=2, frameon=False, bbox_to_anchor=(0.5, 0.91))
    fig.suptitle("Normal Q-Q references for development sensor means", fontsize=14, y=1.01)
    fig.text(0.5, 0.005, f"Same {len(qq_local_indices):,}-row display subset: 200 evenly spaced eligible rows per development specimen.\nEqual specimen weighting; no normality test or model assumption.", ha="center", fontsize=9, linespacing=1.5)
    fig.tight_layout(rect=(0, 0.12, 1, 0.87))
    save_figure(fig, assets / FIGURE_NAMES[2])

    specimen_table = pd.DataFrame(specimen_rows)
    fig, axes = plt.subplots(1, 3, figsize=(13.7, 13.7), sharey=True)
    positions = np.arange(len(dev_groups))
    for channel, ax in enumerate(axes):
        table = specimen_table[specimen_table.feature == names[channel * 14]].set_index("part_id").loc[dev_groups]
        ax.hlines(positions, table.p10, table.p90, color=LIGHT_BLUE, linewidth=2, label="Within-specimen 10th-90th percentiles")
        ax.scatter(table["mean"], positions, color=BLUE, s=15, zorder=3, label="Specimen mean")
        ax.axvline(x[:, channel * 14].mean(), color=DARK, linestyle="--", linewidth=1.3, label="Pooled patch-weighted mean")
        ax.set_yticks(positions)
        ax.set_yticklabels([f"P{int(group):02d}" for group in dev_groups], fontsize=8.5)
        ax.invert_yaxis()
        ax.set_xlim(0, 1)
        ax.set_title(CHANNEL_LABELS[channel])
        ax.set_xlabel("Patch mean intensity (normalized scale)")
        ax.grid(axis="x", alpha=0.6)
    axes[0].set_ylabel("Development specimen ID")
    # hlines/scatter/axvline display distinct marks, independently of their color.
    fig.legend(*axes[0].get_legend_handles_labels(), loc="upper center", ncol=2, frameon=False, bbox_to_anchor=(0.5, 0.97))
    fig.suptitle("Development sensor means: within and between specimens", fontsize=14, y=1.008)
    fig.text(0.5, -0.006, "All 52 development specimens; all eligible candidate classes pooled within each specimen. Intervals describe observations, not confidence intervals.", ha="center", fontsize=9)
    fig.tight_layout(rect=(0, 0.015, 1, 0.94), w_pad=2)
    save_figure(fig, assets / FIGURE_NAMES[3])

    decomposition = pd.DataFrame(variance_rows).set_index("feature")
    chosen_names = [f"{channel}_{stat}" for channel in CHANNELS for stat in ("mean", "std", "gradient_rms", "entropy16")]
    chosen = decomposition.loc[chosen_names]
    fig, ax = plt.subplots(figsize=(12.8, 6.8))
    positions = np.arange(len(chosen))
    ax.barh(positions, chosen.within_fraction, color=BLUE, label="Within-specimen variation")
    ax.barh(positions, chosen.between_fraction, left=chosen.within_fraction, color=GOLD,
            label="Between-specimen mean variation", hatch="//", edgecolor="white", linewidth=0.3)
    ax.set_yticks(positions)
    ax.set_yticklabels([name.replace("visible_melt", "Visible melt").replace("visible_recoat", "Visible recoat").replace("nir_max", "NIR max").replace("_", " ") for name in chosen_names])
    ax.invert_yaxis()
    ax.set_xlim(0, 1)
    ax.set_xlabel("Fraction of total development feature variance (patch-weighted)")
    ax.set_xticks(np.linspace(0, 1, 6), [f"{n:.0%}" for n in np.linspace(0, 1, 6)])
    ax.grid(axis="x", alpha=0.5)
    ax.set_axisbelow(True)
    ax.legend(loc="upper center", bbox_to_anchor=(0.54, 1.13), ncol=2, frameon=False)
    fig.suptitle("Where development feature variation occurs", fontsize=14, y=1.005)
    fig.text(0.5, -0.008, "Exact population-variance decomposition across 52 specimens. This is descriptive; it does not identify a cause or measure flaw-prediction performance.", ha="center", fontsize=9)
    fig.tight_layout(rect=(0, 0.015, 1, 0.95))
    save_figure(fig, assets / FIGURE_NAMES[4])

    for name, expected in verified_hashes.items():
        require(sha256_file(root / name) == expected, f"Frozen input changed during diagnostics: {name}")
    require(sha256_file(feature_dir / "summary.json") == feature_summary_hash, "Feature summary changed")
    artifact_names = [path.name for path in output.iterdir() if path.is_file()]
    mask_hash = hashlib.sha256(mask.astype(np.uint8).tobytes()).hexdigest()
    summary = {
        "stage": "development_only_distribution_diagnostics_complete", "created_utc": datetime.now(timezone.utc).isoformat(),
        "script_sha256": sha256_file(Path(__file__)), "python_version": platform.python_version(),
        "numpy_version": np.__version__, "pandas_version": pd.__version__, "scipy_version": scipy.__version__,
        "matplotlib_version": matplotlib.__version__, "feature_names": names,
        "scope": "Frozen eligible candidate 0/1 rows in development folds 1,2,3,4 only; no fold-0 feature values summarized or plotted.",
        "mask_expression": "eligible & (fold_id != 0)", "mask_sha256_uint8_canonical_bytes": mask_hash,
        "rows": len(x), "features": x.shape[1], "specimens": len(dev_groups),
        "specimen_ids": dev_groups.tolist(), "excluded_test_specimen_ids": excluded_test_groups.tolist(),
        "candidate_counts": {str(candidate): int(np.count_nonzero(y == candidate)) for candidate in (0, 1)},
        "unknown_rows_in_development_excluded": int(np.count_nonzero((fold != 0) & ~eligible)),
        "all_unknown_rows_remain_unknown": True, "input_rows_relabelled_or_dropped": 0,
        "selected_feature_values_finite_and_in_unit_interval": True,
        "input_sha256": verified_hashes, "feature_summary_sha256": feature_summary_hash,
        "protocol_sha256": verified_hashes[(protocol_dir / "protocol.json").relative_to(root).as_posix()],
        "statistics": {"std": "Population (ddof=0)", "quantiles": "NumPy linear method",
                       "skew": "Third population central moment / population SD cubed; undefined for a constant feature",
                       "excess_kurtosis": "Fourth population central moment / population variance squared minus 3; undefined for a constant feature",
                       "endpoint_fractions": "Exact stored-feature equality to 0 and 1",
                       "unique_values": "Exact number of distinct stored float32 feature values",
                       "variance_decomposition": "Var(X) = sum(n_g/N * Var(X|g)) + sum(n_g/N * (mean_g - pooled_mean)^2), population definitions"},
        "normal_reference": {"purpose": "Descriptive comparison only; not a model input, data transformation or claim of Gaussianity",
                             "histogram_reference": "Untruncated normal PDF with the full eligible development feature's pooled mean and population SD; displayed over [0,1]",
                             "qq_reference": "Normal quantiles from the group-balanced descriptive subset's mean and population SD; plotting positions (rank - 0.5)/N",
                             "bounded_features": True, "normality_hypothesis_tests": False,
                             "correlation_note": "Related patches/layers within specimens are not IID; no normality p-values or confidence intervals are inferred"},
        "qq_subset": {"rows": len(qq_local_indices), "specimens": len(dev_groups), "maximum_rows_per_specimen": 200,
                      "selection": "np.linspace(0, eligible_rows_in_specimen-1, min(200,n), dtype=int64), in canonical catalog order",
                      "same_catalog_rows_all_features": True, "balanced_by_specimen": True, "balanced_by_candidate_class": False,
                      "representativeness": "Systematic equal-specimen descriptive display sample; not an IID random sample or exact patch-weighted population"},
        "normal_reference_moments": normal_refs,
        "model_training_or_refitting": False, "model_predictions_read": False,
        "test_feature_statistics_computed": False, "target_changes": False,
        "outlier_removal_or_feature_transforms": False, "source_files_written": False,
        "all_frozen_input_hashes_unchanged": True,
        "artifacts_sha256": {name: sha256_file(output / name) for name in sorted(artifact_names)},
        "figures_sha256": {name: sha256_file(assets / name) for name in FIGURE_NAMES},
        "elapsed_seconds": round(time.perf_counter() - started, 3),
    }
    write_json(output / "summary.json", summary)
    print(json.dumps({key: summary[key] for key in ("stage", "rows", "features", "specimens", "candidate_counts", "qq_subset", "elapsed_seconds")}, indent=2), flush=True)
    return summary


if __name__ == "__main__":
    main()
