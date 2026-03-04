#!/usr/bin/env python3
"""Build a causal report: packet drops/decisions around SUMO collisions.

Inputs per run:
  - artifacts/eva-collision.xml
  - artifacts/drop_decision_timeline/event_timeline.csv

Outputs:
  - artifacts/collision_causality/collision_causality.csv
  - artifacts/collision_causality/collision_causality.md
"""

from __future__ import annotations

import argparse
import math
import xml.etree.ElementTree as ET
from pathlib import Path

import pandas as pd


def _read_timeline(path: Path) -> pd.DataFrame:
    try:
        df = pd.read_csv(path)
    except Exception:
        return pd.DataFrame()
    required = {
        "vehicle_id",
        "pkt_uid",
        "drop_time_s",
        "drop_type",
        "decision_event_type",
        "decision_time_s",
        "msg_seq",
        "tx_id",
        "rx_id",
    }
    if not required.issubset(set(df.columns)):
        return pd.DataFrame()

    out = df.copy()
    out["vehicle_id"] = out["vehicle_id"].astype(str)
    out["pkt_uid"] = out["pkt_uid"].astype(str)
    out["drop_type"] = out["drop_type"].astype(str)
    out["decision_event_type"] = out["decision_event_type"].astype(str)
    for col in ["drop_time_s", "decision_time_s", "msg_seq", "tx_id", "rx_id"]:
        out[col] = pd.to_numeric(out[col], errors="coerce")
    out = out.dropna(subset=["drop_time_s", "vehicle_id"]).copy()
    return out


def _read_collisions(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    try:
        root = ET.parse(path).getroot()
    except Exception:
        return []

    rows: list[dict[str, object]] = []
    idx = 0
    for elem in root.iter("collision"):
        idx += 1
        time_s_raw = elem.attrib.get("time", "")
        try:
            time_s = float(time_s_raw)
        except Exception:
            time_s = math.nan
        rows.append(
            {
                "collision_index": idx,
                "collision_time_s": time_s,
                "collider": elem.attrib.get("collider", ""),
                "victim": elem.attrib.get("victim", ""),
                "lane": elem.attrib.get("lane", ""),
                "pos_m": elem.attrib.get("pos", ""),
                "type": elem.attrib.get("type", ""),
            }
        )
    return rows


def _last_row(df: pd.DataFrame) -> pd.Series | None:
    if df.empty:
        return None
    return df.sort_values("drop_time_s", ascending=True).iloc[-1]


def build_report(
    timeline: pd.DataFrame,
    collisions: list[dict[str, object]],
    window_s: float,
    focus_vehicle: str,
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []

    for c in collisions:
        t = c.get("collision_time_s", math.nan)
        collider = str(c.get("collider", ""))
        if not collider:
            continue
        if focus_vehicle and collider != focus_vehicle:
            continue
        if not isinstance(t, float) or math.isnan(t):
            continue

        before = timeline[
            (timeline["vehicle_id"] == collider)
            & (timeline["drop_time_s"] <= t)
            & (timeline["drop_time_s"] >= (t - window_s))
        ].copy()

        no_action = before[before["decision_event_type"] == "drop_decision_no_action"]
        reactions = before[
            before["decision_event_type"].isin(["cam_drop_reaction", "cpm_drop_reaction"])
        ]
        missing = before[before["decision_event_type"] == "missing_decision"]

        last_ev = _last_row(before)

        evidence = "weak"
        if len(no_action) >= 1 and len(reactions) == 0:
            evidence = "strong_no_action_only"
        elif len(no_action) >= 1 and len(reactions) >= 1:
            evidence = "mixed"
        elif len(before) == 0:
            evidence = "no_drop_events"

        rows.append(
            {
                "collision_index": c["collision_index"],
                "collision_time_s": t,
                "collider": collider,
                "victim": c.get("victim", ""),
                "lane": c.get("lane", ""),
                "pos_m": c.get("pos_m", ""),
                "type": c.get("type", ""),
                "window_s": window_s,
                "drop_events_window": int(len(before)),
                "no_action_events_window": int(len(no_action)),
                "drop_reaction_events_window": int(len(reactions)),
                "missing_decision_events_window": int(len(missing)),
                "last_drop_time_s": float(last_ev["drop_time_s"]) if last_ev is not None else math.nan,
                "last_drop_pkt_uid": str(last_ev["pkt_uid"]) if last_ev is not None else "",
                "last_drop_msg_seq": float(last_ev["msg_seq"]) if last_ev is not None else math.nan,
                "last_drop_tx_id": float(last_ev["tx_id"]) if last_ev is not None else math.nan,
                "last_decision_event_type": str(last_ev["decision_event_type"]) if last_ev is not None else "",
                "causal_evidence": evidence,
            }
        )

    return pd.DataFrame(rows)


def write_md(path: Path, df: pd.DataFrame, collision_xml: Path, timeline_csv: Path) -> None:
    lines: list[str] = []
    lines.append("# Collision Causality Report")
    lines.append("")
    lines.append(f"- collision XML: `{collision_xml}`")
    lines.append(f"- event timeline CSV: `{timeline_csv}`")
    lines.append("")

    if df.empty:
        lines.append("No collision rows were produced (no collisions or missing inputs).")
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return

    lines.append("## Summary")
    lines.append("")
    lines.append(f"- collisions analyzed: {len(df)}")
    lines.append(f"- strong_no_action_only: {(df['causal_evidence'] == 'strong_no_action_only').sum()}")
    lines.append(f"- mixed: {(df['causal_evidence'] == 'mixed').sum()}")
    lines.append(f"- weak/no_drop_events: {(~df['causal_evidence'].isin(['strong_no_action_only', 'mixed'])).sum()}")
    lines.append("")
    lines.append("## Rows")
    lines.append("")

    for _, r in df.sort_values(["collision_time_s", "collision_index"]).iterrows():
        lines.append(
            "- "
            f"t={r['collision_time_s']:.3f}s collider={r['collider']} victim={r['victim']} "
            f"drops={int(r['drop_events_window'])} no_action={int(r['no_action_events_window'])} "
            f"drop_reaction={int(r['drop_reaction_events_window'])} evidence={r['causal_evidence']} "
            f"last_pkt_uid={r['last_drop_pkt_uid']}"
        )

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build collision causality report from run artifacts")
    parser.add_argument("--run-dir", required=True, help="Scenario run directory")
    parser.add_argument("--collision-xml", default="", help="Path to collision XML")
    parser.add_argument("--timeline-csv", default="", help="Path to drop_decision event timeline CSV")
    parser.add_argument("--out-dir", default="", help="Output dir (default: <run>/artifacts/collision_causality)")
    parser.add_argument("--window-s", type=float, default=8.0, help="Lookback window in seconds before collision")
    parser.add_argument("--focus-vehicle", default="", help="Optional collider vehicle filter")
    args = parser.parse_args()

    run_dir = Path(args.run_dir).resolve()
    if not run_dir.exists():
        print(f"Run dir not found: {run_dir}")
        return 1

    collision_xml = (
        Path(args.collision_xml).resolve()
        if args.collision_xml
        else (run_dir / "artifacts" / "eva-collision.xml")
    )
    timeline_csv = (
        Path(args.timeline_csv).resolve()
        if args.timeline_csv
        else (run_dir / "artifacts" / "drop_decision_timeline" / "event_timeline.csv")
    )
    out_dir = Path(args.out_dir).resolve() if args.out_dir else (run_dir / "artifacts" / "collision_causality")
    out_dir.mkdir(parents=True, exist_ok=True)

    timeline = _read_timeline(timeline_csv)
    collisions = _read_collisions(collision_xml)

    report = build_report(
        timeline=timeline,
        collisions=collisions,
        window_s=max(0.1, float(args.window_s)),
        focus_vehicle=args.focus_vehicle.strip(),
    )

    out_csv = out_dir / "collision_causality.csv"
    out_md = out_dir / "collision_causality.md"
    report.to_csv(out_csv, index=False)
    write_md(out_md, report, collision_xml=collision_xml, timeline_csv=timeline_csv)

    print(out_csv)
    print(out_md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
