#!/usr/bin/env bash
set -euo pipefail

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  cat <<'EOF'
Usage:
  analysis/mode2_loss/run_carla_sionna_nrv2x.sh [NS3_DIR]

Environment overrides:
  SIM_TIME=20s                  ns-3 simTime argument (default: 20s)
  OPENCDA_CONFIG=ms_van3t_example
  SUMO_HOME=/usr/share/sumo      SUMO root (must contain tools/)
  CARLA_FORCE_OFFSCREEN=1        force CARLA -RenderOffScreen (auto=1 on WSL)
  CARLA_PREFER_NVIDIA=0          pass -prefernvidia to CARLA launcher
  CARLA_EXTRA_ARGS="..."         extra args passed to CarlaUE4.sh by ns-3
  CARLA_MANUAL=0                 1 = do not auto-start CARLA in ns-3
  OPENCDA_MANUAL=0               1 = do not auto-start OpenCDA in ns-3
  OPENCDA_CARLA_CLIENT_TIMEOUT_SEC=180
                                 CARLA client timeout used by OpenCDA
  OPENCDA_CARLA_LOAD_WORLD_RETRIES=1
                                 retries for CARLA load_world in OpenCDA
  SCENE_XML=<path>              Sionna XML scenario
  SIONNA_PYTHON=<path/python>   Python for Sionna server (default: python3)
  SIONNA_PORT=8103
  SIONNA_GPU=0                  0=CPU only, 1=use first GPU, N=use GPUs [0..N-1]
  SIONNA_MI_VARIANT=<variant>   Mitsuba variant (default for GPU=0: llvm_ad_mono_polarized)
  SIONNA_VERBOSE=1              1 enables verbose logs
EOF
  exit 0
fi

NS3_DIR="${1:-$(pwd)}"
SIM_TIME="${SIM_TIME:-20s}"
OPENCDA_CONFIG="${OPENCDA_CONFIG:-ms_van3t_example}"
SCENE_XML="${SCENE_XML:-$NS3_DIR/src/sionna/scenarios/SionnaCircleScenario/scene.xml}"
SIONNA_PYTHON_RAW="${SIONNA_PYTHON:-python3}"
SIONNA_PORT="${SIONNA_PORT:-8103}"
SIONNA_GPU="${SIONNA_GPU:-0}"
SIONNA_VERBOSE="${SIONNA_VERBOSE:-1}"
SIONNA_MI_VARIANT="${SIONNA_MI_VARIANT:-}"
CARLA_FORCE_OFFSCREEN="${CARLA_FORCE_OFFSCREEN:-}"
CARLA_PREFER_NVIDIA="${CARLA_PREFER_NVIDIA:-0}"
OPENCDA_CARLA_CLIENT_TIMEOUT_SEC="${OPENCDA_CARLA_CLIENT_TIMEOUT_SEC:-180}"
OPENCDA_CARLA_LOAD_WORLD_RETRIES="${OPENCDA_CARLA_LOAD_WORLD_RETRIES:-1}"

CONF_FILE="$NS3_DIR/CARLA-OpenCDA.conf"
SIONNA_SCRIPT="$NS3_DIR/src/sionna/sionna_v1_server_script.py"
CARLA_BINARY="$NS3_DIR/build/src/automotive/examples/ns3-dev-v2v-carla-nrv2x-optimized"

if [[ ! -d "$NS3_DIR" ]]; then
  echo "ERROR: NS3_DIR does not exist: $NS3_DIR" >&2
  exit 1
fi

if [[ ! -f "$CONF_FILE" ]]; then
  cat <<EOF >&2
ERROR: Missing config file: $CONF_FILE
Create it with:
  CARLA_HOME=/path/to/CARLA_0.9.12
  OpenCDA_HOME=/path/to/OpenCDA
  Python_Interpreter=/path/to/python3.7_or_conda_env_python
Or run (interactive):
  cd $NS3_DIR && ./switch_ms-van3t-CARLA.sh
EOF
  exit 1
fi

CARLA_HOME="$( (grep -E '^CARLA_HOME=' "$CONF_FILE" || true) | head -n1 | cut -d= -f2-)"
OPENCDA_HOME="$( (grep -E '^OpenCDA_HOME=' "$CONF_FILE" || true) | head -n1 | cut -d= -f2-)"
PYTHON_INTERPRETER_RAW="$( (grep -E '^Python_Interpreter=' "$CONF_FILE" || true) | head -n1 | cut -d= -f2-)"

if [[ -z "$CARLA_HOME" || -z "$OPENCDA_HOME" || -z "$PYTHON_INTERPRETER_RAW" ]]; then
  echo "ERROR: CARLA-OpenCDA.conf must define CARLA_HOME, OpenCDA_HOME, Python_Interpreter" >&2
  exit 1
fi

if [[ ! -d "$CARLA_HOME" ]]; then
  echo "ERROR: CARLA_HOME does not exist: $CARLA_HOME" >&2
  exit 1
fi

if [[ ! -d "$OPENCDA_HOME" ]]; then
  echo "ERROR: OpenCDA_HOME does not exist: $OPENCDA_HOME" >&2
  exit 1
fi

if [[ -x "$PYTHON_INTERPRETER_RAW" ]]; then
  PYTHON_BIN="$PYTHON_INTERPRETER_RAW"
else
  if command -v "$PYTHON_INTERPRETER_RAW" >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v "$PYTHON_INTERPRETER_RAW")"
  else
    echo "ERROR: Python_Interpreter from conf is not executable: $PYTHON_INTERPRETER_RAW" >&2
    exit 1
  fi
fi

if [[ -x "$SIONNA_PYTHON_RAW" ]]; then
  SIONNA_PYTHON_BIN="$SIONNA_PYTHON_RAW"
else
  if command -v "$SIONNA_PYTHON_RAW" >/dev/null 2>&1; then
    SIONNA_PYTHON_BIN="$(command -v "$SIONNA_PYTHON_RAW")"
  else
    echo "ERROR: SIONNA_PYTHON is not executable: $SIONNA_PYTHON_RAW" >&2
    exit 1
  fi
fi

if [[ ! -f "$SCENE_XML" ]]; then
  echo "ERROR: Sionna scene XML not found: $SCENE_XML" >&2
  exit 1
fi

if [[ ! -f "$SIONNA_SCRIPT" ]]; then
  echo "ERROR: Sionna server script not found: $SIONNA_SCRIPT" >&2
  exit 1
fi

if [[ ! -f "$OPENCDA_HOME/opencda.py" ]]; then
  echo "ERROR: OpenCDA entrypoint not found: $OPENCDA_HOME/opencda.py" >&2
  exit 1
fi

if [[ -z "$CARLA_FORCE_OFFSCREEN" ]]; then
  if grep -qiE "(microsoft|wsl)" /proc/version 2>/dev/null; then
    CARLA_FORCE_OFFSCREEN="1"
  else
    CARLA_FORCE_OFFSCREEN="0"
  fi
fi
export CARLA_FORCE_OFFSCREEN
export CARLA_PREFER_NVIDIA
export OPENCDA_CARLA_CLIENT_TIMEOUT_SEC
export OPENCDA_CARLA_LOAD_WORLD_RETRIES
echo "CARLA_FORCE_OFFSCREEN: $CARLA_FORCE_OFFSCREEN"
echo "CARLA_PREFER_NVIDIA: $CARLA_PREFER_NVIDIA"
echo "OPENCDA_CARLA_CLIENT_TIMEOUT_SEC: $OPENCDA_CARLA_CLIENT_TIMEOUT_SEC"
echo "OPENCDA_CARLA_LOAD_WORLD_RETRIES: $OPENCDA_CARLA_LOAD_WORLD_RETRIES"

# OpenCDA requires SUMO tools on PYTHONPATH.
if [[ -z "${SUMO_HOME:-}" ]]; then
  for candidate in /usr/share/sumo /usr/local/share/sumo /opt/sumo; do
    if [[ -d "$candidate/tools" ]]; then
      SUMO_HOME="$candidate"
      break
    fi
  done
fi
if [[ -z "${SUMO_HOME:-}" || ! -d "$SUMO_HOME/tools" ]]; then
  echo "ERROR: SUMO_HOME is not set (or invalid)." >&2
  echo "Set SUMO_HOME to your SUMO root, e.g.: export SUMO_HOME=/usr/share/sumo" >&2
  exit 1
fi
export SUMO_HOME
export PYTHONPATH="$SUMO_HOME/tools${PYTHONPATH:+:${PYTHONPATH}}"
echo "SUMO_HOME: $SUMO_HOME"

echo "OpenCDA Python: $PYTHON_BIN"
if ! "$PYTHON_BIN" - <<'PY'; then
import importlib.util, sys
required = ("carla", "grpc", "psutil", "omegaconf")
missing = [m for m in required if importlib.util.find_spec(m) is None]
if missing:
    print("MISSING_OPENCDA_MODULES=" + ",".join(missing))
    sys.exit(2)
print("OpenCDA deps OK: carla + grpc + psutil + omegaconf")
PY
  echo "ERROR: Missing OpenCDA modules in '$PYTHON_BIN'." >&2
  echo "Example:" >&2
  echo "  $PYTHON_BIN -m pip install carla==0.9.12 grpcio grpcio-tools pyzmq psutil omegaconf" >&2
  exit 1
fi

# Fail fast if the selected OpenCDA scenario cannot be imported.
if ! (
  cd "$OPENCDA_HOME" && OPENCDA_TEST_SCENARIO="$OPENCDA_CONFIG" "$PYTHON_BIN" - <<'PY'
import importlib
import os
scenario = os.environ["OPENCDA_TEST_SCENARIO"]
importlib.import_module(f"opencda.scenario_testing.{scenario}")
print(f"OpenCDA scenario import OK: {scenario}")
PY
); then
  echo "ERROR: OpenCDA scenario import failed for '$OPENCDA_CONFIG'." >&2
  echo "Run this command for details:" >&2
  echo "  cd $OPENCDA_HOME && OPENCDA_TEST_SCENARIO=$OPENCDA_CONFIG $PYTHON_BIN -c 'import importlib,os; importlib.import_module(\"opencda.scenario_testing.\" + os.environ[\"OPENCDA_TEST_SCENARIO\"])'" >&2
  exit 1
fi

echo "Sionna Python: $SIONNA_PYTHON_BIN"
if ! "$SIONNA_PYTHON_BIN" - <<'PY'; then
import importlib.util, sys
required = ("tensorflow", "sionna")
missing = [m for m in required if importlib.util.find_spec(m) is None]
if missing:
    print("MISSING_SIONNA_MODULES=" + ",".join(missing))
    sys.exit(2)
print("Sionna deps OK: tensorflow + sionna")
PY
  echo "ERROR: Missing Sionna modules in '$SIONNA_PYTHON_BIN'." >&2
  echo "Example:" >&2
  echo "  $SIONNA_PYTHON_BIN -m pip install tensorflow sionna grpcio" >&2
  exit 1
fi

if [[ ! -x "$CARLA_BINARY" ]]; then
  echo "CARLA target binary missing, building v2v-carla-nrv2x..."
  (
    cd "$NS3_DIR/cmake-cache"
    cmake --build . -j 2 --target v2v-carla-nrv2x
  )
fi

echo "Starting Sionna server..."
SIONNA_CMD=("$SIONNA_PYTHON_BIN" "$SIONNA_SCRIPT" "--path-to-xml-scenario" "$SCENE_XML" "--local-machine" "--port" "$SIONNA_PORT" "--gpu" "$SIONNA_GPU")
if [[ "$SIONNA_VERBOSE" == "1" ]]; then
  SIONNA_CMD+=("--verbose")
fi

# TensorFlow pip CUDA wheels place shared libs in site-packages/nvidia/*/lib.
# Expose those paths (plus WSL's /usr/lib/wsl/lib) before starting Sionna.
SIONNA_SITE_PACKAGES="$("$SIONNA_PYTHON_BIN" - <<'PY'
import site
paths = [p for p in site.getsitepackages() if p.endswith("site-packages")]
print(paths[0] if paths else "")
PY
)"
EXTRA_LD_PATHS="/usr/lib/wsl/lib"
if [[ -n "$SIONNA_SITE_PACKAGES" && -d "$SIONNA_SITE_PACKAGES/nvidia" ]]; then
  while IFS= read -r libdir; do
    EXTRA_LD_PATHS="${EXTRA_LD_PATHS}:${libdir}"
  done < <(find "$SIONNA_SITE_PACKAGES/nvidia" -maxdepth 2 -type d -name lib | sort)
fi
export LD_LIBRARY_PATH="${EXTRA_LD_PATHS}${LD_LIBRARY_PATH:+:${LD_LIBRARY_PATH}}"

if [[ -z "$SIONNA_MI_VARIANT" ]]; then
  if [[ "$SIONNA_GPU" == "0" ]]; then
    SIONNA_MI_VARIANT="llvm_ad_mono_polarized"
  else
    # Prefer CUDA Mitsuba backend on GPU runs when OptiX symbol is available.
    OPTIX_STATUS="$("$SIONNA_PYTHON_BIN" - <<'PY'
import ctypes
try:
    lib = ctypes.CDLL("libnvoptix.so.1")
    getattr(lib, "optixQueryFunctionTable")
    print("ok")
except Exception:
    print("missing")
PY
)"
    if [[ "$OPTIX_STATUS" == "ok" ]]; then
      SIONNA_MI_VARIANT="cuda_ad_mono_polarized"
      export DRJIT_LIBOPTIX_PATH="/usr/lib/wsl/lib/libnvoptix.so.1"
    else
      echo "OptiX is not available in this WSL setup; falling back to CPU Mitsuba variant."
      SIONNA_MI_VARIANT="llvm_ad_mono_polarized"
    fi
  fi
fi
if [[ -n "$SIONNA_MI_VARIANT" ]]; then
  export SIONNA_MI_VARIANT
fi

"${SIONNA_CMD[@]}" &
SIONNA_PID=$!

cleanup() {
  if kill -0 "$SIONNA_PID" >/dev/null 2>&1; then
    kill "$SIONNA_PID" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

sleep 3

echo "Running ns-3 CARLA+Sionna scenario..."
(
  cd "$NS3_DIR"
  "$CARLA_BINARY" \
    "--simTime=$SIM_TIME" \
    "--opencda-config=$OPENCDA_CONFIG" \
    "--sionna=true" \
    "--sionna-server-ip=127.0.0.1" \
    "--sionna-local-machine=true" \
    "--sionna-verbose=true"
)
