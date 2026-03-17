# CLAUDE.md — AI Assistant Guide for NEWWAY

## Project Overview

NEWWAY is an ns-3-based open-source framework for simulating ETSI-compliant V2X (Vehicle-to-Everything) communications. It integrates SUMO traffic simulation, multiple wireless standards (802.11p, LTE-V2X, NR-V2X), NVIDIA Sionna ray-tracing, and CARLA vehicle dynamics. It is the successor to ms-van3t.

**License**: GPL-2.0

## Repository Structure

```
NEWWAY/
├── src/                            # Core source modules
│   ├── automotive/                 # ETSI ITS-G5 stack: CAM, DENM, CPM, IVIM, VAM, DCC, GeoNet
│   │   ├── model/                  # Core C++ implementation
│   │   ├── helper/                 # ns-3 helper classes
│   │   ├── examples/               # Runnable example applications (22 .cc files)
│   │   ├── test/                   # Test suites
│   │   └── CMakeLists.txt          # Module build config (~3800 lines)
│   ├── nr/                         # NR-V2X (5G New Radio V2X) Mode 2
│   ├── cv2x/                       # C-V2X / LTE-V2X Mode 4
│   ├── carla/                      # CARLA simulator integration
│   ├── sionna/                     # NVIDIA Sionna ray-tracing channel model
│   ├── traci/                      # SUMO TraCI client
│   ├── traci-applications/         # Traffic control applications
│   ├── gps-tc/                     # GPS trace client (alternative to SUMO)
│   └── vehicle-visualizer/         # Web-based visualization (Node.js, Socket.IO, Leaflet)
├── scenarios/                      # Executable scenario scripts with run.sh
├── valid_scenario/                 # Reproducible thesis-grade scenario
├── analysis/                       # Post-simulation analysis and plotting tools
├── emulation-support/              # Hardware-in-the-loop (UDP/AMQP relayers)
├── docs/                           # Sphinx documentation source (ReadTheDocs)
├── docker/                         # Docker configuration
├── scripts/                        # Utility scripts
├── Makefile                        # High-level build targets
├── sandbox_builder.sh              # Bootstrap installer (creates ns-3-dev tree)
├── DEVELOPMENT.md                  # Developer bootstrap checklist
├── CHANGES.md                      # API change history
└── RELEASE_NOTES.md                # Version release notes
```

## Language & Technology Stack

| Component | Language | Notes |
|-----------|----------|-------|
| Core simulation | C++17 | ns-3 framework, GCC 8+ or Clang 10+ |
| ASN.1 messages | C | ETSI ITS message encoding (700+ definitions) |
| Build system | CMake | ns-3 CMake (replaced Waf in ns-3.36+) |
| Web visualizer | JavaScript | Node.js, Express, Socket.IO |
| Mobility/tools | Python 3 | SUMO integration, ray-tracing, build helpers |
| Emulation | C++/Python | gRPC, Protobuf |

## Build & Development

### Important: Bootstrap is Destructive

`sandbox_builder.sh` creates an `ns-3-dev/` tree and **destroys the current directory's `.git` and top-level files**. Always run in a disposable clone or use `scripts/bootstrap-disposable.sh`.

### Quick Reference (via Makefile)

```bash
make bootstrap-deps          # Bootstrap + install system dependencies
make configure               # Configure ns-3 tree
make build                   # Build all (or BUILD_TARGET=<target>)
make run RUN_TARGET=<name>   # Run a built example
make test-list               # List available test suites
make test-suite TEST_SUITE=<name>  # Run a specific test suite
```

### Manual Build Steps

```bash
# 1. Bootstrap (in disposable workspace)
printf '\n' | ./sandbox_builder.sh install-dependencies

# 2. Configure
cd ns-3-dev
./ns3 configure --build-profile=optimized --enable-examples --enable-tests --disable-python --disable-werror

# 3. Build (use -j 1 or -j 2 to avoid OOM)
./ns3 build -j 2 v2v-simple-cam-exchange-80211p

# 4. Run
./ns3 run --no-build "v2v-simple-cam-exchange-80211p"
```

### Running Tests

```bash
cd ns-3-dev
./test.py --list                        # List all test suites
./test.py --no-build --suite=<name>     # Run a specific suite
```

Note: `./ns3 test` is **not valid** in this tree. Always use `test.py`.

### Running Scenarios

```bash
./scenarios/<scenario-name>/run.sh      # Auto-bootstraps ns-3 if missing
# Results output to analysis/scenario_runs/<YYYY-MM-DD>/
```

## Code Conventions

### Naming

- **Classes**: CamelCase (`CABasicService`, `GeoNet`, `LDM`)
- **Methods**: camelCase (`setStationProperties`, `receiveCAM`)
- **Constants**: UPPER_SNAKE_CASE (`TS_MAX`, `DB_CLEANER_INTERVAL_SECONDS`)
- **Files**: CamelCase for `.h` and `.cc` files
- **Namespaces**: `ns3` is the primary namespace

### Module Layout

Every ns-3 module follows this structure:
```
src/<module>/
├── model/          # Core implementation
├── helper/         # ns-3 helper classes for user setup
├── examples/       # Runnable example applications
├── test/           # Test suites
├── doc/            # Doxygen documentation
└── CMakeLists.txt  # Module build definition
```

### Design Patterns

- **Ptr\<T\>**: ns-3 reference-counted smart pointers everywhere
- **CreateObject\<T\>()**: Factory pattern for ns-3 object creation
- **TracedCallback**: Event-driven callbacks between layers
- **SAP (Service Access Points)**: Layer-to-layer interfaces
- **VDP (Vehicle Data Provider)**: Abstraction for vehicle location/kinematics
- **BSMap**: Basic service container for simplified ETSI stack setup
- **MetricSupervisor**: KPI measurement and CSV logging

### Documentation Style

- Doxygen comments: `/** @brief ... @param ... @return ... */`
- Header guards: `#ifndef FILENAME_H` / `#define FILENAME_H` / `#endif`

### No Automated Formatting

There is no `.clang-format` or linter enforced. Follow existing file style when editing.

## Key Classes (automotive module)

| Class | Purpose | Standard |
|-------|---------|----------|
| `CABasicService` | CAM generation/reception | ETSI EN 302 637-2-1 |
| `DENBasicService` | DENM handling | ETSI EN 302 637-3 |
| `GeoNet` | GeoNetworking protocol | ETSI EN 302 636-4-1 |
| `BTP` | Basic Transport Protocol | ETSI EN 302 636-5-1 |
| `LDM` | Local Dynamic Map (vehicle database) | ETSI EN 302 895 |
| `DCC` | Decentralized Congestion Control | ETSI TS 102 687 |
| `VDP` | Vehicle Data Provider interface | — |
| `MetricSupervisor` | KPI measurement and logging | — |

## Dependencies

**Required**: ns-3 (3.35+), SUMO (1.6.0–1.18.0), CMake 3.10+, Python 3, GCC 8+/Clang 10+

**Optional**: CARLA 0.9.12, NVIDIA Sionna (0.19.0/1.0), Node.js (visualizer), gRPC 1.60.0, Boost geometry, GSL, SQLite3, OpenCV

**Supported OS**: Ubuntu 20.04/22.04 (Ubuntu 24.04 not officially supported)

## Common Pitfalls

1. **`./ns3: No such file or directory`** — `ns3` only exists after `sandbox_builder.sh` creates `ns-3-dev/`
2. **OOM during build** — Reduce parallel jobs (`-j 1`) and/or add swap
3. **SUMO version mismatch** — Stick to SUMO 1.6.0–1.18.0; newer versions may break integrations
4. **`--disable-werror` required** — On Ubuntu 22.04+ with newer GCC, warnings-as-errors will fail the build
5. **No `./ns3 test`** — Use `./test.py` instead

## AI Assistant Guidelines

- Read source files before suggesting modifications; the codebase has complex interdependencies
- Follow existing naming conventions (CamelCase classes, camelCase methods)
- Match the indentation style of the file being edited (mixed tabs/spaces, ns-3 convention)
- When adding new examples, register them in `src/automotive/CMakeLists.txt`
- New modules should follow the standard ns-3 module layout
- ASN.1 generated C files under `model/asn1/` should not be manually edited
- The `src/automotive/CMakeLists.txt` is ~3800 lines — search carefully before adding entries
- Scenario `run.sh` scripts are self-contained and auto-bootstrap; keep them portable
