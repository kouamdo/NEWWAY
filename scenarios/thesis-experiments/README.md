# Thesis Experiments: Impact of 5G NR Message Loss on Connected & Autonomous Vehicles

## Research Question

**Исследование влияния потерь сообщений в 5G NR на поведение подключённого и беспилотного транспорта**

_Investigation of the impact of 5G NR message losses on the behavior of connected and autonomous vehicles._

## Experiment Suite

### Experiment 1: Intersection Collision (`run_experiment_1_intersection.sh`)

**Scenario:** 4-way signalized intersection. An autonomous vehicle (veh_s1) approaching from the south relies on CAM messages from cross-traffic (west→east) to detect approaching vehicles. Under 5G NR message loss, the AV becomes "blind" to cross-traffic → T-bone collision.

**Swept variable:** PHY-level CAM drop probability (0%, 30%, 60%, 90%, 100%)

**Key question:** At what loss rate does the AV fail to yield and collide?

### Experiment 2: Platoon Emergency Braking (`run_experiment_2_platoon.sh`)

**Scenario:** 6-vehicle platoon on a 3-lane highway. The leader performs emergency braking at t=10s. Followers use CAM for cooperative adaptive cruise control (CACC). Under message loss, rear vehicles react too late → pile-up.

**Swept variable:** PHY-level CAM drop probability on tail follower (0%–100%)

**Key question:** How much loss triggers a chain collision in the platoon?

### Experiment 3: 5G NR Physical Layer Parameters (`run_experiment_3_nr_params.sh`)

**Scenario:** Same proven highway incident, but instead of artificial loss injection, we vary **real NR parameters** and let the PHY layer determine natural packet loss.

**Swept variables:**
- (a) txPower: 5, 10, 15, 20, 23 dBm
- (b) MCS: 2, 5, 10, 14, 20, 28
- (c) Numerology μ: 0, 1, 2, 3

**Key question:** Which NR parameters cause safety-critical message loss?

### Experiment 4: Vehicle Density Impact (`run_experiment_4_density.sh`)

**Scenario:** Same road, same incident, but with 7, 12, 60, and 120 vehicles. More vehicles = more NR Mode 2 resource collisions = worse PRR.

**Key question:** At what density does NR-V2X channel congestion degrade safety?

### Experiment 5: Technology Comparison (`run_experiment_5_tech_comparison.sh`)

**Scenario:** Identical traffic conditions for 802.11p (legacy WAVE) and NR-V2X (5G). Same loss injection for fair comparison.

**Key question:** Which technology provides better safety under message loss?

## How to Run

```bash
# Run all experiments (headless, no SUMO GUI)
./scenarios/thesis-experiments/run_all.sh

# Run specific experiments
RUN_EXP="1 3" ./scenarios/thesis-experiments/run_all.sh

# With SUMO visualization
SUMO_GUI=1 ./scenarios/thesis-experiments/run_all.sh

# Override simulation time
SIM_TIME=60 ./scenarios/thesis-experiments/run_all.sh

# Run single experiment
./scenarios/thesis-experiments/run_experiment_1_intersection.sh
```

## Output Structure

```
analysis/scenario_runs/<date>/
├── thesis-exp1-intersection/
│   ├── loss_0p0/        # Baseline (0% loss)
│   ├── loss_0p3/        # 30% loss
│   ├── loss_0p6/        # 60% loss
│   ├── ...
│   ├── exp1_intersection_summary.csv
│   └── exp1_intersection_sweep.png
├── thesis-exp2-platoon/
│   └── ...
├── thesis-exp3-nr-params/
│   ├── txpower_5dBm/
│   ├── txpower_23dBm/
│   ├── mcs_2/
│   ├── mcs_28/
│   ├── exp3a_txpower_sweep.csv
│   ├── exp3b_mcs_sweep.csv
│   └── exp3c_numerology_sweep.csv
├── thesis-exp4-density/
│   └── ...
├── thesis-exp5-tech-comparison/
│   └── ...
└── thesis-unified-report/
    ├── THESIS_REPORT_<date>.md    # Publication-ready Markdown report
    ├── thesis_overview.png         # Multi-experiment summary figure
    └── master_log.txt
```

## Metrics Collected

| Category | Metric | Description |
|----------|--------|-------------|
| Network | PRR (%) | Packet Reception Ratio |
| Network | Latency (ms) | Average message delivery delay |
| Safety | Min TTC (s) | Minimum Time-to-Collision |
| Safety | Min Gap (m) | Minimum inter-vehicle distance |
| Safety | Collisions | Number of collision events |
| Safety | Risky TTC events | TTC below 1.5s threshold |
| Safety | Risky gap events | Gap below 2.0m threshold |
| Behavioral | Reaction delay (s) | Time from event to evasive action |
| Causal | DROP→NO_ACTION chain | PHY drop linked to behavioral failure |

## CAVISE Integration Note

CAVISE (https://github.com/CAVISE/) uses OMNeT++ (Artery) for network simulation, not ns-3. Direct integration with NEWWAY's 5G NR stack is not feasible without reimplementing the NR models in OMNeT++. For 5G NR V2X research, NEWWAY with ns-3 remains the more suitable platform.

## CARLA Integration

The existing `v2v-carlaMobility-nrv2x.cc` example supports CARLA as a mobility backend instead of SUMO. To visualize realistic 3D crashes (vs. SUMO's 2D birdseye), you can:

1. Install CARLA 0.9.12 + OpenCDA
2. Configure `CARLA-OpenCDA.conf` with paths
3. Adapt the thesis scenarios to use CARLA mobility

Note: CARLA adds visual realism but requires significant setup (GPU, dependencies). The SUMO-based experiments provide the same quantitative safety metrics.
