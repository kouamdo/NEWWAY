#!/usr/bin/env bash
set -euo pipefail

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  cat <<'EOF'
Usage:
  analysis/mode2_loss/start_carla_ready.sh [NS3_DIR]

Environment overrides:
  CARLA_PORT=3000
  CARLA_TOWN=Town06
  CARLA_FORCE_OFFSCREEN=1
  CARLA_PREFER_NVIDIA=0
  CARLA_EXTRA_ARGS="..."
  CARLA_READY_MAX_WAIT_SEC=240
EOF
  exit 0
fi

NS3_DIR="${1:-$(pwd)}"
CARLA_PORT="${CARLA_PORT:-3000}"
CARLA_TOWN="${CARLA_TOWN:-Town06}"
CARLA_FORCE_OFFSCREEN="${CARLA_FORCE_OFFSCREEN:-1}"
CARLA_PREFER_NVIDIA="${CARLA_PREFER_NVIDIA:-0}"
CARLA_EXTRA_ARGS="${CARLA_EXTRA_ARGS:-}"
CARLA_READY_MAX_WAIT_SEC="${CARLA_READY_MAX_WAIT_SEC:-240}"
CONF_FILE="$NS3_DIR/CARLA-OpenCDA.conf"

if [[ ! -f "$CONF_FILE" ]]; then
  echo "ERROR: Missing $CONF_FILE" >&2
  exit 1
fi

CARLA_HOME="$( (grep -E '^CARLA_HOME=' "$CONF_FILE" || true) | head -n1 | cut -d= -f2-)"
PYTHON_INTERPRETER_RAW="$( (grep -E '^Python_Interpreter=' "$CONF_FILE" || true) | head -n1 | cut -d= -f2-)"

if [[ -z "$CARLA_HOME" || ! -d "$CARLA_HOME" ]]; then
  echo "ERROR: CARLA_HOME is invalid in $CONF_FILE: $CARLA_HOME" >&2
  exit 1
fi

if [[ -x "$PYTHON_INTERPRETER_RAW" ]]; then
  PYTHON_BIN="$PYTHON_INTERPRETER_RAW"
elif command -v "$PYTHON_INTERPRETER_RAW" >/dev/null 2>&1; then
  PYTHON_BIN="$(command -v "$PYTHON_INTERPRETER_RAW")"
else
  echo "ERROR: Python_Interpreter is invalid in $CONF_FILE: $PYTHON_INTERPRETER_RAW" >&2
  exit 1
fi

CARLA_CMD=(./CarlaUE4.sh "-carla-port=${CARLA_PORT}")
if [[ "$CARLA_FORCE_OFFSCREEN" == "1" ]]; then
  CARLA_CMD+=("-RenderOffScreen")
fi
if [[ "$CARLA_PREFER_NVIDIA" == "1" ]]; then
  CARLA_CMD+=("-prefernvidia")
fi
if [[ -n "$CARLA_EXTRA_ARGS" ]]; then
  read -r -a EXTRA_ARGS_ARR <<< "$CARLA_EXTRA_ARGS"
  CARLA_CMD+=("${EXTRA_ARGS_ARR[@]}")
fi

echo "Starting CARLA: ${CARLA_CMD[*]}"
pkill -f 'CarlaUE4-Linux-Shipping' >/dev/null 2>&1 || true
sleep 1
(
  cd "$CARLA_HOME"
  nohup "${CARLA_CMD[@]}" >/tmp/carla_output.txt 2>&1 < /dev/null &
  echo $! >/tmp/carla_ready_launcher.pid
)
CARLA_LAUNCHER_PID="$(cat /tmp/carla_ready_launcher.pid)"
rm -f /tmp/carla_ready_launcher.pid
echo "CARLA launcher PID: $CARLA_LAUNCHER_PID"

start_ts="$(date +%s)"
while true; do
  now_ts="$(date +%s)"
  elapsed=$((now_ts - start_ts))
  if (( elapsed > CARLA_READY_MAX_WAIT_SEC )); then
    echo "ERROR: CARLA did not become ready in ${CARLA_READY_MAX_WAIT_SEC}s" >&2
    tail -n 40 /tmp/carla_output.txt || true
    kill "$CARLA_LAUNCHER_PID" >/dev/null 2>&1 || true
    exit 1
  fi

  if CARLA_PORT="$CARLA_PORT" CARLA_TOWN="$CARLA_TOWN" "$PYTHON_BIN" - <<'PY'
import carla
import os

port = int(os.environ["CARLA_PORT"])
town = os.environ["CARLA_TOWN"]

client = carla.Client("localhost", port)
client.set_timeout(10.0)
client.get_server_version()
client.get_world()
client.set_timeout(120.0)
w = client.load_world(town)
print(f"CARLA ready on port {port}. Loaded {w.get_map().name}")
PY
  then
    echo "CARLA warm-up complete."
    exit 0
  fi

  echo "Waiting for CARLA warm-up... (${elapsed}s)"
  sleep 5
done
