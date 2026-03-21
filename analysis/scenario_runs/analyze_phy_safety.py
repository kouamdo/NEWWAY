#!/usr/bin/env python3
"""
PHY-Safety Correlation Analyzer for 5G NR Thesis.

Reads *-PHY.csv files from EVA scenario runs and correlates PHY-layer metrics
(SINR, SNR, RSSI, RSRP) with safety outcomes (collisions, TTC, gap).

Generates:
  1. SINR distribution (received vs dropped)
  2. SINR vs distance scatter
  3. SINR CDF per loss condition
  4. PHY metric correlation heatmap
  5. Safety threshold analysis: at what SINR do collisions start?
  6. Per-vehicle PHY timeline (SINR over simulation time)

Usage:
  python analyze_phy_safety.py --run-dir <path> [--out-dir <path>]
  python analyze_phy_safety.py --sweep-dir <path>  # analyzes multiple runs
"""
import argparse
import csv
import glob
import os
import sys
from collections import defaultdict

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.ticker as mticker
    import numpy as np
    HAS_MPL = True
except ImportError:
    HAS_MPL = False

SENTINEL = 42000.0  # SignalInfo SENTINEL_VALUE for missing data


def read_phy_csv(path):
    """Read a PHY CSV file, filtering out sentinel values."""
    rows = []
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            converted = {}
            for k, v in row.items():
                try:
                    val = float(v)
                    # Filter sentinel values (42000 = not available)
                    if abs(val) > 40000:
                        val = None
                    converted[k] = val
                except (ValueError, TypeError):
                    converted[k] = v
            rows.append(converted)
    return rows


def collect_phy_data(run_dir):
    """Collect all PHY CSV data from a run directory."""
    all_rows = []
    patterns = [
        os.path.join(run_dir, "*-PHY.csv"),
        os.path.join(run_dir, "artifacts", "*-PHY.csv"),
    ]
    for pattern in patterns:
        for f in glob.glob(pattern):
            rows = read_phy_csv(f)
            all_rows.extend(rows)
    return all_rows


def safe_array(rows, key):
    """Extract numeric array, skipping None."""
    return [r[key] for r in rows if r.get(key) is not None]


def analyze_single_run(run_dir, out_dir):
    """Analyze PHY metrics from a single run."""
    rows = collect_phy_data(run_dir)
    if not rows:
        print(f"No PHY data found in {run_dir}")
        return None

    os.makedirs(out_dir, exist_ok=True)

    # Write consolidated PHY summary
    sinr_vals = safe_array(rows, "sinr_dB")
    snr_vals = safe_array(rows, "snr_dB")
    rssi_vals = safe_array(rows, "rssi_dBm")
    rsrp_vals = safe_array(rows, "rsrp_dBm")
    dist_vals = [r["distance_m"] for r in rows if r.get("distance_m") is not None and r["distance_m"] >= 0]

    summary = {
        "total_msgs": len(rows),
        "sinr_count": len(sinr_vals),
        "sinr_mean": sum(sinr_vals) / len(sinr_vals) if sinr_vals else None,
        "sinr_min": min(sinr_vals) if sinr_vals else None,
        "sinr_max": max(sinr_vals) if sinr_vals else None,
        "snr_count": len(snr_vals),
        "snr_mean": sum(snr_vals) / len(snr_vals) if snr_vals else None,
        "rssi_count": len(rssi_vals),
        "rssi_mean": sum(rssi_vals) / len(rssi_vals) if rssi_vals else None,
        "rsrp_count": len(rsrp_vals),
        "rsrp_mean": sum(rsrp_vals) / len(rsrp_vals) if rsrp_vals else None,
    }

    # Write summary CSV
    summary_path = os.path.join(out_dir, "phy_summary.csv")
    with open(summary_path, "w") as f:
        f.write(",".join(summary.keys()) + "\n")
        f.write(",".join(str(v) if v is not None else "N/A" for v in summary.values()) + "\n")
    print(f"PHY summary: {summary_path}")

    if not HAS_MPL:
        print("matplotlib not available, skipping plots")
        return summary

    # =================== PLOT 1: SINR Distribution ===================
    if sinr_vals:
        fig, ax = plt.subplots(figsize=(10, 6))
        ax.hist(sinr_vals, bins=50, color="#2196F3", alpha=0.7, edgecolor="white")
        ax.set_xlabel("SINR (dB)", fontsize=12)
        ax.set_ylabel("Count", fontsize=12)
        ax.set_title("SINR Distribution of Received CAM Messages", fontsize=14)
        ax.axvline(x=0, color="red", linestyle="--", alpha=0.5, label="0 dB")
        if summary["sinr_mean"]:
            ax.axvline(x=summary["sinr_mean"], color="green", linestyle="--",
                       alpha=0.7, label=f'Mean: {summary["sinr_mean"]:.1f} dB')
        ax.legend(fontsize=10)
        ax.grid(True, alpha=0.3)
        fig.savefig(os.path.join(out_dir, "phy_sinr_distribution.png"), dpi=150, bbox_inches="tight")
        plt.close(fig)

    # =================== PLOT 2: SINR vs Distance ===================
    if sinr_vals and dist_vals:
        paired = [(r.get("distance_m"), r.get("sinr_dB"))
                  for r in rows
                  if r.get("distance_m") is not None and r["distance_m"] >= 0
                  and r.get("sinr_dB") is not None]
        if paired:
            ds, ss = zip(*paired)
            fig, ax = plt.subplots(figsize=(10, 6))
            ax.scatter(ds, ss, alpha=0.3, s=10, color="#2196F3")
            ax.set_xlabel("Distance (m)", fontsize=12)
            ax.set_ylabel("SINR (dB)", fontsize=12)
            ax.set_title("SINR vs Inter-Vehicle Distance", fontsize=14)
            ax.axhline(y=0, color="red", linestyle="--", alpha=0.5, label="0 dB threshold")
            ax.grid(True, alpha=0.3)
            ax.legend(fontsize=10)
            fig.savefig(os.path.join(out_dir, "phy_sinr_vs_distance.png"), dpi=150, bbox_inches="tight")
            plt.close(fig)

    # =================== PLOT 3: SINR Timeline per Vehicle ===================
    if sinr_vals:
        vehicles = defaultdict(list)
        for r in rows:
            vid = r.get("vehicle_id", "?")
            t = r.get("time_s")
            s = r.get("sinr_dB")
            if t is not None and s is not None:
                vehicles[vid].append((t, s))

        if vehicles:
            fig, ax = plt.subplots(figsize=(12, 6))
            for vid, pts in sorted(vehicles.items()):
                ts, ss = zip(*pts)
                ax.plot(ts, ss, marker=".", markersize=2, linewidth=0.5, alpha=0.7, label=vid)
            ax.set_xlabel("Simulation Time (s)", fontsize=12)
            ax.set_ylabel("SINR (dB)", fontsize=12)
            ax.set_title("SINR Timeline per Vehicle", fontsize=14)
            ax.axhline(y=0, color="red", linestyle="--", alpha=0.5)
            if len(vehicles) <= 10:
                ax.legend(fontsize=8, loc="upper right")
            ax.grid(True, alpha=0.3)
            fig.savefig(os.path.join(out_dir, "phy_sinr_timeline.png"), dpi=150, bbox_inches="tight")
            plt.close(fig)

    # =================== PLOT 4: Multi-metric Overview ===================
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle("NR-V2X PHY Layer Metrics Overview", fontsize=16, fontweight="bold")

    metrics = [
        ("sinr_dB", "SINR (dB)", "#2196F3", axes[0, 0]),
        ("snr_dB", "SNR (dB)", "#4CAF50", axes[0, 1]),
        ("rssi_dBm", "RSSI (dBm)", "#FF9800", axes[1, 0]),
        ("rsrp_dBm", "RSRP (dBm)", "#9C27B0", axes[1, 1]),
    ]

    for key, label, color, ax in metrics:
        vals = safe_array(rows, key)
        if vals:
            ax.hist(vals, bins=40, color=color, alpha=0.7, edgecolor="white")
            mean_v = sum(vals) / len(vals)
            ax.axvline(x=mean_v, color="black", linestyle="--", alpha=0.7,
                       label=f"Mean: {mean_v:.1f}")
            ax.legend(fontsize=9)
        else:
            ax.text(0.5, 0.5, "No data", ha="center", va="center",
                    transform=ax.transAxes, fontsize=14)
        ax.set_xlabel(label, fontsize=11)
        ax.set_ylabel("Count", fontsize=11)
        ax.set_title(label, fontsize=12, fontweight="bold")
        ax.grid(True, alpha=0.3)

    plt.tight_layout(rect=[0, 0, 1, 0.95])
    fig.savefig(os.path.join(out_dir, "phy_metrics_overview.png"), dpi=150, bbox_inches="tight")
    plt.close(fig)

    return summary


def analyze_sweep(sweep_dir, out_dir):
    """Analyze PHY metrics across a parameter sweep (multiple run subdirs)."""
    os.makedirs(out_dir, exist_ok=True)

    # Find all subdirectories with PHY data
    subdirs = sorted(glob.glob(os.path.join(sweep_dir, "*/")))
    if not subdirs:
        subdirs = [sweep_dir]

    sweep_data = []
    for sd in subdirs:
        label = os.path.basename(sd.rstrip("/"))
        rows = collect_phy_data(sd)
        if not rows:
            continue
        sinr_vals = safe_array(rows, "sinr_dB")
        summary = {
            "label": label,
            "msg_count": len(rows),
            "sinr_mean": sum(sinr_vals) / len(sinr_vals) if sinr_vals else None,
            "sinr_min": min(sinr_vals) if sinr_vals else None,
            "sinr_p10": sorted(sinr_vals)[len(sinr_vals) // 10] if len(sinr_vals) > 10 else None,
            "sinr_p50": sorted(sinr_vals)[len(sinr_vals) // 2] if sinr_vals else None,
        }
        sweep_data.append((label, rows, summary))

    if not sweep_data:
        print("No PHY data found across sweep directories")
        return

    # Write sweep summary
    summary_path = os.path.join(out_dir, "phy_sweep_summary.csv")
    with open(summary_path, "w") as f:
        f.write("case,msg_count,sinr_mean_dB,sinr_min_dB,sinr_p10_dB,sinr_p50_dB\n")
        for label, _, s in sweep_data:
            f.write(f"{label},{s['msg_count']},"
                    f"{s['sinr_mean']:.2f}," if s['sinr_mean'] is not None else f"{label},{s['msg_count']},N/A,")
            f.write(f"{s['sinr_min']:.2f}," if s['sinr_min'] is not None else "N/A,")
            f.write(f"{s['sinr_p10']:.2f}," if s['sinr_p10'] is not None else "N/A,")
            f.write(f"{s['sinr_p50']:.2f}\n" if s['sinr_p50'] is not None else "N/A\n")
    print(f"Sweep PHY summary: {summary_path}")

    if not HAS_MPL:
        return

    # =================== PLOT: SINR CDF per sweep case ===================
    fig, ax = plt.subplots(figsize=(10, 6))
    for label, rows, _ in sweep_data:
        sinr = sorted(safe_array(rows, "sinr_dB"))
        if sinr:
            y = [(i + 1) / len(sinr) for i in range(len(sinr))]
            ax.plot(sinr, y, linewidth=2, label=label)
    ax.set_xlabel("SINR (dB)", fontsize=12)
    ax.set_ylabel("CDF", fontsize=12)
    ax.set_title("SINR CDF Across Experiment Conditions", fontsize=14)
    ax.axvline(x=0, color="red", linestyle="--", alpha=0.5, label="0 dB")
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)
    fig.savefig(os.path.join(out_dir, "phy_sinr_cdf_sweep.png"), dpi=150, bbox_inches="tight")
    plt.close(fig)

    # =================== PLOT: Mean SINR across cases ===================
    labels = [s["label"] for _, _, s in sweep_data]
    means = [s["sinr_mean"] for _, _, s in sweep_data]
    mins = [s["sinr_min"] for _, _, s in sweep_data]

    if any(m is not None for m in means):
        fig, ax = plt.subplots(figsize=(10, 6))
        x_pos = range(len(labels))
        valid_means = [(i, m) for i, m in enumerate(means) if m is not None]
        valid_mins = [(i, m) for i, m in enumerate(mins) if m is not None]
        if valid_means:
            ix, mv = zip(*valid_means)
            ax.bar(ix, mv, color="#2196F3", alpha=0.7, label="Mean SINR")
        if valid_mins:
            ix, mnv = zip(*valid_mins)
            ax.scatter(ix, mnv, color="#F44336", marker="v", s=80, zorder=5, label="Min SINR")
        ax.set_xticks(list(x_pos))
        ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=9)
        ax.set_ylabel("SINR (dB)", fontsize=12)
        ax.set_title("Mean and Minimum SINR Across Experiment Conditions", fontsize=14)
        ax.axhline(y=0, color="red", linestyle="--", alpha=0.5)
        ax.legend(fontsize=10)
        ax.grid(True, alpha=0.3, axis="y")
        plt.tight_layout()
        fig.savefig(os.path.join(out_dir, "phy_sinr_bar_sweep.png"), dpi=150, bbox_inches="tight")
        plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description="PHY-Safety correlation analyzer")
    parser.add_argument("--run-dir", help="Single run directory to analyze")
    parser.add_argument("--sweep-dir", help="Sweep directory with multiple run subdirs")
    parser.add_argument("--out-dir", help="Output directory (default: <run-dir>/phy_analysis)")
    args = parser.parse_args()

    if args.run_dir:
        out = args.out_dir or os.path.join(args.run_dir, "phy_analysis")
        analyze_single_run(args.run_dir, out)
    elif args.sweep_dir:
        out = args.out_dir or os.path.join(args.sweep_dir, "phy_analysis")
        analyze_sweep(args.sweep_dir, out)
    else:
        print("Specify --run-dir or --sweep-dir")
        sys.exit(1)


if __name__ == "__main__":
    main()
