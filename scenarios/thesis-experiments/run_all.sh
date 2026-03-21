#!/usr/bin/env bash
# ============================================================================
# MASTER RUNNER: All 5 Thesis Experiments
# ============================================================================
# Thesis: "Исследование влияния потерь сообщений в 5G NR на поведение
#           подключенного и беспилотного транспорта"
#
# Experiments:
#   1. Intersection collision under 5G NR message loss
#   2. Platoon emergency braking under 5G NR message loss
#   3. Impact of 5G NR PHY parameters (txPower, MCS, numerology) on safety
#   4. Vehicle density impact on 5G NR channel and safety
#   5. 802.11p vs NR-V2X technology comparison
#
# Usage:
#   ./run_all.sh                    # Run all experiments
#   RUN_EXP="1 3" ./run_all.sh     # Run only experiments 1 and 3
#   SUMO_GUI=1 ./run_all.sh        # With SUMO visualization
#   SIM_TIME=60 ./run_all.sh       # Override simulation time
#
# Output: analysis/scenario_runs/<date>/thesis-<expN>/
# Final:  analysis/scenario_runs/<date>/thesis-unified-report/
# ============================================================================
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DATE_TAG="$(date +%F)"

export SUMO_GUI="${SUMO_GUI:-0}"
export SIM_TIME="${SIM_TIME:-40}"

RUN_EXP="${RUN_EXP:-1 2 3 4 5}"

echo "================================================================"
echo " THESIS EXPERIMENT SUITE"
echo " Date: $DATE_TAG"
echo " Experiments to run: $RUN_EXP"
echo " SIM_TIME=$SIM_TIME  SUMO_GUI=$SUMO_GUI"
echo "================================================================"
echo ""

REPORT_DIR="$ROOT/analysis/scenario_runs/$DATE_TAG/thesis-unified-report"
mkdir -p "$REPORT_DIR"

MASTER_LOG="$REPORT_DIR/master_log.txt"
: > "$MASTER_LOG"

log() {
  echo "$@" | tee -a "$MASTER_LOG"
}

TOTAL_START=$(date +%s)
RESULTS=()

for exp in $RUN_EXP; do
  script="$SCRIPT_DIR/run_experiment_${exp}_*.sh"
  # Expand glob
  script_files=( $script )
  if [[ ${#script_files[@]} -eq 0 || ! -f "${script_files[0]}" ]]; then
    log "SKIP: Experiment $exp script not found"
    continue
  fi
  script_file="${script_files[0]}"

  log ""
  log "============================================"
  log " STARTING EXPERIMENT $exp: $(basename "$script_file")"
  log " $(date)"
  log "============================================"

  EXP_START=$(date +%s)

  if bash "$script_file" 2>&1 | tee -a "$MASTER_LOG"; then
    status="PASS"
  else
    status="FAIL"
  fi

  EXP_END=$(date +%s)
  EXP_DURATION=$(( EXP_END - EXP_START ))

  log "Experiment $exp: $status (${EXP_DURATION}s)"
  RESULTS+=("Exp$exp: $status (${EXP_DURATION}s)")
done

TOTAL_END=$(date +%s)
TOTAL_DURATION=$(( TOTAL_END - TOTAL_START ))

log ""
log "================================================================"
log " THESIS EXPERIMENT SUITE COMPLETE"
log " Total time: ${TOTAL_DURATION}s"
log "================================================================"
for r in "${RESULTS[@]}"; do
  log "  $r"
done
log ""

# Collect all summary CSVs into unified report
log "Collecting summary CSVs..."
for f in "$ROOT/analysis/scenario_runs/$DATE_TAG"/thesis-exp*/exp*_summary.csv \
         "$ROOT/analysis/scenario_runs/$DATE_TAG"/thesis-exp*/exp*_sweep.csv \
         "$ROOT/analysis/scenario_runs/$DATE_TAG"/thesis-exp*/exp*_comparison.csv; do
  if [[ -f "$f" ]]; then
    cp "$f" "$REPORT_DIR/"
    log "  Collected: $(basename "$f")"
  fi
done

# Generate unified thesis plots
PY_BIN="$ROOT/.venv/bin/python"
if [[ ! -x "$PY_BIN" ]]; then PY_BIN="python3"; fi

if command -v "$PY_BIN" &>/dev/null; then
  "$PY_BIN" "$ROOT/analysis/scenario_runs/thesis_unified_report.py" \
    --report-dir "$REPORT_DIR" \
    --date "$DATE_TAG" 2>/dev/null || log "Unified report generation skipped (script not found or error)"
fi

log ""
log "Unified report: $REPORT_DIR"
log "Master log: $MASTER_LOG"
