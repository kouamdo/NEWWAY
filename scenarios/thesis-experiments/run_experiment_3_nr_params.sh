#!/usr/bin/env bash
# ============================================================================
# EXPERIMENT 3: Impact of 5G NR Physical Layer Parameters on Safety
# ============================================================================
# Research question: How do actual 5G NR PHY parameters (txPower, MCS,
# numerology, bandwidth) affect message delivery and vehicle safety?
#
# This is the CORE experiment that ties 5G NR parameters to safety outcomes.
# Unlike artificial drop probability sweeps, this varies REAL NR parameters
# and measures the NATURAL packet loss they cause.
#
# Method:
#   - Fixed traffic scenario: incident + follower reaction (proven EVA setup)
#   - Sweep independently:
#     (a) txPower: 5, 10, 15, 20, 23 dBm
#     (b) MCS: 2, 5, 10, 14, 20, 28
#     (c) Numerology (μ): 0, 1, 2, 3
#   - No artificial loss injection — let PHY-layer determine natural PRR
#   - Measure: PRR, latency, SINR, TTC, gap, collisions
#
# Output: analysis/scenario_runs/<date>/thesis-exp3-nr-params/
# ============================================================================
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DATE_TAG="$(date +%F)"
OUT_BASE="${OUT_BASE:-$ROOT/analysis/scenario_runs/$DATE_TAG/thesis-exp3-nr-params}"
SIM_TIME="${SIM_TIME:-40}"
SUMO_GUI="${SUMO_GUI:-0}"

# Parameter grids
TX_POWERS="${TX_POWERS:-5 10 15 20 23}"
MCS_VALUES="${MCS_VALUES:-2 5 10 14 20 28}"
NUMEROLOGIES="${NUMEROLOGIES:-0 1 2 3}"

# Which sweep to run (all by default)
RUN_TXPOWER="${RUN_TXPOWER:-1}"
RUN_MCS="${RUN_MCS:-1}"
RUN_NUMEROLOGY="${RUN_NUMEROLOGY:-1}"

NS3_DIR="${NS3_DIR:-}"
NS3_DIR="$("$ROOT/scripts/ensure-ns3-dev.sh" --root "$ROOT" --ns3-dir "$NS3_DIR")"

mkdir -p "$OUT_BASE"

PY_BIN="$ROOT/.venv/bin/python"
if [[ ! -x "$PY_BIN" ]]; then PY_BIN="python3"; fi

# Base scenario: incident on highway with known-safe baseline
SUMO_CFG="src/automotive/examples/sumo_files_v2v_map/map_incident_threeflow.sumo.cfg"

BASE_ARGS="--sumo-gui=${SUMO_GUI} --sim-time=${SIM_TIME} --met-sup=1 --penetrationRate=1 \
  --sumo-config=${SUMO_CFG} \
  --incident-enable=1 --incident-vehicle-id=veh2 --incident-time-s=8 --incident-stop-duration-s=20 \
  --incident-setstop-enable=0 \
  --rx-drop-prob-phy-cam=0 --rx-drop-prob-phy-cpm=0 \
  --drop-triggered-reaction-enable=0 \
  --cam-reaction-distance-m=22 --cam-reaction-target-lane=1 --reaction-force-lane-change-enable=1 \
  --cpm-reaction-distance-m=0 --cpm-reaction-ttc-s=0 \
  --crash-mode-enable=0 \
  --enableSensing=0 --enableChannelRandomness=1 --channelUpdatePeriod=100"

run_single() {
  local label="$1"
  local extra_args="$2"
  local case_dir="$OUT_BASE/$label"
  mkdir -p "$case_dir"

  echo "--- Running: $label ---"
  RUN_ARGS="$BASE_ARGS $extra_args" \
  ENABLE_COLLISION_OUTPUT=1 \
  COLLISION_ACTION="warn" \
  OUT_DIR="$case_dir" \
  "$ROOT/scenarios/v2v-emergencyVehicleAlert-nrv2x/run.sh" || {
    echo "WARN: run failed for $label"
    return 1
  }
}

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

# =================== SWEEP (a): txPower ===================
if [[ "$RUN_TXPOWER" == "1" ]]; then
  echo "=================================================="
  echo "EXP3a: txPower sweep"
  echo "=================================================="
  SWEEP_CSV="$OUT_BASE/exp3a_txpower_sweep.csv"
  echo "txPower_dBm,prr_percent,avg_latency_ms,min_ttc_s,min_gap_m,collisions,risky_ttc,risky_gap" > "$SWEEP_CSV"

  for txp in $TX_POWERS; do
    label="txpower_${txp}dBm"
    run_single "$label" "--txPower=$txp --mcs=14 --numerologyBwpSl=2" || continue
    metrics=$(extract_metrics "$OUT_BASE/$label")
    echo "$txp,$metrics" >> "$SWEEP_CSV"
    echo "  txPower=$txp → $metrics"
  done
  echo "Sweep saved: $SWEEP_CSV"
fi

# =================== SWEEP (b): MCS ===================
if [[ "$RUN_MCS" == "1" ]]; then
  echo "=================================================="
  echo "EXP3b: MCS sweep"
  echo "=================================================="
  SWEEP_CSV="$OUT_BASE/exp3b_mcs_sweep.csv"
  echo "mcs,prr_percent,avg_latency_ms,min_ttc_s,min_gap_m,collisions,risky_ttc,risky_gap" > "$SWEEP_CSV"

  for m in $MCS_VALUES; do
    label="mcs_${m}"
    run_single "$label" "--txPower=23 --mcs=$m --numerologyBwpSl=2" || continue
    metrics=$(extract_metrics "$OUT_BASE/$label")
    echo "$m,$metrics" >> "$SWEEP_CSV"
    echo "  MCS=$m → $metrics"
  done
  echo "Sweep saved: $SWEEP_CSV"
fi

# =================== SWEEP (c): Numerology ===================
if [[ "$RUN_NUMEROLOGY" == "1" ]]; then
  echo "=================================================="
  echo "EXP3c: Numerology sweep"
  echo "=================================================="
  SWEEP_CSV="$OUT_BASE/exp3c_numerology_sweep.csv"
  echo "numerology,prr_percent,avg_latency_ms,min_ttc_s,min_gap_m,collisions,risky_ttc,risky_gap" > "$SWEEP_CSV"

  for nu in $NUMEROLOGIES; do
    label="numerology_${nu}"
    # Adjust T2 selection window for different numerologies
    t2_val=$((81 * (1 << nu)))
    run_single "$label" "--txPower=23 --mcs=14 --numerologyBwpSl=$nu --t2=$t2_val" || continue
    metrics=$(extract_metrics "$OUT_BASE/$label")
    echo "$nu,$metrics" >> "$SWEEP_CSV"
    echo "  Numerology=$nu → $metrics"
  done
  echo "Sweep saved: $SWEEP_CSV"
fi

echo ""
echo "============================================"
echo "EXP3 COMPLETE. Results in: $OUT_BASE"
echo "============================================"

if command -v "$PY_BIN" &>/dev/null; then
  "$PY_BIN" "$ROOT/analysis/scenario_runs/thesis_plot_sweep.py" \
    --summary-csv "$OUT_BASE/exp3a_txpower_sweep.csv" \
    --out-dir "$OUT_BASE" \
    --experiment "exp3a_txpower" 2>/dev/null || true
  "$PY_BIN" "$ROOT/analysis/scenario_runs/thesis_plot_sweep.py" \
    --summary-csv "$OUT_BASE/exp3b_mcs_sweep.csv" \
    --out-dir "$OUT_BASE" \
    --experiment "exp3b_mcs" 2>/dev/null || true
  "$PY_BIN" "$ROOT/analysis/scenario_runs/thesis_plot_sweep.py" \
    --summary-csv "$OUT_BASE/exp3c_numerology_sweep.csv" \
    --out-dir "$OUT_BASE" \
    --experiment "exp3c_numerology" 2>/dev/null || true
fi
