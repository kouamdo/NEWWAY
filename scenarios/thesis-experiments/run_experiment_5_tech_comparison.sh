#!/usr/bin/env bash
# ============================================================================
# EXPERIMENT 5: 802.11p vs NR-V2X Technology Comparison under Loss
# ============================================================================
# Research question: Does 5G NR-V2X provide better safety outcomes than
# legacy 802.11p under identical traffic conditions and loss profiles?
#
# Method:
#   - Identical traffic scenario for both technologies
#   - Same incident injection (leader stops at t=8s)
#   - Sweep loss probability: 0%, 30%, 60%, 90%
#   - Compare PRR, latency, TTC, gap, collision outcomes
#   - NR-V2X: v2v-emergencyVehicleAlert-nrv2x
#   - 802.11p: v2v-emergencyVehicleAlert-80211p (same loss injection args)
#
# Output: analysis/scenario_runs/<date>/thesis-exp5-tech-comparison/
# ============================================================================
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DATE_TAG="$(date +%F)"
OUT_BASE="${OUT_BASE:-$ROOT/analysis/scenario_runs/$DATE_TAG/thesis-exp5-tech-comparison}"
SIM_TIME="${SIM_TIME:-40}"
SUMO_GUI="${SUMO_GUI:-0}"

LOSS_PROBS="${LOSS_PROBS:-0.0 0.3 0.6 0.9}"

NS3_DIR="${NS3_DIR:-}"
NS3_DIR="$("$ROOT/scripts/ensure-ns3-dev.sh" --root "$ROOT" --ns3-dir "$NS3_DIR")"

mkdir -p "$OUT_BASE"

PY_BIN="$ROOT/.venv/bin/python"
if [[ ! -x "$PY_BIN" ]]; then PY_BIN="python3"; fi

SUMMARY_CSV="$OUT_BASE/exp5_tech_comparison.csv"
echo "technology,loss_prob,prr_percent,avg_latency_ms,min_ttc_s,min_gap_m,collisions,risky_ttc,risky_gap" > "$SUMMARY_CSV"

SUMO_CFG="src/automotive/examples/sumo_files_v2v_map/map_incident_threeflow.sumo.cfg"

COMMON_ARGS="--sumo-gui=${SUMO_GUI} --sim-time=${SIM_TIME} --met-sup=1 --penetrationRate=1 \
  --sumo-config=${SUMO_CFG} \
  --incident-enable=1 --incident-vehicle-id=veh2 --incident-time-s=8 --incident-stop-duration-s=20 \
  --incident-setstop-enable=0 \
  --drop-triggered-reaction-enable=0 \
  --cam-reaction-distance-m=22 --cam-reaction-target-lane=1 --reaction-force-lane-change-enable=1 \
  --cpm-reaction-distance-m=0 --cpm-reaction-ttc-s=0 \
  --crash-mode-enable=1 --crash-mode-vehicle-id=veh4 --crash-mode-no-action-threshold=10 \
  --crash-mode-force-speed-mps=30 --crash-mode-duration-s=6 --crash-mode-min-time-s=6 \
  --target-loss-profile-enable=1 --target-loss-vehicle-id=veh4"

extract_metrics() {
  local case_dir="$1"
  local prr="N/A" lat="N/A" ttc="N/A" gap="N/A" coll="0" r_ttc="0" r_gap="0"

  for csv in "$case_dir"/artifacts/*cumulative*.csv "$case_dir"/*cumulative*.csv; do
    if [[ -f "$csv" ]]; then
      prr=$(tail -1 "$csv" | cut -d',' -f2 2>/dev/null || echo "N/A")
      lat=$(tail -1 "$csv" | cut -d',' -f3 2>/dev/null || echo "N/A")
      break
    fi
  done

  local risk_csv="$case_dir/artifacts/collision_risk_summary.csv"
  if [[ -f "$risk_csv" ]]; then
    ttc=$(tail -1 "$risk_csv" | cut -d',' -f2 2>/dev/null || echo "N/A")
    gap=$(tail -1 "$risk_csv" | cut -d',' -f3 2>/dev/null || echo "N/A")
    r_ttc=$(tail -1 "$risk_csv" | cut -d',' -f4 2>/dev/null || echo "0")
    r_gap=$(tail -1 "$risk_csv" | cut -d',' -f5 2>/dev/null || echo "0")
  fi

  local coll_xml="$case_dir/artifacts/eva-collision.xml"
  if [[ -f "$coll_xml" ]]; then
    coll=$(grep -c '<collision' "$coll_xml" 2>/dev/null || echo "0")
  fi

  echo "$prr,$lat,$ttc,$gap,$coll,$r_ttc,$r_gap"
}

# =================== NR-V2X runs ===================
echo "======================================================"
echo "EXP5: NR-V2X technology"
echo "======================================================"

for prob in $LOSS_PROBS; do
  case_id="nrv2x_loss_${prob//./p}"
  case_dir="$OUT_BASE/$case_id"
  mkdir -p "$case_dir"

  echo "--- NR-V2X loss=$prob ---"

  RUN_ARGS="$COMMON_ARGS \
    --target-loss-rx-drop-prob-phy-cam=${prob} --target-loss-rx-drop-prob-phy-cpm=${prob} \
    --rx-drop-prob-phy-cam=0 --rx-drop-prob-phy-cpm=0 \
    --enableSensing=0 --txPower=23 --slThresPsschRsrp=-128"

  ENABLE_COLLISION_OUTPUT=1 \
  COLLISION_ACTION="warn" \
  OUT_DIR="$case_dir" \
  RUN_ARGS="$RUN_ARGS" \
  "$ROOT/scenarios/v2v-emergencyVehicleAlert-nrv2x/run.sh" || {
    echo "WARN: NR-V2X run failed for loss=$prob"
    continue
  }

  metrics=$(extract_metrics "$case_dir")
  echo "NR-V2X,$prob,$metrics" >> "$SUMMARY_CSV"
  echo "  → NR-V2X loss=$prob: $metrics"
done

# =================== 802.11p runs ===================
echo "======================================================"
echo "EXP5: 802.11p technology"
echo "======================================================"

# Check if 80211p scenario runner exists
WIFI_RUNNER="$ROOT/scenarios/v2v-emergencyVehicleAlert-80211p/run.sh"
if [[ ! -x "$WIFI_RUNNER" ]]; then
  # Fallback: try to use the NR runner with a note
  echo "NOTE: 802.11p scenario runner not found at $WIFI_RUNNER."
  echo "Creating stub 802.11p results with the same framework."
  echo "For full comparison, build and run v2v-emergencyVehicleAlert-80211p separately."

  for prob in $LOSS_PROBS; do
    echo "80211p,$prob,N/A,N/A,N/A,N/A,N/A,N/A,N/A" >> "$SUMMARY_CSV"
  done
else
  for prob in $LOSS_PROBS; do
    case_id="80211p_loss_${prob//./p}"
    case_dir="$OUT_BASE/$case_id"
    mkdir -p "$case_dir"

    echo "--- 802.11p loss=$prob ---"

    RUN_ARGS="$COMMON_ARGS \
      --target-loss-rx-drop-prob-phy-cam=${prob} --target-loss-rx-drop-prob-phy-cpm=${prob} \
      --rx-drop-prob-phy-cam=0 --rx-drop-prob-phy-cpm=0"

    ENABLE_COLLISION_OUTPUT=1 \
    COLLISION_ACTION="warn" \
    OUT_DIR="$case_dir" \
    RUN_ARGS="$RUN_ARGS" \
    "$WIFI_RUNNER" || {
      echo "WARN: 802.11p run failed for loss=$prob"
      continue
    }

    metrics=$(extract_metrics "$case_dir")
    echo "80211p,$prob,$metrics" >> "$SUMMARY_CSV"
    echo "  → 802.11p loss=$prob: $metrics"
  done
fi

echo ""
echo "============================================"
echo "EXP5 COMPLETE. Summary: $SUMMARY_CSV"
echo "============================================"
cat "$SUMMARY_CSV"

if command -v "$PY_BIN" &>/dev/null; then
  "$PY_BIN" "$ROOT/analysis/scenario_runs/thesis_plot_sweep.py" \
    --summary-csv "$SUMMARY_CSV" \
    --out-dir "$OUT_BASE" \
    --experiment "exp5_tech_comparison" 2>/dev/null || echo "Plot generation skipped"
fi
