#!/usr/bin/env bash
# ============================================================================
# EXPERIMENT 4: Vehicle Density Impact on 5G NR Channel and Safety
# ============================================================================
# Research question: How does increasing vehicle density cause 5G NR
# channel congestion (resource collisions), degrade PRR, and impact safety?
#
# Method:
#   - Same base scenario (incident on highway)
#   - Use existing SUMO configs with different vehicle counts:
#     7 vehicles (sparse), 12 (threeflow), 60, 120
#   - Fixed NR params (txPower=23, MCS=14, numerology=2)
#   - No artificial loss — channel congestion causes natural loss
#   - Measure: PRR, latency, PSSCH overlap ratio, TTC, gap, collisions
#
# Output: analysis/scenario_runs/<date>/thesis-exp4-density/
# ============================================================================
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DATE_TAG="$(date +%F)"
OUT_BASE="${OUT_BASE:-$ROOT/analysis/scenario_runs/$DATE_TAG/thesis-exp4-density}"
SIM_TIME="${SIM_TIME:-40}"
SUMO_GUI="${SUMO_GUI:-0}"

NS3_DIR="${NS3_DIR:-}"
NS3_DIR="$("$ROOT/scripts/ensure-ns3-dev.sh" --root "$ROOT" --ns3-dir "$NS3_DIR")"

mkdir -p "$OUT_BASE"

PY_BIN="$ROOT/.venv/bin/python"
if [[ ! -x "$PY_BIN" ]]; then PY_BIN="python3"; fi

SUMMARY_CSV="$OUT_BASE/exp4_density_summary.csv"
echo "vehicle_count,sumo_config,prr_percent,avg_latency_ms,min_ttc_s,min_gap_m,collisions,risky_ttc,risky_gap" > "$SUMMARY_CSV"

# Configs with increasing vehicle counts
declare -A DENSITY_CONFIGS
DENSITY_CONFIGS[7]="src/automotive/examples/sumo_files_v2v_map/map_7.sumo.cfg"
DENSITY_CONFIGS[12]="src/automotive/examples/sumo_files_v2v_map/map_incident_threeflow.sumo.cfg"
DENSITY_CONFIGS[60]="src/automotive/examples/sumo_files_v2v_map/map_60.sumo.cfg"
DENSITY_CONFIGS[120]="src/automotive/examples/sumo_files_v2v_map/map_120.sumo.cfg"

BASE_NR_ARGS="--enableSensing=0 --txPower=23 --mcs=14 --numerologyBwpSl=2 --slThresPsschRsrp=-128 \
  --enableChannelRandomness=1 --channelUpdatePeriod=100"

for count in 7 12 60 120; do
  cfg="${DENSITY_CONFIGS[$count]}"
  if [[ ! -f "$ROOT/ns-3-dev/$cfg" && ! -f "$NS3_DIR/$cfg" ]]; then
    # Try to find the config relative to ROOT
    if [[ ! -f "$ROOT/$cfg" ]]; then
      echo "WARN: Config for $count vehicles not found: $cfg, skipping"
      continue
    fi
  fi

  case_dir="$OUT_BASE/density_${count}"
  mkdir -p "$case_dir"

  echo "=========================================="
  echo "EXP4 DENSITY: $count vehicles"
  echo "=========================================="

  # For sparse configs, incident may use different vehicle IDs
  INCIDENT_ARGS=""
  if [[ "$count" -ge 12 ]]; then
    INCIDENT_ARGS="--incident-enable=1 --incident-vehicle-id=veh2 --incident-time-s=8 --incident-stop-duration-s=20 --incident-setstop-enable=0"
  fi

  RUN_ARGS="--sumo-gui=${SUMO_GUI} --sim-time=${SIM_TIME} --met-sup=1 --penetrationRate=1 \
    --sumo-config=${cfg} \
    ${INCIDENT_ARGS} \
    --rx-drop-prob-phy-cam=0 --rx-drop-prob-phy-cpm=0 \
    --drop-triggered-reaction-enable=0 \
    --cam-reaction-distance-m=22 --cam-reaction-target-lane=1 --reaction-force-lane-change-enable=1 \
    --cpm-reaction-distance-m=0 --cpm-reaction-ttc-s=0 \
    --crash-mode-enable=0 \
    $BASE_NR_ARGS"

  ENABLE_COLLISION_OUTPUT=1 \
  COLLISION_ACTION="warn" \
  OUT_DIR="$case_dir" \
  RUN_ARGS="$RUN_ARGS" \
  "$ROOT/scenarios/v2v-emergencyVehicleAlert-nrv2x/run.sh" || {
    echo "WARN: run failed for density=$count"
    continue
  }

  # Extract metrics
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

  echo "$count,$cfg,$prr,$lat,$ttc,$gap,$coll,$r_ttc,$r_gap" >> "$SUMMARY_CSV"
  echo "  → vehicles=$count PRR=$prr, TTC=$ttc, collisions=$coll"
done

echo ""
echo "============================================"
echo "EXP4 COMPLETE. Summary: $SUMMARY_CSV"
echo "============================================"
cat "$SUMMARY_CSV"

if command -v "$PY_BIN" &>/dev/null; then
  "$PY_BIN" "$ROOT/analysis/scenario_runs/thesis_plot_sweep.py" \
    --summary-csv "$SUMMARY_CSV" \
    --out-dir "$OUT_BASE" \
    --experiment "exp4_density" 2>/dev/null || echo "Plot generation skipped"
fi
