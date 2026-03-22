#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
NS3_DIR="${NS3_DIR:-}"
OUT_DIR="${OUT_DIR:-$ROOT/analysis/scenario_runs/$(date +%F)}"
JOBS="${JOBS:-8}"
RUN_ARGS="${RUN_ARGS:---sumo-gui=0 --sim-time=40 --met-sup=1}"
EXTRA_ARGS="${EXTRA_ARGS:-}"
PLOT="${PLOT:-1}"
RUN_RETRIES="${RUN_RETRIES:-3}"
SUMO_PORT="${SUMO_PORT:-}"
CSV_PREFIX="${CSV_PREFIX:-$OUT_DIR/artifacts/eva}"
NETSTATE_FILE="${NETSTATE_FILE:-$OUT_DIR/artifacts/eva-netstate.xml}"
RISK_GAP_THRESHOLD="${RISK_GAP_THRESHOLD:-2.0}"
RISK_TTC_THRESHOLD="${RISK_TTC_THRESHOLD:-1.5}"
ENABLE_COLLISION_OUTPUT="${ENABLE_COLLISION_OUTPUT:-0}"
COLLISION_OUTPUT_FILE="${COLLISION_OUTPUT_FILE:-$OUT_DIR/artifacts/eva-collision.xml}"
COLLISION_ACTION="${COLLISION_ACTION:-warn}"
COLLISION_CHECK_JUNCTIONS="${COLLISION_CHECK_JUNCTIONS:-1}"
COLLISION_STOPTIME_S="${COLLISION_STOPTIME_S:-}"
EXPORT_RESULTS="${EXPORT_RESULTS:-1}"
EXPORT_ROOT="${EXPORT_ROOT:-$ROOT/analysis/scenario_runs/chatgpt_exports}"
EXPORT_INCLUDE_RAW_CSV="${EXPORT_INCLUDE_RAW_CSV:-0}"
EVENT_TIMELINE="${EVENT_TIMELINE:-1}"
EVENT_TIMELINE_DIR="${EVENT_TIMELINE_DIR:-$OUT_DIR/artifacts/drop_decision_timeline}"
COLLISION_CAUSALITY="${COLLISION_CAUSALITY:-1}"
COLLISION_CAUSALITY_WINDOW_S="${COLLISION_CAUSALITY_WINDOW_S:-8.0}"
COLLISION_CAUSALITY_OUT_DIR="${COLLISION_CAUSALITY_OUT_DIR:-$OUT_DIR/artifacts/collision_causality}"
COLLISION_CAUSALITY_FOCUS_VEHICLE="${COLLISION_CAUSALITY_FOCUS_VEHICLE:-}"
NS3_CONFIGURE_ARGS="${NS3_CONFIGURE_ARGS:---enable-examples --build-profile=optimized --disable-werror}"
NS3_REQUIRE_OPTIMIZED="${NS3_REQUIRE_OPTIMIZED:-1}"

if [[ "$OUT_DIR" != /* ]]; then
  OUT_DIR="$ROOT/$OUT_DIR"
fi
if [[ "$CSV_PREFIX" != /* ]]; then
  CSV_PREFIX="$ROOT/$CSV_PREFIX"
fi
if [[ "$NETSTATE_FILE" != /* ]]; then
  NETSTATE_FILE="$ROOT/$NETSTATE_FILE"
fi
if [[ "$COLLISION_OUTPUT_FILE" != /* ]]; then
  COLLISION_OUTPUT_FILE="$ROOT/$COLLISION_OUTPUT_FILE"
fi
if [[ "$EVENT_TIMELINE_DIR" != /* ]]; then
  EVENT_TIMELINE_DIR="$ROOT/$EVENT_TIMELINE_DIR"
fi
if [[ "$COLLISION_CAUSALITY_OUT_DIR" != /* ]]; then
  COLLISION_CAUSALITY_OUT_DIR="$ROOT/$COLLISION_CAUSALITY_OUT_DIR"
fi

NS3_DIR="$("$ROOT/scripts/ensure-ns3-dev.sh" --root "$ROOT" --ns3-dir "$NS3_DIR")"
"$ROOT/scripts/sync-overlay-into-bootstrap-ns3.sh" --root "$ROOT" --ns3-dir "$NS3_DIR"

old_out_dir="$OUT_DIR"
if ! mkdir -p "$OUT_DIR/artifacts" 2>/dev/null; then
  fallback_base="${HOME:-/tmp}/NEWWAY_runs/$(date +%F)"
  fallback_tag="$(basename "$old_out_dir")"
  OUT_DIR="$fallback_base/$fallback_tag"
  echo "Warning: cannot create OUT_DIR '$old_out_dir', fallback to '$OUT_DIR'"

  for var_name in CSV_PREFIX NETSTATE_FILE COLLISION_OUTPUT_FILE EVENT_TIMELINE_DIR COLLISION_CAUSALITY_OUT_DIR; do
    old_val="${!var_name}"
    if [[ "$old_val" == "$old_out_dir"* ]]; then
      rel="${old_val#$old_out_dir}"
      printf -v "$var_name" '%s%s' "$OUT_DIR" "$rel"
    fi
  done
  mkdir -p "$OUT_DIR/artifacts"
fi
mkdir -p "$(dirname "$CSV_PREFIX")"
cd "$NS3_DIR"

if [[ "$EUID" -eq 0 ]]; then
  NS3_USER_OVERRIDE="${NS3_USER_OVERRIDE:-ns3}"
  run_ns3() { USER="$NS3_USER_OVERRIDE" ./ns3 "$@"; }
else
  run_ns3() { ./ns3 "$@"; }
fi

CONFIG_STATE="$(run_ns3 show config 2>/dev/null | sed -r 's/\x1B\[[0-9;]*[mK]//g' || true)"
need_configure=0
if ! grep -Eq 'Examples[[:space:]]*:[[:space:]]*ON' <<<"$CONFIG_STATE"; then
  need_configure=1
fi
if [[ "$NS3_REQUIRE_OPTIMIZED" == "1" ]] && ! grep -Eq 'Build profile[[:space:]]*:[[:space:]]*optimized' <<<"$CONFIG_STATE"; then
  need_configure=1
fi
if [[ "$need_configure" -eq 1 ]]; then
  read -r -a configure_args <<< "$NS3_CONFIGURE_ARGS"
  run_ns3 configure "${configure_args[@]}"
fi

run_ns3 build -j "$JOBS" v2v-emergencyVehicleAlert-nrv2x

rm -f "$NETSTATE_FILE"
rm -f "$COLLISION_OUTPUT_FILE"
rm -f "${CSV_PREFIX}"-veh*-CAM.csv "${CSV_PREFIX}"-veh*-MSG.csv "${CSV_PREFIX}"-veh*-CTRL.csv "${CSV_PREFIX}"-veh*-PHY.csv 2>/dev/null || true

sumo_collision_args=""
if [[ -n "$COLLISION_ACTION" ]]; then
  sumo_collision_args+=" --sumo-collision-action=$COLLISION_ACTION"
  sumo_collision_args+=" --sumo-collision-check-junctions=$COLLISION_CHECK_JUNCTIONS"
fi
if [[ "$ENABLE_COLLISION_OUTPUT" == "1" ]]; then
  mkdir -p "$(dirname "$COLLISION_OUTPUT_FILE")"
  sumo_collision_args+=" --sumo-collision-output=$COLLISION_OUTPUT_FILE"
fi
if [[ -n "$COLLISION_STOPTIME_S" ]]; then
  sumo_collision_args+=" --sumo-collision-stoptime-s=$COLLISION_STOPTIME_S"
fi

RUN_CMD="v2v-emergencyVehicleAlert-nrv2x $RUN_ARGS --csv-log=$CSV_PREFIX --netstate-dump-file=$NETSTATE_FILE $sumo_collision_args"

if [[ -z "$SUMO_PORT" ]]; then
  SUMO_PORT="$((30000 + (RANDOM % 20000)))"
fi
RUN_CMD+=" --sumo-port=$SUMO_PORT"

if [[ -n "$EXTRA_ARGS" ]]; then
  RUN_CMD+=" $EXTRA_ARGS"
fi

attempt=1
while true; do
  set +e
  run_ns3 run --no-build "$RUN_CMD" > "$OUT_DIR/v2v-emergencyVehicleAlert-nrv2x.log" 2>&1
  rc=$?
  set -e
  if [[ $rc -eq 0 ]]; then
    break
  fi
  if [[ $attempt -ge $RUN_RETRIES ]] || ! grep -q "Connection refused" "$OUT_DIR/v2v-emergencyVehicleAlert-nrv2x.log"; then
    echo "Scenario failed. See $OUT_DIR/v2v-emergencyVehicleAlert-nrv2x.log"
    exit $rc
  fi
  SUMO_PORT="$((30000 + (RANDOM % 20000)))"
  RUN_CMD="$(sed -E "s/--sumo-port=[0-9]+/--sumo-port=$SUMO_PORT/" <<<"$RUN_CMD")"
  attempt=$((attempt + 1))
  sleep 2
done

PY_BIN="$ROOT/.venv/bin/python"
if [[ ! -x "$PY_BIN" ]]; then
  PY_BIN="python3"
fi

if [[ -f "$NETSTATE_FILE" ]]; then
  "$PY_BIN" "$ROOT/analysis/scenario_runs/analyze_netstate_collision_risk.py" \
    --netstate "$NETSTATE_FILE" \
    --out-dir "$OUT_DIR/artifacts/collision_risk" \
    --gap-threshold-m "$RISK_GAP_THRESHOLD" \
    --ttc-threshold-s "$RISK_TTC_THRESHOLD"
else
  echo "Warning: netstate file not found, collision risk analysis skipped: $NETSTATE_FILE"
fi

if [[ "$EVENT_TIMELINE" == "1" ]]; then
  if ! "$PY_BIN" "$ROOT/analysis/scenario_runs/build_drop_decision_timeline.py" \
    --run-dir "$OUT_DIR" \
    --out-dir "$EVENT_TIMELINE_DIR"; then
    echo "Warning: drop decision timeline generation failed for v2v-emergencyVehicleAlert-nrv2x"
  fi
fi

if [[ "$ENABLE_COLLISION_OUTPUT" == "1" ]] && [[ -f "$COLLISION_OUTPUT_FILE" ]]; then
  echo "Collision output: $COLLISION_OUTPUT_FILE"
fi

if [[ "$COLLISION_CAUSALITY" == "1" ]] && [[ -f "$COLLISION_OUTPUT_FILE" ]] && [[ -f "$EVENT_TIMELINE_DIR/event_timeline.csv" ]]; then
  causality_args=(
    --run-dir "$OUT_DIR"
    --collision-xml "$COLLISION_OUTPUT_FILE"
    --timeline-csv "$EVENT_TIMELINE_DIR/event_timeline.csv"
    --out-dir "$COLLISION_CAUSALITY_OUT_DIR"
    --window-s "$COLLISION_CAUSALITY_WINDOW_S"
  )
  if [[ -n "$COLLISION_CAUSALITY_FOCUS_VEHICLE" ]]; then
    causality_args+=(--focus-vehicle "$COLLISION_CAUSALITY_FOCUS_VEHICLE")
  fi
  if ! "$PY_BIN" "$ROOT/analysis/scenario_runs/build_collision_causality_report.py" "${causality_args[@]}"; then
    echo "Warning: collision causality report generation failed for v2v-emergencyVehicleAlert-nrv2x"
  fi
fi

if [[ "$PLOT" == "1" ]]; then
  if ! "$PY_BIN" "$ROOT/analysis/scenario_runs/make_plots.py" \
    --run-dir "$OUT_DIR" \
    --scenario "v2v-emergencyVehicleAlert-nrv2x"; then
    echo "Warning: plot generation failed for v2v-emergencyVehicleAlert-nrv2x"
  fi
fi

if [[ "$EXPORT_RESULTS" == "1" ]]; then
  export_args=(--run-dir "$OUT_DIR" --export-root "$EXPORT_ROOT")
  if [[ "$EXPORT_INCLUDE_RAW_CSV" == "1" ]]; then
    export_args+=(--include-raw-csv)
  fi
  if ! "$PY_BIN" "$ROOT/analysis/scenario_runs/export_results_bundle.py" "${export_args[@]}"; then
    echo "Warning: export bundle generation failed for v2v-emergencyVehicleAlert-nrv2x"
  fi
fi

# PHY-level metrics analysis (SINR, SNR, RSSI, RSRP)
PHY_ANALYSIS="${PHY_ANALYSIS:-1}"
if [[ "$PHY_ANALYSIS" == "1" ]]; then
  phy_csvs=("${CSV_PREFIX}"-*-PHY.csv)
  if [[ -f "${phy_csvs[0]:-}" ]]; then
    if ! "$PY_BIN" "$ROOT/analysis/scenario_runs/analyze_phy_safety.py" \
      --run-dir "$OUT_DIR" \
      --out-dir "$OUT_DIR/artifacts/phy_analysis"; then
      echo "Warning: PHY analysis failed for v2v-emergencyVehicleAlert-nrv2x"
    fi
  else
    echo "Note: No PHY CSV files found (rebuild with SignalInfo-enabled EVA to enable)"
  fi
fi

echo "Done: $OUT_DIR/v2v-emergencyVehicleAlert-nrv2x.log"
