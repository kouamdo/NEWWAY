#!/usr/bin/env python3
"""
Thesis Sweep Plotter — generates publication-quality plots from experiment CSVs.

Usage:
  python thesis_plot_sweep.py --summary-csv <path> --out-dir <path> --experiment <name>

Supports all 5 thesis experiments with automatic column detection.
"""
import argparse
import csv
import os
import sys

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.ticker as mticker
    HAS_MPL = True
except ImportError:
    HAS_MPL = False


def read_csv(path):
    """Read CSV and return list of dicts with auto-converted numeric values."""
    rows = []
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            converted = {}
            for k, v in row.items():
                try:
                    converted[k] = float(v)
                except (ValueError, TypeError):
                    converted[k] = v
            rows.append(converted)
    return rows


def safe_vals(rows, key):
    """Extract numeric values for key, replacing N/A with None."""
    vals = []
    for r in rows:
        v = r.get(key)
        if v is None or v == "N/A" or v == "":
            vals.append(None)
        elif isinstance(v, (int, float)):
            vals.append(float(v))
        else:
            try:
                vals.append(float(v))
            except ValueError:
                vals.append(None)
    return vals


def plot_sweep(rows, x_key, x_label, out_dir, prefix):
    """Generate a multi-panel sweep plot: PRR, Latency, TTC, Collisions vs X."""
    if not HAS_MPL:
        print("matplotlib not available, skipping plots")
        return

    x = safe_vals(rows, x_key)
    prr = safe_vals(rows, "prr_percent")
    lat = safe_vals(rows, "avg_latency_ms")
    ttc = safe_vals(rows, "min_ttc_s")
    gap = safe_vals(rows, "min_gap_m")
    coll = safe_vals(rows, "collisions")
    r_ttc = safe_vals(rows, "risky_ttc_events") or safe_vals(rows, "risky_ttc")
    r_gap = safe_vals(rows, "risky_gap_events") or safe_vals(rows, "risky_gap")

    fig, axes = plt.subplots(2, 3, figsize=(18, 10))
    fig.suptitle(f"Thesis Experiment: {prefix}", fontsize=16, fontweight="bold")

    def plot_panel(ax, xv, yv, ylabel, color, marker="o"):
        valid = [(xi, yi) for xi, yi in zip(xv, yv) if xi is not None and yi is not None]
        if not valid:
            ax.text(0.5, 0.5, "No data", ha="center", va="center", transform=ax.transAxes)
            return
        xs, ys = zip(*valid)
        ax.plot(xs, ys, marker=marker, color=color, linewidth=2, markersize=8)
        ax.set_xlabel(x_label, fontsize=12)
        ax.set_ylabel(ylabel, fontsize=12)
        ax.grid(True, alpha=0.3)
        ax.tick_params(labelsize=10)

    plot_panel(axes[0, 0], x, prr, "PRR (%)", "#2196F3")
    axes[0, 0].set_title("Packet Reception Ratio", fontsize=13)
    if any(v is not None for v in prr):
        axes[0, 0].set_ylim(bottom=0)

    plot_panel(axes[0, 1], x, lat, "Latency (ms)", "#FF9800")
    axes[0, 1].set_title("Average Latency", fontsize=13)

    plot_panel(axes[0, 2], x, ttc, "Min TTC (s)", "#F44336")
    axes[0, 2].set_title("Minimum Time-to-Collision", fontsize=13)
    axes[0, 2].axhline(y=1.5, color="red", linestyle="--", alpha=0.5, label="Danger threshold")
    axes[0, 2].legend(fontsize=9)

    plot_panel(axes[1, 0], x, gap, "Min Gap (m)", "#4CAF50")
    axes[1, 0].set_title("Minimum Inter-Vehicle Gap", fontsize=13)
    axes[1, 0].axhline(y=2.0, color="red", linestyle="--", alpha=0.5, label="Danger threshold")
    axes[1, 0].legend(fontsize=9)

    plot_panel(axes[1, 1], x, coll, "Collisions", "#9C27B0", marker="s")
    axes[1, 1].set_title("Collision Count", fontsize=13)
    if any(v is not None for v in coll):
        axes[1, 1].yaxis.set_major_locator(mticker.MaxNLocator(integer=True))

    # Risky events combined
    plot_panel(axes[1, 2], x, r_ttc, "Events", "#E91E63", marker="^")
    if r_gap and any(v is not None for v in r_gap):
        valid_gap = [(xi, yi) for xi, yi in zip(x, r_gap) if xi is not None and yi is not None]
        if valid_gap:
            xs_g, ys_g = zip(*valid_gap)
            axes[1, 2].plot(xs_g, ys_g, marker="v", color="#00BCD4", linewidth=2, markersize=8, label="Risky gap")
    axes[1, 2].set_title("Risky Events (TTC & Gap)", fontsize=13)
    axes[1, 2].legend(["Risky TTC", "Risky gap"], fontsize=9)

    plt.tight_layout(rect=[0, 0, 1, 0.95])
    out_path = os.path.join(out_dir, f"{prefix}_sweep.png")
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Plot saved: {out_path}")


def plot_tech_comparison(rows, out_dir, prefix):
    """Special plot for experiment 5: grouped bar chart NR-V2X vs 802.11p."""
    if not HAS_MPL:
        return

    techs = sorted(set(r.get("technology", "") for r in rows))
    if len(techs) < 2:
        print("Not enough technologies for comparison plot, using standard sweep")
        return

    fig, axes = plt.subplots(1, 3, figsize=(18, 6))
    fig.suptitle("Technology Comparison: NR-V2X vs 802.11p", fontsize=16, fontweight="bold")

    colors = {"NR-V2X": "#2196F3", "80211p": "#FF9800", "nrv2x": "#2196F3"}
    metrics = [
        ("prr_percent", "PRR (%)", "Packet Reception Ratio"),
        ("min_ttc_s", "Min TTC (s)", "Minimum Time-to-Collision"),
        ("collisions", "Collisions", "Collision Count"),
    ]

    for idx, (metric_key, ylabel, title) in enumerate(metrics):
        ax = axes[idx]
        for tech in techs:
            tech_rows = [r for r in rows if r.get("technology") == tech]
            x = safe_vals(tech_rows, "loss_prob")
            y = safe_vals(tech_rows, metric_key)
            valid = [(xi, yi) for xi, yi in zip(x, y) if xi is not None and yi is not None]
            if valid:
                xs, ys = zip(*valid)
                c = colors.get(tech, "#666666")
                ax.plot(xs, ys, marker="o", color=c, linewidth=2, markersize=8, label=tech)
        ax.set_xlabel("Loss Probability", fontsize=12)
        ax.set_ylabel(ylabel, fontsize=12)
        ax.set_title(title, fontsize=13)
        ax.grid(True, alpha=0.3)
        ax.legend(fontsize=10)

    plt.tight_layout(rect=[0, 0, 1, 0.93])
    out_path = os.path.join(out_dir, f"{prefix}_comparison.png")
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Comparison plot saved: {out_path}")


def main():
    parser = argparse.ArgumentParser(description="Thesis sweep plotter")
    parser.add_argument("--summary-csv", required=True, help="Path to summary CSV")
    parser.add_argument("--out-dir", required=True, help="Output directory for plots")
    parser.add_argument("--experiment", required=True, help="Experiment name prefix")
    args = parser.parse_args()

    if not os.path.isfile(args.summary_csv):
        print(f"CSV not found: {args.summary_csv}")
        sys.exit(1)

    rows = read_csv(args.summary_csv)
    if not rows:
        print("No data rows in CSV")
        sys.exit(1)

    os.makedirs(args.out_dir, exist_ok=True)

    # Detect x-axis key
    headers = list(rows[0].keys())
    x_key = headers[0]  # First column is always the sweep variable

    x_labels = {
        "loss_prob": "Message Loss Probability",
        "txPower_dBm": "Transmit Power (dBm)",
        "mcs": "Modulation and Coding Scheme (MCS)",
        "numerology": "Numerology (μ)",
        "vehicle_count": "Number of Vehicles",
        "technology": "Technology",
    }
    x_label = x_labels.get(x_key, x_key)

    # Technology comparison needs special handling
    if "technology" in headers:
        plot_tech_comparison(rows, args.out_dir, args.experiment)
    else:
        plot_sweep(rows, x_key, x_label, args.out_dir, args.experiment)


if __name__ == "__main__":
    main()
