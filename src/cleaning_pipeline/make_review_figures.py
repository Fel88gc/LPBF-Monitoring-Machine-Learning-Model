"""Create new, explicitly provisional figures matching the pilot crop policy."""
import argparse
import csv
from pathlib import Path
import h5py
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--run", type=Path, required=True)
    args = parser.parse_args()
    root, run = args.root.resolve(), args.run.resolve()
    if not run.is_relative_to(root / "results/data_quality"):
        raise ValueError("Run must stay inside project audit results")
    out = run / "spatial/review_figures"
    out.mkdir(exist_ok=False)
    with (run / "spatial/candidate_crop_comparison.csv").open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    selected = sorted([r for r in rows if int(r["part_id"]) == 16 and int(r["layer"]) == 600
                       and int(r["camera_x"]) == 1994 and int(r["camera_y"]) in (1997, 2021)],
                      key=lambda r: int(r["camera_y"]))
    if len(selected) != 2:
        raise ValueError("Expected two recorded P16 trace examples; refusing an incomplete figure")
    raw = root / "data/raw/2024-05-01 M2 AMMTO Fatigue Blanks 05.hdf5"
    fig, axes = plt.subplots(2, 5, figsize=(15, 7), layout="constrained")
    paths = ["/slices/camera_data/visible/0", "/slices/camera_data/visible/1", "/slices/camera_data/nir/1"]
    with h5py.File(raw, "r") as h5:
        for index, row in enumerate(selected):
            y, x, size = (int(row[key]) for key in ("camera_y", "camera_x", "patch_size"))
            y0, y1, x0, x1 = (int(row[f"pilot_round_{key}"]) for key in ("y0", "y1", "x0", "x1"))
            for channel, path in enumerate(paths):
                image = h5[path][600, y:y+size, x:x+size]
                axes[index, channel].imshow(image, origin="lower", cmap="gray" if channel < 2 else "inferno",
                                           vmin=0, vmax=255 if channel < 2 else 65535)
            ct = h5["/slices/registered_data/x-ray_ct_data"][600, y0:y1, x0:x1]
            flaw = h5["/slices/registered_data/x-ray_ct_flaw"][600, y0:y1, x0:x1]
            lo, hi = np.percentile(ct, [2, 98])
            axes[index, 3].imshow(ct, origin="lower", cmap="gray", vmin=lo, vmax=max(hi, lo+1))
            axes[index, 4].imshow(flaw != 0, origin="lower", cmap="binary", vmin=0, vmax=1)
            axes[index, 0].set_ylabel(f"Provisional label {row['original_label']}\nCamera Y={y}, X={x}")
            axes[index, 3].set_xlabel(f"XCT Y={y0}:{y1}\nX={x0}:{x1}")
            axes[index, 4].set_xlabel(f"Nonzero flaw pixels: {np.count_nonzero(flaw)}")
            for ax in axes[index]:
                ax.set_xticks([])
                ax.set_yticks([])
    for ax, title in zip(axes[0], ["Visible post-melt", "Visible post-recoat", "NIR integrated max", "XCT grayscale", "XCT annotation mask"]):
        ax.set_title(title)
    fig.suptitle("P16, layer 600 — original pilot_round crops reproduced\nProvisional correspondence; physical mapping and measured coverage remain unvalidated", fontsize=13)
    fig.savefig(out / "slide6_provisional_pilot_round.png", dpi=180, facecolor="white")
    plt.close(fig)
    changed = [r for r in rows if int(r["crop_label_disagreement"])]
    fig, ax = plt.subplots(figsize=(11, 5.3), layout="constrained")
    positions = np.arange(len(changed))
    width = 0.24
    for offset, method, color, hatch in [(-1, "pilot_round", "#1864ab", ""), (0, "audit_floor_ceil", "#d17b00", "//"), (1, "export_floor", "#868e96", "..")]:
        bars = ax.bar(positions + offset*width, [int(r[f"{method}_flaw_pixels"]) for r in changed],
                      width, color=color, edgecolor="black", linewidth=.5, hatch=hatch, label=method)
        ax.bar_label(bars, padding=3, fontsize=10)
    ax.set_xticks(positions, [f"P{r['part_id']} / L{r['layer']}\nrow {r['pilot_row']}" for r in changed])
    ax.set_ylabel("Nonzero XCT annotation pixels in crop")
    ax.set_ylim(0, 5.2)
    ax.set_title("Six patches cross the current >0 label boundary when cropping changes")
    ax.legend(loc="upper center", ncols=3, bbox_to_anchor=(.5, 1.0))
    ax.spines[['top', 'right']].set_visible(False)
    fig.savefig(out / "crop_sensitive_patches.png", dpi=180, facecolor="white")
    plt.close(fig)
    print(out)


if __name__ == "__main__":
    main()
