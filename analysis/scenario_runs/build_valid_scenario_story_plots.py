#!/usr/bin/env python3
"""Build under-the-hood story plots for the validated EVA bidirectional scenario."""

from __future__ import annotations

import argparse
import csv
import math
import re
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


def _to_float(value: str | None) -> float:
    try:
        return float(value)
    except Exception:
        return math.nan


def _to_int(value: str | None, default: int = -1) -> int:
    try:
        return int(float(value))
    except Exception:
        return default


def _lane_index(lane_id: str) -> int:
    if "_" not in lane_id:
        return -1
    tail = lane_id.rsplit("_", 1)[-1]
    return _to_int(tail, -1)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build story plots for valid EVA scenario")
    p.add_argument("--run-dir", required=True, help="Scenario run directory")
    p.add_argument(
        "--focus-vehicles",
        default="veh2,veh3,veh4,veh5",
        help="Comma-separated vehicle IDs to track",
    )
    p.add_argument("--netstate", default="", help="Override netstate XML path")
    p.add_argument("--collision-xml", default="", help="Override collision XML path")
    p.add_argument("--timeline-csv", default="", help="Override drop_decision timeline CSV path")
    p.add_argument("--out-dir", default="", help="Output directory (default: artifacts/valid_scenario_story)")
    return p.parse_args()


def parse_netstate(netstate: Path, focus: set[str]) -> dict[str, list[dict[str, float | str | int]]]:
    records: dict[str, list[dict[str, float | str | int]]] = defaultdict(list)

    for _, elem in ET.iterparse(netstate, events=("end",)):
        if elem.tag != "timestep":
            continue

        t_s = _to_float(elem.attrib.get("time"))
        for edge in elem.findall("edge"):
            edge_id = edge.attrib.get("id", "")
            for lane in edge.findall("lane"):
                lane_id = lane.attrib.get("id", "")
                lane_idx = _lane_index(lane_id)
                for veh in lane.findall("vehicle"):
                    vid = veh.attrib.get("id", "")
                    if vid not in focus:
                        continue
                    records[vid].append(
                        {
                            "time_s": t_s,
                            "edge_id": edge_id,
                            "lane_id": lane_id,
                            "lane_idx": lane_idx,
                            "lane_pos": _to_float(veh.attrib.get("pos")),
                            "speed": _to_float(veh.attrib.get("speed")),
                            "x": _to_float(veh.attrib.get("x")),
                            "y": _to_float(veh.attrib.get("y")),
                        }
                    )
        elem.clear()

    for vid in records:
        records[vid].sort(key=lambda r: float(r["time_s"]))

    return records


def write_vehicle_state_csv(records: dict[str, list[dict[str, float | str | int]]], out_csv: Path) -> None:
    with out_csv.open("w", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "time_s",
                "vehicle_id",
                "edge_id",
                "lane_id",
                "lane_idx",
                "lane_pos",
                "speed",
                "x",
                "y",
            ],
        )
        writer.writeheader()
        for vid, rows in sorted(records.items()):
            for row in rows:
                out = dict(row)
                out["vehicle_id"] = vid
                writer.writerow(out)


def parse_collisions(collision_xml: Path) -> list[dict[str, float | str]]:
    collisions: list[dict[str, float | str]] = []
    if not collision_xml.exists():
        return collisions
    root = ET.parse(collision_xml).getroot()
    for c in root.findall("collision"):
        collisions.append(
            {
                "time_s": _to_float(c.attrib.get("time")),
                "collider": c.attrib.get("collider", ""),
                "victim": c.attrib.get("victim", ""),
                "lane": c.attrib.get("lane", ""),
                "pos_m": _to_float(c.attrib.get("pos")),
                "collider_speed": _to_float(c.attrib.get("colliderSpeed")),
                "victim_speed": _to_float(c.attrib.get("victimSpeed")),
            }
        )
    return collisions


def read_ctrl_events(ctrl_csv: Path) -> list[dict[str, float | str | int]]:
    events: list[dict[str, float | str | int]] = []
    if not ctrl_csv.exists():
        return events
    with ctrl_csv.open(newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            events.append(
                {
                    "time_s": _to_float(row.get("time_s")),
                    "event_type": (row.get("event_type") or "").strip(),
                    "lane_before": _to_int(row.get("lane_before"), -1),
                    "lane_after": _to_int(row.get("lane_after"), -1),
                }
            )
    return events


def read_timeline_events(timeline_csv: Path, vehicle_id: str) -> list[dict[str, float | str]]:
    events: list[dict[str, float | str]] = []
    if not timeline_csv.exists():
        return events
    with timeline_csv.open(newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            vid = (row.get("vehicle_id") or row.get("rx_vehicle_id") or "").strip()
            if vid != vehicle_id:
                continue
            events.append(
                {
                    "drop_time_s": _to_float(row.get("drop_time_s")),
                    "drop_type": (row.get("drop_type") or "").strip(),
                    "decision_event_type": (row.get("decision_event_type") or "").strip(),
                }
            )
    return events


def _pair_series(
    records: dict[str, list[dict[str, float | str | int]]],
    rear_id: str,
    front_id: str,
) -> tuple[list[float], list[float], list[float]]:
    rear = records.get(rear_id, [])
    front = records.get(front_id, [])
    if not rear or not front:
        return [], [], []

    by_t_rear = {round(float(r["time_s"]), 2): r for r in rear}
    by_t_front = {round(float(r["time_s"]), 2): r for r in front}
    common = sorted(set(by_t_rear).intersection(by_t_front))

    times: list[float] = []
    gaps: list[float] = []
    ttcs: list[float] = []

    for t in common:
        rr = by_t_rear[t]
        ff = by_t_front[t]
        if rr["lane_id"] != ff["lane_id"]:
            continue
        gap = float(ff["lane_pos"]) - float(rr["lane_pos"])
        if not math.isfinite(gap) or gap <= 0:
            continue
        closing = float(rr["speed"]) - float(ff["speed"])
        ttc = gap / closing if closing > 0.1 else math.nan
        times.append(float(t))
        gaps.append(gap)
        ttcs.append(ttc)

    return times, gaps, ttcs


def _bin_counts(times: list[float], max_time: int) -> np.ndarray:
    counts = np.zeros(max_time + 1, dtype=float)
    for t in times:
        if not math.isfinite(t):
            continue
        idx = int(math.floor(t))
        if 0 <= idx <= max_time:
            counts[idx] += 1.0
    return counts


def _read_log_incident_time(log_path: Path) -> float:
    if not log_path.exists():
        return math.nan
    pattern = re.compile(r"INCIDENT-APPLIED,id=veh2,time_s=([0-9.]+)")
    with log_path.open() as f:
        for line in f:
            m = pattern.search(line)
            if m:
                return _to_float(m.group(1))
    return math.nan


def _first_lane_change_cam(events: list[dict[str, float | str | int]]) -> float:
    valid = [
        e["time_s"]
        for e in events
        if e["event_type"] == "cam_reaction"
        and int(e["lane_before"]) >= 0
        and int(e["lane_after"]) >= 0
        and int(e["lane_before"]) != int(e["lane_after"])
        and math.isfinite(float(e["time_s"]))
    ]
    if not valid:
        return math.nan
    return float(min(valid))


def main() -> int:
    args = parse_args()
    run_dir = Path(args.run_dir).resolve()
    artifacts = run_dir / "artifacts"
    if not artifacts.exists():
        raise FileNotFoundError(f"No artifacts dir: {artifacts}")

    out_dir = Path(args.out_dir).resolve() if args.out_dir else (artifacts / "valid_scenario_story")
    out_dir.mkdir(parents=True, exist_ok=True)

    focus = [v.strip() for v in args.focus_vehicles.split(",") if v.strip()]
    focus_set = set(focus)

    netstate = Path(args.netstate).resolve() if args.netstate else (artifacts / "eva-netstate.xml")
    collision_xml = Path(args.collision_xml).resolve() if args.collision_xml else (artifacts / "eva-collision.xml")
    timeline_csv = (
        Path(args.timeline_csv).resolve()
        if args.timeline_csv
        else (artifacts / "drop_decision_timeline" / "event_timeline.csv")
    )

    if not netstate.exists():
        raise FileNotFoundError(f"Missing netstate: {netstate}")

    records = parse_netstate(netstate, focus_set)

    vehicle_state_csv = out_dir / "vehicle_state_timeseries.csv"
    write_vehicle_state_csv(records, vehicle_state_csv)

    colors = {
        "veh2": "#d62728",
        "veh3": "#2ca02c",
        "veh4": "#9467bd",
        "veh5": "#1f77b4",
    }

    fig, ax = plt.subplots(2, 1, figsize=(12, 7), sharex=True)
    for vid in focus:
        rows = records.get(vid, [])
        if not rows:
            continue
        t = [float(r["time_s"]) for r in rows]
        speed = [float(r["speed"]) for r in rows]
        lane = [float(r["lane_idx"]) for r in rows]
        color = colors.get(vid)
        ax[0].plot(t, speed, label=vid, linewidth=1.6, color=color)
        ax[1].step(t, lane, where="post", label=vid, linewidth=1.4, color=color)

    ax[0].set_ylabel("Speed [m/s]")
    ax[0].set_title("SUMO under the hood: focus vehicle speeds")
    ax[0].grid(alpha=0.3)
    ax[0].legend(ncol=4, fontsize=9)

    ax[1].set_xlabel("Time [s]")
    ax[1].set_ylabel("Lane index")
    ax[1].set_title("SUMO under the hood: lane indices")
    ax[1].grid(alpha=0.3)
    ax[1].legend(ncol=4, fontsize=9)

    speed_lane_png = out_dir / "speed_lane_timeseries.png"
    fig.tight_layout()
    fig.savefig(speed_lane_png, dpi=170)
    plt.close(fig)

    collisions = parse_collisions(collision_xml)
    collision_times = [float(c["time_s"]) for c in collisions if math.isfinite(float(c["time_s"]))]

    t42, gap42, ttc42 = _pair_series(records, "veh4", "veh2")
    t54, gap54, ttc54 = _pair_series(records, "veh5", "veh4")

    fig, ax = plt.subplots(2, 1, figsize=(12, 7), sharex=True)
    if t42:
        ax[0].plot(t42, gap42, label="gap veh4->veh2", color="#9467bd")
    if t54:
        ax[0].plot(t54, gap54, label="gap veh5->veh4", color="#1f77b4")
    ax[0].axhline(2.0, linestyle="--", color="gray", linewidth=1.0, label="2 m threshold")
    for ct in collision_times:
        ax[0].axvline(ct, linestyle=":", color="#d62728", alpha=0.8)
    ax[0].set_ylabel("Gap [m]")
    ax[0].set_title("SUMO safety proxies: inter-vehicle gaps")
    ax[0].grid(alpha=0.3)
    ax[0].legend(fontsize=9)

    if t42:
        ax[1].plot(t42, ttc42, label="TTC veh4->veh2", color="#9467bd")
    if t54:
        ax[1].plot(t54, ttc54, label="TTC veh5->veh4", color="#1f77b4")
    ax[1].axhline(1.5, linestyle="--", color="gray", linewidth=1.0, label="1.5 s threshold")
    for ct in collision_times:
        ax[1].axvline(ct, linestyle=":", color="#d62728", alpha=0.8)
    ax[1].set_xlabel("Time [s]")
    ax[1].set_ylabel("TTC [s]")
    ax[1].set_title("SUMO safety proxies: TTC")
    ax[1].grid(alpha=0.3)
    ax[1].legend(fontsize=9)

    gap_ttc_png = out_dir / "gap_ttc_timeseries.png"
    fig.tight_layout()
    fig.savefig(gap_ttc_png, dpi=170)
    plt.close(fig)

    ctrl_veh3 = read_ctrl_events(artifacts / "eva-veh3-CTRL.csv")
    ctrl_veh4 = read_ctrl_events(artifacts / "eva-veh4-CTRL.csv")
    ctrl_veh5 = read_ctrl_events(artifacts / "eva-veh5-CTRL.csv")
    timeline_veh4 = read_timeline_events(timeline_csv, "veh4")

    no_action_veh4 = [
        float(e["time_s"]) for e in ctrl_veh4 if e["event_type"] == "drop_decision_no_action" and math.isfinite(float(e["time_s"]))
    ]
    lc_veh3 = [
        float(e["time_s"])
        for e in ctrl_veh3
        if e["event_type"] == "cam_reaction"
        and int(e["lane_before"]) >= 0
        and int(e["lane_after"]) >= 0
        and int(e["lane_before"]) != int(e["lane_after"])
        and math.isfinite(float(e["time_s"]))
    ]
    lc_veh5 = [
        float(e["time_s"])
        for e in ctrl_veh5
        if e["event_type"] == "cam_reaction"
        and int(e["lane_before"]) >= 0
        and int(e["lane_after"]) >= 0
        and int(e["lane_before"]) != int(e["lane_after"])
        and math.isfinite(float(e["time_s"]))
    ]
    drop_phy_veh4 = [
        float(e["drop_time_s"]) for e in timeline_veh4 if math.isfinite(float(e["drop_time_s"])) and e["drop_type"].endswith("DROP_PHY")
    ]

    max_time = 0
    for seq in (no_action_veh4, lc_veh3, lc_veh5, drop_phy_veh4):
        if seq:
            max_time = max(max_time, int(math.ceil(max(seq))))

    t_axis = np.arange(0, max_time + 1)
    fig, ax = plt.subplots(1, 1, figsize=(12, 4.2))
    if len(t_axis) > 0:
        ax.step(t_axis, _bin_counts(drop_phy_veh4, max_time), where="post", label="veh4 DROP_PHY / sec", color="#7f7f7f")
        ax.step(t_axis, _bin_counts(no_action_veh4, max_time), where="post", label="veh4 no_action / sec", color="#9467bd")
        ax.step(t_axis, _bin_counts(lc_veh3, max_time), where="post", label="veh3 lane-change cam / sec", color="#2ca02c")
        ax.step(t_axis, _bin_counts(lc_veh5, max_time), where="post", label="veh5 lane-change cam / sec", color="#1f77b4")
    for ct in collision_times:
        ax.axvline(ct, linestyle=":", color="#d62728", alpha=0.8)
    ax.set_xlabel("Time [s]")
    ax.set_ylabel("Events per second")
    ax.set_title("ns-3 under the hood: packet drops and control decisions")
    ax.grid(alpha=0.3)
    ax.legend(fontsize=8, ncol=2)

    ns3_events_png = out_dir / "ns3_events_per_second.png"
    fig.tight_layout()
    fig.savefig(ns3_events_png, dpi=170)
    plt.close(fig)

    log_path = run_dir / "v2v-emergencyVehicleAlert-nrv2x.log"
    incident_time = _read_log_incident_time(log_path)
    veh3_lc_time = _first_lane_change_cam(ctrl_veh3)
    veh5_lc_time = _first_lane_change_cam(ctrl_veh5)

    collision_veh4_veh2 = math.nan
    for c in collisions:
        if c["collider"] == "veh4" and c["victim"] == "veh2":
            collision_veh4_veh2 = float(c["time_s"])
            break

    chain_rows = [
        {"event_name": "incident_applied_veh2", "time_s": incident_time, "evidence": "scenario log"},
        {"event_name": "veh3_first_lane_change", "time_s": veh3_lc_time, "evidence": "veh3 CTRL cam_reaction"},
        {"event_name": "collision_veh4_into_veh2", "time_s": collision_veh4_veh2, "evidence": "SUMO collision.xml"},
        {"event_name": "veh5_first_lane_change", "time_s": veh5_lc_time, "evidence": "veh5 CTRL cam_reaction"},
    ]

    finite_rows = [r for r in chain_rows if math.isfinite(float(r["time_s"]))]
    finite_rows.sort(key=lambda r: float(r["time_s"]))
    for i, row in enumerate(finite_rows, start=1):
        row["event_order"] = i

    chain_csv = out_dir / "event_chain.csv"
    with chain_csv.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["event_order", "event_name", "time_s", "evidence"])
        writer.writeheader()
        for row in finite_rows:
            writer.writerow(row)

    fig, ax = plt.subplots(1, 1, figsize=(12, 2.7))
    if finite_rows:
        times = [float(r["time_s"]) for r in finite_rows]
        labels = [str(r["event_name"]) for r in finite_rows]
        ax.scatter(times, np.zeros(len(times)), color="#d62728", s=55)
        for t_s, label in zip(times, labels):
            ax.text(t_s, 0.05, label, rotation=25, ha="left", va="bottom", fontsize=9)
    ax.set_yticks([])
    ax.set_xlabel("Time [s]")
    ax.set_title("Story timeline: incident -> lane change -> collision -> lane change")
    ax.grid(axis="x", alpha=0.3)

    chain_png = out_dir / "event_chain_timeline.png"
    fig.tight_layout()
    fig.savefig(chain_png, dpi=170)
    plt.close(fig)

    print(vehicle_state_csv)
    print(speed_lane_png)
    print(gap_ttc_png)
    print(ns3_events_png)
    print(chain_csv)
    print(chain_png)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
