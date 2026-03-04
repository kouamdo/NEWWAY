#!/usr/bin/env python3
"""Build ID-aware DROP_PHY -> DECISION timelines from scenario artifacts.

This script correlates PHY-drop events from *-MSG.csv with control decisions from
*-CTRL.csv via pkt_uid (packet UID). It produces:
  - event_timeline.csv: one row per DROP_PHY event with matched decision fields
  - summary.csv: aggregate quality/coverage metrics
  - decision_delay_scatter.png: delay from drop to decision over time
  - decision_type_counts.png: distribution of decision event types
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


DROP_TYPES = {"CAM_DROP_PHY", "CPM_DROP_PHY", "OTHER_DROP_PHY"}
REACTION_TYPES = {"cam_drop_reaction", "cpm_drop_reaction"}


def _read_csv(path: Path) -> pd.DataFrame:
    try:
        return pd.read_csv(path)
    except Exception:
        return pd.DataFrame()


def _to_num(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def _vehicle_from_path(path: Path) -> str:
    # Example: eva-veh8-MSG.csv -> veh8
    parts = path.stem.split("-")
    if len(parts) >= 2:
        return parts[-2]
    return "unknown"


def _iter_msg_ctrl_pairs(artifacts: Path, only_vehicle: str | None) -> Iterable[tuple[str, Path, Path]]:
    for msg_path in sorted(artifacts.glob("*-MSG.csv")):
        veh = _vehicle_from_path(msg_path)
        if only_vehicle is not None and veh != only_vehicle:
            continue
        ctrl_path = msg_path.with_name(msg_path.name.replace("-MSG.csv", "-CTRL.csv"))
        if ctrl_path.exists():
            yield veh, msg_path, ctrl_path


def _build_vehicle_timeline(vehicle_id: str, msg_path: Path, ctrl_path: Path) -> pd.DataFrame:
    msg = _read_csv(msg_path)
    ctrl = _read_csv(ctrl_path)
    if msg.empty:
        return pd.DataFrame()

    required_msg_cols = {"msg_type", "pkt_uid", "rx_t_s", "msg_seq", "tx_id", "rx_id"}
    if not required_msg_cols.issubset(set(msg.columns)):
        return pd.DataFrame()

    drops = msg[msg["msg_type"].astype(str).isin(DROP_TYPES)].copy()
    if drops.empty:
        return pd.DataFrame()

    drops["pkt_uid"] = drops["pkt_uid"].astype(str)
    drops["drop_time_s"] = _to_num(drops["rx_t_s"])
    drops["msg_seq"] = _to_num(drops["msg_seq"])
    drops["tx_id"] = _to_num(drops["tx_id"])
    drops["rx_id"] = _to_num(drops["rx_id"])
    drops = drops.dropna(subset=["drop_time_s", "pkt_uid"])
    if drops.empty:
        return pd.DataFrame()

    drops = drops.rename(columns={"msg_type": "drop_type"})
    drops = drops[
        ["pkt_uid", "drop_time_s", "drop_type", "msg_seq", "tx_id", "rx_id"]
    ].copy()

    if ctrl.empty or "pkt_uid" not in ctrl.columns:
        out = drops.copy()
        out["vehicle_id"] = vehicle_id
        out["decision_time_s"] = np.nan
        out["decision_event_type"] = "missing_decision"
        out["decision_delay_s"] = np.nan
        out["lane_before"] = np.nan
        out["lane_after"] = np.nan
        out["target_speed_mps"] = np.nan
        out["lane_change"] = False
        return out

    ctrl["pkt_uid"] = ctrl["pkt_uid"].astype(str)
    ctrl["decision_time_s"] = _to_num(ctrl.get("time_s"))
    ctrl["lane_before"] = _to_num(ctrl.get("lane_before"))
    ctrl["lane_after"] = _to_num(ctrl.get("lane_after"))
    ctrl["target_speed_mps"] = _to_num(ctrl.get("target_speed_mps"))
    ctrl["decision_event_type"] = ctrl.get("event_type", "unknown").astype(str)
    ctrl["priority"] = np.where(ctrl["decision_event_type"].isin(REACTION_TYPES), 0, 1)

    ctrl = ctrl.dropna(subset=["decision_time_s", "pkt_uid"])
    if ctrl.empty:
        out = drops.copy()
        out["vehicle_id"] = vehicle_id
        out["decision_time_s"] = np.nan
        out["decision_event_type"] = "missing_decision"
        out["decision_delay_s"] = np.nan
        out["lane_before"] = np.nan
        out["lane_after"] = np.nan
        out["target_speed_mps"] = np.nan
        out["lane_change"] = False
        return out

    ctrl = ctrl.sort_values(["decision_time_s", "priority"], ascending=[True, True])
    first_decision = ctrl.groupby("pkt_uid", as_index=False).first()
    first_decision = first_decision[
        ["pkt_uid", "decision_time_s", "decision_event_type", "lane_before", "lane_after", "target_speed_mps"]
    ].copy()

    out = drops.merge(first_decision, on="pkt_uid", how="left")
    out["vehicle_id"] = vehicle_id
    out["decision_event_type"] = out["decision_event_type"].fillna("missing_decision")
    out["decision_delay_s"] = out["decision_time_s"] - out["drop_time_s"]
    out["lane_change"] = (
        out["lane_before"].notna()
        & out["lane_after"].notna()
        & (out["lane_before"] >= 0)
        & (out["lane_after"] >= 0)
        & (out["lane_before"] != out["lane_after"])
    )
    return out


def _write_scatter(df: pd.DataFrame, out_png: Path) -> None:
    matched = df[df["decision_event_type"] != "missing_decision"].copy()
    if matched.empty:
        return

    fig, ax = plt.subplots(figsize=(11, 5))
    for etype, grp in matched.groupby("decision_event_type"):
        ax.scatter(grp["drop_time_s"], grp["decision_delay_s"], s=12, alpha=0.7, label=etype)
    ax.set_xlabel("Drop time [s]")
    ax.set_ylabel("Decision delay [s]")
    ax.set_title("DROP_PHY -> DECISION delay timeline (matched by pkt_uid)")
    ax.grid(alpha=0.25)
    ax.legend(fontsize=8, ncols=3)
    fig.tight_layout()
    fig.savefig(out_png, dpi=160)
    plt.close(fig)


def _write_counts(df: pd.DataFrame, out_png: Path) -> None:
    if df.empty:
        return

    counts = df["decision_event_type"].value_counts().sort_values(ascending=False)
    fig, ax = plt.subplots(figsize=(10, 4.5))
    counts.plot(kind="bar", ax=ax, color="#4c78a8")
    ax.set_xlabel("Decision event type")
    ax.set_ylabel("Count")
    ax.set_title("Decision event type distribution for DROP_PHY packets")
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(out_png, dpi=160)
    plt.close(fig)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build pkt_uid-aware drop->decision timelines")
    parser.add_argument("--run-dir", required=True, help="Scenario run directory (contains artifacts/)")
    parser.add_argument(
        "--out-dir",
        default="",
        help="Output directory (default: <run-dir>/artifacts/drop_decision_timeline)",
    )
    parser.add_argument("--vehicle-id", default="", help="Optional vehicle filter, e.g., veh8")
    args = parser.parse_args()

    run_dir = Path(args.run_dir).resolve()
    artifacts = run_dir / "artifacts"
    if not artifacts.exists():
        print(f"No artifacts dir: {artifacts}")
        return 1

    out_dir = Path(args.out_dir).resolve() if args.out_dir else (artifacts / "drop_decision_timeline")
    out_dir.mkdir(parents=True, exist_ok=True)

    only_vehicle = args.vehicle_id.strip() or None
    timelines: list[pd.DataFrame] = []
    vehicles_seen = set()
    for veh, msg_path, ctrl_path in _iter_msg_ctrl_pairs(artifacts, only_vehicle):
        vehicles_seen.add(veh)
        t = _build_vehicle_timeline(veh, msg_path, ctrl_path)
        if not t.empty:
            timelines.append(t)

    if not timelines:
        empty = pd.DataFrame(
            columns=[
                "vehicle_id",
                "pkt_uid",
                "drop_time_s",
                "drop_type",
                "msg_seq",
                "tx_id",
                "rx_id",
                "decision_time_s",
                "decision_event_type",
                "decision_delay_s",
                "lane_before",
                "lane_after",
                "target_speed_mps",
                "lane_change",
            ]
        )
        empty.to_csv(out_dir / "event_timeline.csv", index=False)
        pd.DataFrame(
            [
                {
                    "vehicles_scanned": len(vehicles_seen),
                    "total_drop_events": 0,
                    "matched_decision_events": 0,
                    "strict_match_ratio": np.nan,
                    "reaction_events": 0,
                    "no_action_events": 0,
                    "missing_decision_events": 0,
                    "lane_change_events": 0,
                    "median_decision_delay_s": np.nan,
                    "p95_decision_delay_s": np.nan,
                }
            ]
        ).to_csv(out_dir / "summary.csv", index=False)
        print(out_dir / "event_timeline.csv")
        print(out_dir / "summary.csv")
        return 0

    all_events = pd.concat(timelines, ignore_index=True)
    all_events = all_events.sort_values(["drop_time_s", "vehicle_id", "pkt_uid"], ascending=[True, True, True])
    all_events.to_csv(out_dir / "event_timeline.csv", index=False)

    matched_mask = all_events["decision_event_type"] != "missing_decision"
    matched = all_events[matched_mask]
    delays = matched["decision_delay_s"].dropna()
    summary = {
        "vehicles_scanned": int(all_events["vehicle_id"].nunique()),
        "total_drop_events": int(len(all_events)),
        "matched_decision_events": int(matched_mask.sum()),
        "strict_match_ratio": float(matched_mask.mean()) if len(all_events) > 0 else np.nan,
        "reaction_events": int(all_events["decision_event_type"].isin(REACTION_TYPES).sum()),
        "no_action_events": int((all_events["decision_event_type"] == "drop_decision_no_action").sum()),
        "missing_decision_events": int((all_events["decision_event_type"] == "missing_decision").sum()),
        "lane_change_events": int(all_events["lane_change"].sum()),
        "median_decision_delay_s": float(delays.median()) if not delays.empty else np.nan,
        "p95_decision_delay_s": float(delays.quantile(0.95)) if not delays.empty else np.nan,
    }
    pd.DataFrame([summary]).to_csv(out_dir / "summary.csv", index=False)

    _write_scatter(all_events, out_dir / "decision_delay_scatter.png")
    _write_counts(all_events, out_dir / "decision_type_counts.png")

    print(out_dir / "event_timeline.csv")
    print(out_dir / "summary.csv")
    print(out_dir / "decision_delay_scatter.png")
    print(out_dir / "decision_type_counts.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
