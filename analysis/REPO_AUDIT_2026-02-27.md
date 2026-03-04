# Repository Audit (2026-02-27)

## Scope

This audit focuses on:
- repository structure and maintainability signals,
- run/log artifacts under `analysis/scenario_runs`,
- ns-3 <-> SUMO bidirectional coupling evidence around PHY drops and control decisions.

## Snapshot

- Project root file count (`rg --files | wc -l`): `13182`
- `analysis/` size: `518M`
- `analysis/` file count: `11911`
- `analysis/scenario_runs` audited rows: `153` runs
- Top-level log files in audited runs: `160`
- Recursive CSV files in audited runs: `4302`
- Recursive PNG files in audited runs: `414`

Detailed run-level metrics are in:
- `analysis/scenario_runs/log_audit_summary_2026-02-27.csv`
- `analysis/scenario_runs/LOG_AUDIT_2026-02-27.md`

## TODO / FIXME concentration

Quick count across `src/ scenarios/ docs/`:
- `TODO|FIXME|HACK|XXX`: `270` occurrences

Hotspots:
- `src/nr`: `108`
- `src/automotive`: `65`
- `src/vehicle-visualizer`: `59`
- `src/cv2x`: `36`

## Coupling-quality evidence (DROP -> DECISION)

New ID-aware timeline outputs are produced per run:
- `artifacts/drop_decision_timeline/event_timeline.csv`
- `artifacts/drop_decision_timeline/summary.csv`
- `artifacts/drop_decision_timeline/decision_delay_scatter.png`
- `artifacts/drop_decision_timeline/decision_type_counts.png`

Latest check run:
- `analysis/scenario_runs/2026-02-27/timeline-auto-check`
- strict match ratio (`DROP_PHY` to decision by `pkt_uid`): `1.0`

## What was improved in this step

1. Added pkt_uid-aware timeline generator:
   - `analysis/scenario_runs/build_drop_decision_timeline.py`
2. Added global log auditor:
   - `analysis/scenario_runs/analyze_all_logs.py`
3. Integrated automatic timeline generation into:
   - `scenarios/v2v-emergencyVehicleAlert-nrv2x/run.sh` (`EVENT_TIMELINE=1` by default)
4. Updated documentation:
   - `analysis/scenario_runs/README.md`
   - `scenarios/v2v-emergencyVehicleAlert-nrv2x/README.md`
   - `README.md`

## Recommended next cleanup wave

1. Prioritize and triage `TODO/FIXME` in `src/nr` and `src/automotive`.
2. Add CI job for:
   - `analyze_all_logs.py` (nightly),
   - `build_drop_decision_timeline.py` on latest EVA run.
3. Add one regression test that checks `strict_match_ratio == 1.0` on a short deterministic run.
