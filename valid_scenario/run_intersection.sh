#!/usr/bin/env bash
# ============================================================================
# Valid Scenario Variant: Intersection Collision Demonstration
# ============================================================================
# Deterministic demonstration of T-bone collision at intersection
# caused by 100% 5G NR message loss on the autonomous vehicle.
#
# Like the original valid_scenario, this is thesis-grade reproducible.
# ============================================================================
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DATE_TAG="$(date +%F)"
OUT_DIR="${OUT_DIR:-$HOME/NEWWAY_runs/$DATE_TAG/valid_scenario_intersection}"
SUMO_GUI="${SUMO_GUI:-1}"
SIM_TIME="${SIM_TIME:-40}"

PLOT="${PLOT:-0}"
EXPORT_RESULTS="${EXPORT_RESULTS:-0}"
EVENT_TIMELINE="${EVENT_TIMELINE:-1}"
ENABLE_COLLISION_OUTPUT="${ENABLE_COLLISION_OUTPUT:-1}"
COLLISION_ACTION="${COLLISION_ACTION:-warn}"
COLLISION_STOPTIME_S="${COLLISION_STOPTIME_S:-1000}"
COLLISION_CAUSALITY="${COLLISION_CAUSALITY:-1}"
COLLISION_CAUSALITY_FOCUS_VEHICLE="${COLLISION_CAUSALITY_FOCUS_VEHICLE:-veh_s1}"

BASE_RUN_ARGS="--sumo-gui=${SUMO_GUI} --sim-time=${SIM_TIME} --met-sup=1 --penetrationRate=1 \
--sumo-config=src/automotive/examples/sumo_files_intersection/intersection.sumo.cfg \
--cam-reaction-distance-m=50 --cam-reaction-heading-deg=90 --cam-reaction-target-lane=0 \
--reaction-force-lane-change-enable=0 \
--cpm-reaction-distance-m=50 --cpm-reaction-ttc-s=3.0 \
--drop-triggered-reaction-enable=0 \
--target-loss-profile-enable=1 --target-loss-vehicle-id=veh_s1 \
--target-loss-rx-drop-prob-phy-cam=1.0 --target-loss-rx-drop-prob-phy-cpm=1.0 \
--rx-drop-prob-phy-cam=0 --rx-drop-prob-phy-cpm=0 \
--crash-mode-enable=1 --crash-mode-vehicle-id=veh_s1 --crash-mode-no-action-threshold=5 \
--crash-mode-force-speed-mps=13 --crash-mode-duration-s=8 --crash-mode-min-time-s=3 \
--enableSensing=0 --txPower=23 --slThresPsschRsrp=-128"

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
  --out-dir "$STORY_OUT_DIR" 2>/dev/null || echo "Story plot generation skipped"

echo "VALID_SCENARIO_INTERSECTION_DONE: $OUT_DIR"
echo "STORY_PLOTS: $STORY_OUT_DIR"
