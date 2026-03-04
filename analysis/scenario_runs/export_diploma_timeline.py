#!/usr/bin/env python3
"""Export strict pkt_uid timelines for diploma-ready figures.

Produces a packet-centric timeline that explicitly links:
DROP_PHY -> DECISION -> ACTION(lane/speed)

Inputs:
  - run dir with artifacts/drop_decision_timeline/event_timeline.csv
  - or explicit --event-timeline-csv

Outputs:
  - packet_flow_timeline.csv: one row per packet flow (DROP->DECISION->ACTION)
  - event_timeline_long.csv: long-form stage rows for plotting/inspection
  - packet_flow_timeline.png: line per packet UID
  - summary.csv: aggregate counters for thesis text/tables
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D


REACTION_TYPES = {"cam_drop_reaction", "cpm_drop_reaction"}
NO_ACTION_TYPE = "drop_decision_no_action"
MISSING_TYPE = "missing_decision"


def _read_csv(path: Path) -> pd.DataFrame:
    try:
        return pd.read_csv(path)
    except Exception:
        return pd.DataFrame()


def _to_num(series: pd.Series | None) -> pd.Series:
    if series is None:
        return pd.Series(dtype="float64")
    return pd.to_numeric(series, errors="coerce")


def _parse_vehicle_ids(raw: str) -> set[str]:
    if not raw.strip():
        return set()
    return {v.strip() for v in raw.split(",") if v.strip()}


def _ensure_event_timeline(
    run_dir: Path,
    timeline_csv: Path,
    timeline_dir: Path,
    auto_build: bool,
) -> bool:
    if timeline_csv.exists():
        return True
    if not auto_build:
        return False

    root = Path(__file__).resolve().parents[2]
    build_script = root / "analysis/scenario_runs/build_drop_decision_timeline.py"
    if not build_script.exists():
        return False

    cmd = [
        sys.executable,
        str(build_script),
        "--run-dir",
        str(run_dir),
        "--out-dir",
        str(timeline_dir),
    ]
    rc = subprocess.run(cmd, check=False).returncode
    return rc == 0 and timeline_csv.exists()


def _classify_action(row: pd.Series) -> str:
    decision_type = str(row.get("decision_event_type", MISSING_TYPE))
    if decision_type == MISSING_TYPE:
        return "missing_action"
    if decision_type == NO_ACTION_TYPE:
        return "no_action"

    lane_before = row.get("lane_before", np.nan)
    lane_after = row.get("lane_after", np.nan)
    target_speed = row.get("target_speed_mps", np.nan)

    lane_change = (
        pd.notna(lane_before)
        and pd.notna(lane_after)
        and float(lane_before) >= 0
        and float(lane_after) >= 0
        and float(lane_before) != float(lane_after)
    )
    speed_change = pd.notna(target_speed) and float(target_speed) >= 0.0

    if lane_change and speed_change:
        return "lane_and_speed_change"
    if lane_change:
        return "lane_change_only"
    if speed_change:
        return "speed_change_only"
    return "decision_only"


def _build_packet_flows(df: pd.DataFrame, action_visual_offset_s: float) -> pd.DataFrame:
    out = df.copy()
    out["decision_event_type"] = out["decision_event_type"].fillna(MISSING_TYPE).astype(str)
    out["action_kind"] = out.apply(_classify_action, axis=1)
    out["has_decision"] = (
        out["decision_event_type"].ne(MISSING_TYPE) & out["decision_time_s"].notna()
    )
    out["action_time_raw_s"] = out["decision_time_s"]
    out["action_time_plot_s"] = out["decision_time_s"] + np.where(
        out["has_decision"], action_visual_offset_s, np.nan
    )
    out["packet_key"] = out.apply(
        lambda r: f"{r['vehicle_id']}|{r['pkt_uid']}|{int(r['msg_seq']) if pd.notna(r['msg_seq']) else -1}|{int(r['tx_id']) if pd.notna(r['tx_id']) else -1}|{int(r['rx_id']) if pd.notna(r['rx_id']) else -1}",
        axis=1,
    )
    return out


def _limit_packets(flows: pd.DataFrame, max_packets: int) -> pd.DataFrame:
    if max_packets <= 0 or len(flows) <= max_packets:
        return flows

    flows = flows.copy()
    flows["priority"] = np.where(
        flows["action_kind"].isin({"lane_and_speed_change", "lane_change_only", "speed_change_only"}),
        0,
        np.where(flows["decision_event_type"].isin(REACTION_TYPES), 1, 2),
    )
    flows = flows.sort_values(
        ["priority", "drop_time_s", "vehicle_id", "pkt_uid"],
        ascending=[True, True, True, True],
    ).head(max_packets)
    return flows.drop(columns=["priority"])


def _build_long_timeline(flows: pd.DataFrame) -> pd.DataFrame:
    records: list[dict[str, object]] = []

    base_cols = [
        "packet_key",
        "vehicle_id",
        "pkt_uid",
        "drop_type",
        "decision_event_type",
        "action_kind",
        "msg_seq",
        "tx_id",
        "rx_id",
        "lane_before",
        "lane_after",
        "target_speed_mps",
        "lane_change",
    ]

    for _, row in flows.iterrows():
        base = {k: row.get(k, np.nan) for k in base_cols}
        records.append(
            {
                **base,
                "stage": "DROP_PHY",
                "stage_time_s": row.get("drop_time_s", np.nan),
                "stage_time_plot_s": row.get("drop_time_s", np.nan),
            }
        )
        if bool(row.get("has_decision", False)):
            records.append(
                {
                    **base,
                    "stage": "DECISION",
                    "stage_time_s": row.get("decision_time_s", np.nan),
                    "stage_time_plot_s": row.get("decision_time_s", np.nan),
                }
            )
            records.append(
                {
                    **base,
                    "stage": "ACTION",
                    "stage_time_s": row.get("action_time_raw_s", np.nan),
                    "stage_time_plot_s": row.get("action_time_plot_s", np.nan),
                }
            )

    long_df = pd.DataFrame.from_records(records)
    if long_df.empty:
        return long_df
    return long_df.sort_values(["stage_time_plot_s", "vehicle_id", "pkt_uid"])


def _plot_flows(flows: pd.DataFrame, out_png: Path, annotate_n: int) -> None:
    if flows.empty:
        return

    plot_df = flows.sort_values(["drop_time_s", "vehicle_id", "pkt_uid"], ascending=[True, True, True]).copy()
    plot_df["packet_idx"] = np.arange(len(plot_df), dtype=int)

    action_colors = {
        "lane_and_speed_change": "#2ca02c",
        "lane_change_only": "#1f77b4",
        "speed_change_only": "#17becf",
        "decision_only": "#8c564b",
        "no_action": "#7f7f7f",
        "missing_action": "#d62728",
    }

    fig_h = min(max(5.0, 0.018 * len(plot_df)), 18.0)
    fig, ax = plt.subplots(figsize=(14, fig_h))

    for _, row in plot_df.iterrows():
        y = row["packet_idx"]
        drop_t = row["drop_time_s"]
        dec_t = row["decision_time_s"]
        act_t = row["action_time_plot_s"]
        action_kind = str(row["action_kind"])
        color = action_colors.get(action_kind, "#7f7f7f")

        ax.scatter([drop_t], [y], marker="x", s=20, color="#d62728", alpha=0.8)
        if pd.notna(dec_t):
            ax.plot([drop_t, dec_t], [y, y], color="#ff7f0e", alpha=0.55, linewidth=0.9)
            ax.scatter([dec_t], [y], marker="o", s=16, color="#1f77b4", alpha=0.8)

        if pd.notna(act_t):
            ax.plot([dec_t, act_t], [y, y], color=color, alpha=0.8, linewidth=1.2)
            ax.scatter([act_t], [y], marker="^", s=18, color=color, alpha=0.85)

    if annotate_n > 0:
        ann = plot_df[plot_df["action_kind"].ne("no_action")].head(annotate_n)
        for _, row in ann.iterrows():
            act_t = row["action_time_plot_s"] if pd.notna(row["action_time_plot_s"]) else row["drop_time_s"]
            text = f"{row['vehicle_id']}:{row['pkt_uid']} {row['action_kind']}"
            ax.text(float(act_t) + 0.002, int(row["packet_idx"]) + 0.1, text, fontsize=7, alpha=0.8)

    ax.set_xlabel("Time [s]")
    ax.set_ylabel("Packet flow index (ordered by drop time)")
    ax.set_title("Per-packet strict timeline: DROP_PHY -> DECISION -> ACTION")
    ax.grid(alpha=0.2)

    legend_items = [
        Line2D([0], [0], marker="x", linestyle="None", color="#d62728", label="DROP_PHY"),
        Line2D([0], [0], marker="o", linestyle="None", color="#1f77b4", label="DECISION"),
        Line2D([0], [0], marker="^", linestyle="None", color="#2ca02c", label="ACTION"),
        Line2D([0], [0], color="#ff7f0e", linewidth=1.0, label="DROP->DECISION"),
    ]
    ax.legend(handles=legend_items, fontsize=8, loc="upper right")

    fig.tight_layout()
    fig.savefig(out_png, dpi=180)
    plt.close(fig)


def main() -> int:
    parser = argparse.ArgumentParser(description="Export thesis-ready per-packet event timelines")
    parser.add_argument("--run-dir", required=True, help="Run directory containing artifacts/")
    parser.add_argument(
        "--out-dir",
        default="",
        help="Output directory (default: <run-dir>/artifacts/drop_decision_timeline_diploma)",
    )
    parser.add_argument(
        "--event-timeline-csv",
        default="",
        help="Optional explicit path to event_timeline.csv",
    )
    parser.add_argument(
        "--vehicle-ids",
        default="",
        help="Comma-separated vehicle IDs, e.g. veh8,veh10 (default: all)",
    )
    parser.add_argument(
        "--max-packets",
        type=int,
        default=1000,
        help="Limit number of packet lines in PNG/CSV (<=0 means all).",
    )
    parser.add_argument(
        "--annotate-n",
        type=int,
        default=30,
        help="Annotate first N non-no_action packet lines on PNG.",
    )
    parser.add_argument(
        "--action-visual-offset-ms",
        type=float,
        default=1.0,
        help="Visual offset (ms) between DECISION and ACTION markers.",
    )
    parser.add_argument(
        "--auto-build-timeline",
        type=int,
        default=1,
        help="Build event_timeline.csv automatically if it is missing (1/0).",
    )
    args = parser.parse_args()

    run_dir = Path(args.run_dir).resolve()
    if not run_dir.exists():
        print(f"Run dir not found: {run_dir}")
        return 1

    out_dir = Path(args.out_dir).resolve() if args.out_dir else (run_dir / "artifacts" / "drop_decision_timeline_diploma")
    out_dir.mkdir(parents=True, exist_ok=True)

    timeline_dir = run_dir / "artifacts" / "drop_decision_timeline"
    default_timeline_csv = timeline_dir / "event_timeline.csv"
    timeline_csv = Path(args.event_timeline_csv).resolve() if args.event_timeline_csv else default_timeline_csv
    if not _ensure_event_timeline(
        run_dir=run_dir,
        timeline_csv=timeline_csv,
        timeline_dir=timeline_dir,
        auto_build=bool(args.auto_build_timeline),
    ):
        print(f"event_timeline.csv is missing: {timeline_csv}")
        return 1

    timeline = _read_csv(timeline_csv)
    if timeline.empty:
        print(f"Timeline is empty: {timeline_csv}")
        return 1

    required_cols = {
        "vehicle_id",
        "pkt_uid",
        "drop_time_s",
        "drop_type",
        "decision_time_s",
        "decision_event_type",
        "lane_before",
        "lane_after",
        "target_speed_mps",
        "lane_change",
        "msg_seq",
        "tx_id",
        "rx_id",
    }
    if not required_cols.issubset(set(timeline.columns)):
        missing = sorted(required_cols - set(timeline.columns))
        print(f"Missing columns in timeline CSV: {missing}")
        return 1

    timeline["vehicle_id"] = timeline["vehicle_id"].astype(str)
    timeline["pkt_uid"] = timeline["pkt_uid"].astype(str)
    timeline["drop_time_s"] = _to_num(timeline["drop_time_s"])
    timeline["decision_time_s"] = _to_num(timeline["decision_time_s"])
    timeline["lane_before"] = _to_num(timeline["lane_before"])
    timeline["lane_after"] = _to_num(timeline["lane_after"])
    timeline["target_speed_mps"] = _to_num(timeline["target_speed_mps"])
    timeline["msg_seq"] = _to_num(timeline["msg_seq"])
    timeline["tx_id"] = _to_num(timeline["tx_id"])
    timeline["rx_id"] = _to_num(timeline["rx_id"])
    timeline["lane_change"] = timeline["lane_change"].fillna(False).astype(bool)

    vehicle_filter = _parse_vehicle_ids(args.vehicle_ids)
    if vehicle_filter:
        timeline = timeline[timeline["vehicle_id"].isin(vehicle_filter)].copy()
    timeline = timeline.dropna(subset=["drop_time_s", "pkt_uid", "vehicle_id"])
    if timeline.empty:
        print("No rows after filters.")
        return 1

    flows = _build_packet_flows(
        timeline.sort_values(["drop_time_s", "vehicle_id", "pkt_uid"]),
        action_visual_offset_s=max(0.0, args.action_visual_offset_ms) / 1000.0,
    )
    flows = _limit_packets(flows, max_packets=int(args.max_packets))
    flows = flows.sort_values(["drop_time_s", "vehicle_id", "pkt_uid"], ascending=[True, True, True])

    long_timeline = _build_long_timeline(flows)

    packet_flow_csv = out_dir / "packet_flow_timeline.csv"
    long_csv = out_dir / "event_timeline_long.csv"
    summary_csv = out_dir / "summary.csv"
    png_path = out_dir / "packet_flow_timeline.png"

    flows.to_csv(packet_flow_csv, index=False)
    long_timeline.to_csv(long_csv, index=False)

    summary = {
        "vehicles_included": int(flows["vehicle_id"].nunique()),
        "packets_included": int(len(flows)),
        "reaction_packets": int(flows["decision_event_type"].isin(REACTION_TYPES).sum()),
        "no_action_packets": int((flows["decision_event_type"] == NO_ACTION_TYPE).sum()),
        "missing_decision_packets": int((flows["decision_event_type"] == MISSING_TYPE).sum()),
        "lane_change_packets": int(flows["action_kind"].isin({"lane_and_speed_change", "lane_change_only"}).sum()),
        "speed_command_packets": int(
            flows["action_kind"].isin({"lane_and_speed_change", "speed_change_only"}).sum()
        ),
    }
    pd.DataFrame([summary]).to_csv(summary_csv, index=False)

    _plot_flows(flows, png_path, annotate_n=max(0, int(args.annotate_n)))

    print(packet_flow_csv)
    print(long_csv)
    print(summary_csv)
    print(png_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
