#!/usr/bin/env bash
# ============================================================================
# EXPERIMENT 1: Intersection Collision under 5G NR Message Loss
# ============================================================================
# Research question: Does 5G NR message loss at a signalized intersection
# cause autonomous vehicles to miss cross-traffic warnings (CAM) and collide?
#
# Method:
#   - 4-way intersection with cross-traffic flows (W→E and S→N)
#   - veh_s1 (autonomous) relies on CAM from veh_w1 to yield
#   - Sweep PHY-level CAM drop probability: 0%, 30%, 60%, 90%, 100%
#   - Measure: PRR, latency, TTC, gap, collision count
#
# Output: analysis/scenario_runs/<date>/thesis-exp1-intersection/
# ============================================================================
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DATE_TAG="$(date +%F)"
OUT_BASE="${OUT_BASE:-$ROOT/analysis/scenario_runs/$DATE_TAG/thesis-exp1-intersection}"
SIM_TIME="${SIM_TIME:-40}"
SUMO_GUI="${SUMO_GUI:-0}"

LOSS_PROBS="${LOSS_PROBS:-0.0 0.3 0.6 0.9 1.0}"

NS3_DIR="${NS3_DIR:-}"
NS3_DIR="$("$ROOT/scripts/ensure-ns3-dev.sh" --root "$ROOT" --ns3-dir "$NS3_DIR")"

TARGET="${BUILD_TARGET:-v2v-emergencyVehicleAlert-nrv2x}"

mkdir -p "$OUT_BASE"

PY_BIN="$ROOT/.venv/bin/python"
if [[ ! -x "$PY_BIN" ]]; then PY_BIN="python3"; fi

SUMMARY_CSV="$OUT_BASE/exp1_intersection_summary.csv"
echo "loss_prob,prr_percent,avg_latency_ms,min_ttc_s,min_gap_m,collisions,risky_ttc_events,risky_gap_events" > "$SUMMARY_CSV"

ENABLE_COLLISION_OUTPUT=1
COLLISION_ACTION="warn"

for prob in $LOSS_PROBS; do
  case_id="loss_${prob//./p}"
  case_dir="$OUT_BASE/$case_id"
  mkdir -p "$case_dir"

  echo "=========================================="
  echo "EXP1 INTERSECTION: loss_prob=$prob"
  echo "=========================================="

  SUMO_CFG="src/automotive/examples/sumo_files_intersection/intersection.sumo.cfg"

  RUN_ARGS="--sumo-gui=${SUMO_GUI} --sim-time=${SIM_TIME} --met-sup=1 --penetrationRate=1 \
    --sumo-config=${SUMO_CFG} \
    --rx-drop-prob-phy-cam=${prob} --rx-drop-prob-phy-cpm=${prob} \
    --drop-triggered-reaction-enable=0 \
    --target-loss-profile-enable=1 --target-loss-vehicle-id=veh_s1 \
    --target-loss-rx-drop-prob-phy-cam=${prob} --target-loss-rx-drop-prob-phy-cpm=${prob} \
    --cam-reaction-distance-m=50 --cam-reaction-heading-deg=90 \
    --cam-reaction-target-lane=0 --reaction-force-lane-change-enable=0 \
    --cpm-reaction-distance-m=50 --cpm-reaction-ttc-s=3.0 \
    --enableSensing=0 --txPower=23 --slThresPsschRsrp=-128"

  ENABLE_COLLISION_OUTPUT="$ENABLE_COLLISION_OUTPUT" \
  COLLISION_ACTION="$COLLISION_ACTION" \
  SUMO_GUI="$SUMO_GUI" \
  OUT_DIR="$case_dir" \
  RUN_ARGS="$RUN_ARGS" \
  "$ROOT/scenarios/v2v-emergencyVehicleAlert-nrv2x/run.sh" || {
    echo "WARN: run failed for loss_prob=$prob, skipping"
    continue
  }

  # Extract metrics
  prr="N/A"; lat="N/A"; ttc="N/A"; gap="N/A"; coll="0"; r_ttc="0"; r_gap="0"

  # PRR/latency from MetricSupervisor CSV
  for csv in "$case_dir"/artifacts/*cumulative*.csv "$case_dir"/*cumulative*.csv; do
    if [[ -f "$csv" ]]; then
      prr=$(tail -1 "$csv" | cut -d',' -f2 2>/dev/null || echo "N/A")
      lat=$(tail -1 "$csv" | cut -d',' -f3 2>/dev/null || echo "N/A")
      break
    fi
  done

  # Collision risk from netstate analysis
  risk_csv="$case_dir/artifacts/collision_risk_summary.csv"
  if [[ -f "$risk_csv" ]]; then
    ttc=$(tail -1 "$risk_csv" | cut -d',' -f2 2>/dev/null || echo "N/A")
    gap=$(tail -1 "$risk_csv" | cut -d',' -f3 2>/dev/null || echo "N/A")
    r_ttc=$(tail -1 "$risk_csv" | cut -d',' -f4 2>/dev/null || echo "0")
    r_gap=$(tail -1 "$risk_csv" | cut -d',' -f5 2>/dev/null || echo "0")
  fi

  # Collision count from XML
  coll_xml="$case_dir/artifacts/eva-collision.xml"
  if [[ -f "$coll_xml" ]]; then
    coll=$(grep -c '<collision' "$coll_xml" 2>/dev/null || echo "0")
  fi

  echo "$prob,$prr,$lat,$ttc,$gap,$coll,$r_ttc,$r_gap" >> "$SUMMARY_CSV"
  echo "  → PRR=$prr, latency=$lat ms, TTC=$ttc s, collisions=$coll"
done

echo ""
echo "============================================"
echo "EXP1 COMPLETE. Summary: $SUMMARY_CSV"
echo "============================================"
cat "$SUMMARY_CSV"

# Generate plots
if command -v "$PY_BIN" &>/dev/null; then
  "$PY_BIN" "$ROOT/analysis/scenario_runs/thesis_plot_sweep.py" \
    --summary-csv "$SUMMARY_CSV" \
    --out-dir "$OUT_BASE" \
    --experiment "exp1_intersection" 2>/dev/null || echo "Plot generation skipped (script not found or error)"
fi
