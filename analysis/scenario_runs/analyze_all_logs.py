#!/usr/bin/env python3
"""Repository-wide log audit for analysis/scenario_runs.

The script scans run directories, extracts key metrics, and writes:
  - CSV summary with per-run metrics
  - Markdown report with aggregated findings
"""

from __future__ import annotations

import argparse
import math
import re
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd


def _max_valid(a: float, b: float) -> float:
    if math.isnan(a):
        return b
    if math.isnan(b):
        return a
    return max(a, b)


def _parse_float(pattern: str, text: str) -> float:
    m = re.search(pattern, text)
    if not m:
        return math.nan
    try:
        return float(m.group(1))
    except ValueError:
        return math.nan


def _collect_run_dirs(root: Path) -> list[Path]:
    out: list[Path] = []
    for d in sorted(p for p in root.rglob("*") if p.is_dir()):
        has_log = any(d.glob("*.log"))
        has_artifacts_logs = (d / "artifacts").exists() and any((d / "artifacts").glob("*-MSG.csv"))
        if has_log or has_artifacts_logs:
            out.append(d)
    return out


def _safe_read_csv(path: Path, usecols: list[str] | None = None) -> pd.DataFrame:
    try:
        return pd.read_csv(path, usecols=usecols)
    except Exception:
        return pd.DataFrame()


def _eva_metrics(run_dir: Path) -> dict[str, float]:
    artifacts = run_dir / "artifacts"
    msg_files = sorted(artifacts.glob("*-MSG.csv"))
    ctrl_files = sorted(artifacts.glob("*-CTRL.csv"))
    if not msg_files and not ctrl_files:
        return {
            "eva_drop_phy_total": math.nan,
            "eva_cam_drop_phy": math.nan,
            "eva_cpm_drop_phy": math.nan,
            "eva_ctrl_events_total": math.nan,
            "eva_drop_decision_match_ratio": math.nan,
        }

    ctrl_total = 0
    ctrl_uids_by_vehicle: dict[str, set[str]] = {}
    for f in ctrl_files:
        veh = f.stem.split("-")[-2] if len(f.stem.split("-")) >= 2 else "unknown"
        df = _safe_read_csv(f, usecols=["pkt_uid"])
        if df.empty:
            continue
        ctrl_total += int(len(df))
        ctrl_uids_by_vehicle[veh] = set(df["pkt_uid"].astype(str).tolist())

    drop_phy_total = 0
    cam_drop_phy = 0
    cpm_drop_phy = 0
    matched = 0
    for f in msg_files:
        veh = f.stem.split("-")[-2] if len(f.stem.split("-")) >= 2 else "unknown"
        df = _safe_read_csv(f, usecols=["msg_type", "pkt_uid"])
        if df.empty:
            continue
        df["msg_type"] = df["msg_type"].astype(str)
        df["pkt_uid"] = df["pkt_uid"].astype(str)
        drops = df[df["msg_type"].isin(["CAM_DROP_PHY", "CPM_DROP_PHY", "OTHER_DROP_PHY"])]
        if drops.empty:
            continue
        cam_drop_phy += int((drops["msg_type"] == "CAM_DROP_PHY").sum())
        cpm_drop_phy += int((drops["msg_type"] == "CPM_DROP_PHY").sum())
        drop_phy_total += int(len(drops))
        ctrl_uids = ctrl_uids_by_vehicle.get(veh, set())
        matched += int(drops["pkt_uid"].isin(ctrl_uids).sum())

    ratio = float(matched / drop_phy_total) if drop_phy_total > 0 else math.nan
    return {
        "eva_drop_phy_total": float(drop_phy_total),
        "eva_cam_drop_phy": float(cam_drop_phy),
        "eva_cpm_drop_phy": float(cpm_drop_phy),
        "eva_ctrl_events_total": float(ctrl_total),
        "eva_drop_decision_match_ratio": ratio,
    }


def _summarize_run(run_dir: Path) -> dict[str, object]:
    logs = sorted(run_dir.glob("*.log"))
    csv_count = len(list(run_dir.rglob("*.csv")))
    png_count = len(list(run_dir.rglob("*.png")))

    avg_prr = math.nan
    avg_latency = math.nan
    incident_applied = 0
    sionna_enabled = False

    for log in logs:
        txt = log.read_text(errors="ignore")
        avg_prr = _max_valid(avg_prr, _parse_float(r"Average PRR:\s*([0-9.]+)", txt))
        avg_latency = _max_valid(avg_latency, _parse_float(r"Average latency \(ms\):\s*([0-9.]+)", txt))
        incident_applied += len(re.findall(r"INCIDENT-APPLIED", txt))
        if "sionna" in txt.lower():
            sionna_enabled = True

    scenario_guess = ",".join(sorted({p.stem for p in logs})) if logs else "no-top-level-log"
    in_export = "chatgpt_exports" in str(run_dir)
    out: dict[str, object] = {
        "run_dir": str(run_dir),
        "date_dir": run_dir.parts[-2] if len(run_dir.parts) >= 2 else "",
        "scenario_guess": scenario_guess,
        "log_files_top_level": len(logs),
        "csv_files_recursive": csv_count,
        "png_files_recursive": png_count,
        "avg_prr": avg_prr,
        "avg_latency_ms": avg_latency,
        "incident_applied_count": incident_applied,
        "sionna_mentioned": int(sionna_enabled),
        "in_chatgpt_exports": int(in_export),
    }
    out.update(_eva_metrics(run_dir))
    return out


def _build_markdown(df: pd.DataFrame, csv_path: Path) -> str:
    def _frame_to_markdown(frame: pd.DataFrame) -> str:
        if frame.empty:
            return "| n/a |\n| --- |\n| empty |"
        cols = list(frame.columns)
        lines_tbl = []
        lines_tbl.append("| " + " | ".join(cols) + " |")
        lines_tbl.append("| " + " | ".join(["---"] * len(cols)) + " |")
        for _, row in frame.iterrows():
            vals = []
            for c in cols:
                v = row[c]
                if isinstance(v, float) and math.isnan(v):
                    vals.append("nan")
                else:
                    vals.append(str(v))
            lines_tbl.append("| " + " | ".join(vals) + " |")
        return "\n".join(lines_tbl)

    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines: list[str] = []
    lines.append("# Log Audit Report")
    lines.append("")
    lines.append(f"- Generated: {ts}")
    lines.append(f"- Source rows: {len(df)}")
    lines.append(f"- CSV summary: `{csv_path}`")
    lines.append("")

    lines.append("## Global Totals")
    lines.append("")
    lines.append(f"- Total top-level log files: {int(df['log_files_top_level'].sum())}")
    lines.append(f"- Total recursive CSV files across runs: {int(df['csv_files_recursive'].sum())}")
    lines.append(f"- Total recursive PNG files across runs: {int(df['png_files_recursive'].sum())}")
    lines.append(f"- Runs with incident applied: {int((df['incident_applied_count'] > 0).sum())}")
    lines.append(f"- Runs mentioning Sionna: {int((df['sionna_mentioned'] > 0).sum())}")
    lines.append("")

    eva = df[df["eva_drop_phy_total"].notna()].copy()
    if not eva.empty:
        lines.append("## Emergency Scenario Coupling Quality")
        lines.append("")
        lines.append(f"- Runs with EVA artifacts: {len(eva)}")
        lines.append(f"- Total PHY drops (CAM+CPM+OTHER): {int(eva['eva_drop_phy_total'].sum())}")
        lines.append(f"- Total CAM PHY drops: {int(eva['eva_cam_drop_phy'].sum())}")
        lines.append(f"- Total CPM PHY drops: {int(eva['eva_cpm_drop_phy'].sum())}")
        valid_ratio = eva["eva_drop_decision_match_ratio"].dropna()
        if not valid_ratio.empty:
            lines.append(f"- Mean drop->decision match ratio: {valid_ratio.mean():.4f}")
            lines.append(f"- Min drop->decision match ratio: {valid_ratio.min():.4f}")
        lines.append("")

        top = eva[eva["eva_drop_phy_total"] > 0].sort_values("eva_drop_phy_total", ascending=False).head(10)[
            ["run_dir", "eva_drop_phy_total", "eva_drop_decision_match_ratio", "avg_prr", "avg_latency_ms"]
        ]
        lines.append("### Top 10 runs by PHY drops")
        lines.append("")
        lines.append(_frame_to_markdown(top))
        lines.append("")

    low_quality = df[df["eva_drop_decision_match_ratio"].notna() & (df["eva_drop_decision_match_ratio"] < 1.0)]
    lines.append("## Potential Issues")
    lines.append("")
    if low_quality.empty:
        lines.append("- No runs with drop->decision match ratio below 1.0 found in audited rows.")
    else:
        lines.append(f"- Runs with ratio < 1.0: {len(low_quality)}")
        lines.append(_frame_to_markdown(low_quality[["run_dir", "eva_drop_decision_match_ratio"]]))
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Scan and audit analysis/scenario_runs logs")
    parser.add_argument(
        "--root",
        default="analysis/scenario_runs",
        help="Root directory with scenario run folders",
    )
    parser.add_argument(
        "--out-dir",
        default="analysis/scenario_runs",
        help="Output directory for audit CSV/MD",
    )
    parser.add_argument(
        "--tag",
        default=datetime.now().strftime("%Y-%m-%d"),
        help="Suffix tag for output filenames",
    )
    args = parser.parse_args()

    root = Path(args.root).resolve()
    out_dir = Path(args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    if not root.exists():
        print(f"Root not found: {root}")
        return 1

    run_dirs = _collect_run_dirs(root)
    rows = [_summarize_run(d) for d in run_dirs]
    if not rows:
        print(f"No run directories found under {root}")
        return 1

    df = pd.DataFrame(rows).sort_values(["date_dir", "run_dir"], ascending=[True, True])
    csv_path = out_dir / f"log_audit_summary_{args.tag}.csv"
    md_path = out_dir / f"LOG_AUDIT_{args.tag}.md"
    df.to_csv(csv_path, index=False)
    md_path.write_text(_build_markdown(df, csv_path), encoding="utf-8")

    print(csv_path)
    print(md_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
