#!/usr/bin/env bash
# ============================================================================
# EXPERIMENT 2: Platoon Emergency Braking under 5G NR Message Loss
# ============================================================================
# Research question: How does 5G NR message loss affect cooperative braking
# in a vehicle platoon (CACC), and does it cause pile-up collisions?
#
# Method:
#   - 6-vehicle platoon on 3-lane highway, tight inter-vehicle spacing (~10m)
#   - Leader (veh_lead) performs emergency stop at ~10s (incident injection)
#   - Followers rely on CAM for cooperative braking (shorter reaction time)
#   - Sweep PHY-level CAM drop: 0%, 20%, 40%, 60%, 80%, 100%
#   - Target loss on rear followers (veh_f3, veh_f4, veh_f5) via per-vehicle profile
#   - Measure: PRR, reaction delay, TTC, gap, collision chain length
#
# Output: analysis/scenario_runs/<date>/thesis-exp2-platoon/
# ============================================================================
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DATE_TAG="$(date +%F)"
OUT_BASE="${OUT_BASE:-$ROOT/analysis/scenario_runs/$DATE_TAG/thesis-exp2-platoon}"
SIM_TIME="${SIM_TIME:-45}"
SUMO_GUI="${SUMO_GUI:-0}"

LOSS_PROBS="${LOSS_PROBS:-0.0 0.2 0.4 0.6 0.8 1.0}"

NS3_DIR="${NS3_DIR:-}"
NS3_DIR="$("$ROOT/scripts/ensure-ns3-dev.sh" --root "$ROOT" --ns3-dir "$NS3_DIR")"

mkdir -p "$OUT_BASE"

PY_BIN="$ROOT/.venv/bin/python"
if [[ ! -x "$PY_BIN" ]]; then PY_BIN="python3"; fi

SUMMARY_CSV="$OUT_BASE/exp2_platoon_summary.csv"
echo "loss_prob,prr_percent,avg_latency_ms,min_ttc_s,min_gap_m,collisions,risky_ttc_events,risky_gap_events" > "$SUMMARY_CSV"

for prob in $LOSS_PROBS; do
  case_id="loss_${prob//./p}"
  case_dir="$OUT_BASE/$case_id"
  mkdir -p "$case_dir"

  echo "=========================================="
  echo "EXP2 PLATOON: loss_prob=$prob"
  echo "=========================================="

  SUMO_CFG="src/automotive/examples/sumo_files_platoon/platoon.sumo.cfg"

  # Target loss on rear platoon members (veh_f4 is most vulnerable)
  RUN_ARGS="--sumo-gui=${SUMO_GUI} --sim-time=${SIM_TIME} --met-sup=1 --penetrationRate=1 \
    --sumo-config=${SUMO_CFG} \
    --incident-enable=1 --incident-vehicle-id=veh_lead --incident-time-s=10 --incident-stop-duration-s=20 \
    --incident-setstop-enable=0 \
    --rx-drop-prob-phy-cam=0 --rx-drop-prob-phy-cpm=0 \
    --target-loss-profile-enable=1 --target-loss-vehicle-id=veh_f4 \
    --target-loss-rx-drop-prob-phy-cam=${prob} --target-loss-rx-drop-prob-phy-cpm=${prob} \
    --drop-triggered-reaction-enable=0 \
    --cam-reaction-distance-m=30 --cam-reaction-heading-deg=15 \
    --cam-reaction-target-lane=0 --reaction-force-lane-change-enable=1 \
    --cam-reaction-speed-factor-target-lane=0.3 --cam-reaction-speed-factor-other-lane=1.5 \
    --cam-reaction-action-duration-s=5.0 \
    --cpm-reaction-distance-m=0 --cpm-reaction-ttc-s=0 \
    --crash-mode-enable=1 --crash-mode-vehicle-id=veh_f4 --crash-mode-no-action-threshold=8 \
    --crash-mode-force-speed-mps=28 --crash-mode-duration-s=5 --crash-mode-min-time-s=8 \
    --enableSensing=0 --txPower=23 --slThresPsschRsrp=-128"

  ENABLE_COLLISION_OUTPUT=1 \
  COLLISION_ACTION="warn" \
  OUT_DIR="$case_dir" \
  RUN_ARGS="$RUN_ARGS" \
  "$ROOT/scenarios/v2v-emergencyVehicleAlert-nrv2x/run.sh" || {
    echo "WARN: run failed for loss_prob=$prob, skipping"
    continue
  }

  # Extract metrics (same pattern as exp1)
  prr="N/A"; lat="N/A"; ttc="N/A"; gap="N/A"; coll="0"; r_ttc="0"; r_gap="0"

  for csv in "$case_dir"/artifacts/*cumulative*.csv "$case_dir"/*cumulative*.csv; do
    if [[ -f "$csv" ]]; then
      prr=$(tail -1 "$csv" | cut -d',' -f2 2>/dev/null || echo "N/A")
      lat=$(tail -1 "$csv" | cut -d',' -f3 2>/dev/null || echo "N/A")
      break
    fi
  done

  risk_csv="$case_dir/artifacts/collision_risk_summary.csv"
  if [[ -f "$risk_csv" ]]; then
    ttc=$(tail -1 "$risk_csv" | cut -d',' -f2 2>/dev/null || echo "N/A")
    gap=$(tail -1 "$risk_csv" | cut -d',' -f3 2>/dev/null || echo "N/A")
    r_ttc=$(tail -1 "$risk_csv" | cut -d',' -f4 2>/dev/null || echo "0")
    r_gap=$(tail -1 "$risk_csv" | cut -d',' -f5 2>/dev/null || echo "0")
  fi

  coll_xml="$case_dir/artifacts/eva-collision.xml"
  if [[ -f "$coll_xml" ]]; then
    coll=$(grep -c '<collision' "$coll_xml" 2>/dev/null || echo "0")
  fi

  echo "$prob,$prr,$lat,$ttc,$gap,$coll,$r_ttc,$r_gap" >> "$SUMMARY_CSV"
  echo "  → PRR=$prr, latency=$lat ms, TTC=$ttc s, collisions=$coll"
done

echo ""
echo "============================================"
echo "EXP2 COMPLETE. Summary: $SUMMARY_CSV"
echo "============================================"
cat "$SUMMARY_CSV"

if command -v "$PY_BIN" &>/dev/null; then
  "$PY_BIN" "$ROOT/analysis/scenario_runs/thesis_plot_sweep.py" \
    --summary-csv "$SUMMARY_CSV" \
    --out-dir "$OUT_BASE" \
    --experiment "exp2_platoon" 2>/dev/null || echo "Plot generation skipped"
fi
