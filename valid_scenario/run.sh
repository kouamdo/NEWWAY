#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DATE_TAG="$(date +%F)"
OUT_DIR="${OUT_DIR:-$HOME/NEWWAY_runs/$DATE_TAG/valid_scenario}"
SUMO_GUI="${SUMO_GUI:-1}"
SIM_TIME="${SIM_TIME:-40}"

PLOT="${PLOT:-0}"
EXPORT_RESULTS="${EXPORT_RESULTS:-0}"
EVENT_TIMELINE="${EVENT_TIMELINE:-1}"
ENABLE_COLLISION_OUTPUT="${ENABLE_COLLISION_OUTPUT:-1}"
COLLISION_ACTION="${COLLISION_ACTION:-warn}"
COLLISION_STOPTIME_S="${COLLISION_STOPTIME_S:-1000}"
COLLISION_CAUSALITY="${COLLISION_CAUSALITY:-1}"
COLLISION_CAUSALITY_FOCUS_VEHICLE="${COLLISION_CAUSALITY_FOCUS_VEHICLE:-veh4}"

BASE_RUN_ARGS="--sumo-gui=${SUMO_GUI} --sim-time=${SIM_TIME} --met-sup=1 --penetrationRate=1 \
--sumo-config=src/automotive/examples/sumo_files_v2v_map/map_incident_threeflow.sumo.cfg \
--incident-enable=1 --incident-vehicle-id=veh2 --incident-time-s=6 --incident-stop-duration-s=20 --incident-setstop-enable=0 \
--cam-reaction-target-lane=1 --cam-reaction-distance-m=22 --reaction-force-lane-change-enable=1 \
--cpm-reaction-distance-m=0 --cpm-reaction-ttc-s=0 \
--drop-triggered-reaction-enable=0 --rx-drop-prob-phy-cam=0 --rx-drop-prob-phy-cpm=0 \
--target-loss-profile-enable=1 --target-loss-vehicle-id=veh4 \
--target-loss-rx-drop-prob-phy-cam=1.0 --target-loss-rx-drop-prob-phy-cpm=1.0 \
--crash-mode-enable=1 --crash-mode-vehicle-id=veh4 --crash-mode-no-action-threshold=10 \
--crash-mode-force-speed-mps=30 --crash-mode-duration-s=6 --crash-mode-min-time-s=6"

EXTRA_RUN_ARGS="${EXTRA_RUN_ARGS:-}"
RUN_ARGS_FINAL="$BASE_RUN_ARGS"
if [[ -n "$EXTRA_RUN_ARGS" ]]; then
  RUN_ARGS_FINAL+=" $EXTRA_RUN_ARGS"
fi

PLOT="$PLOT" \
EXPORT_RESULTS="$EXPORT_RESULTS" \
EVENT_TIMELINE="$EVENT_TIMELINE" \
ENABLE_COLLISION_OUTPUT="$ENABLE_COLLISION_OUTPUT" \
COLLISION_ACTION="$COLLISION_ACTION" \
COLLISION_STOPTIME_S="$COLLISION_STOPTIME_S" \
COLLISION_CAUSALITY="$COLLISION_CAUSALITY" \
COLLISION_CAUSALITY_FOCUS_VEHICLE="$COLLISION_CAUSALITY_FOCUS_VEHICLE" \
OUT_DIR="$OUT_DIR" \
RUN_ARGS="$RUN_ARGS_FINAL" \
"$ROOT/scenarios/v2v-emergencyVehicleAlert-nrv2x/run.sh"

PY_BIN="$ROOT/.venv/bin/python"
if [[ ! -x "$PY_BIN" ]]; then
  PY_BIN="python3"
fi

STORY_OUT_DIR="${STORY_OUT_DIR:-$OUT_DIR/artifacts/valid_scenario_story}"
"$PY_BIN" "$ROOT/analysis/scenario_runs/build_valid_scenario_story_plots.py" \
  --run-dir "$OUT_DIR" \
  --out-dir "$STORY_OUT_DIR"

echo "VALID_SCENARIO_DONE: $OUT_DIR"
echo "STORY_PLOTS: $STORY_OUT_DIR"
