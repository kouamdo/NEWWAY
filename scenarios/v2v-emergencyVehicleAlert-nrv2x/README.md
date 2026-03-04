# v2v-emergencyVehicleAlert-nrv2x

NR-V2X Mode 2 сценарий с поведенческой реакцией на экстренное ТС (`changeLane` + `setMaxSpeed`).

- Исходник: `src/automotive/examples/v2v-emergencyVehicleAlert-nrv2x.cc`
- Логика реакции на CAM/CPM: `src/automotive/model/Applications/emergencyVehicleAlert.cc`

## Что добавлено для исследования потерь

- `--rx-drop-prob-cam` и `--rx-drop-prob-cpm`:
  управляемый application-level fault injection для приема CAM/CPM.
- `--rx-drop-prob-phy-cam` и `--rx-drop-prob-phy-cpm`:
  управляемый drop до приложения (в GeoNet, до учета `MetricSupervisor::signalReceivedPacket`),
  поэтому влияет на PRR как на канальном уровне.
- `--drop-triggered-reaction-enable`:
  по умолчанию `0` (strict): на `*_DROP_PHY` пишется `drop_decision_no_action`, без маневра "по факту потери".
- `--target-loss-profile-enable=1` + `--target-loss-vehicle-id=vehX`:
  таргетированная деградация связи для одного receiver в рамках того же прогона
  (`--target-loss-rx-drop-prob-*`), чтобы получить сценарий "все объезжают, один не получает и врезается".
- `--crash-mode-min-time-s`:
  защита от раннего столкновения в начале прогона; crash-mode активируется только после указанного времени.
- Логи управления `*-CTRL.csv`:
  фиксируют моменты и типы маневров (`cam_reaction`, `cpm_reaction`, `cam_drop_reaction`, `cpm_drop_reaction`, `drop_decision_no_action`).
- CPM теперь участвует в управлении: при риске по порогам
  `--cpm-reaction-distance-m` и `--cpm-reaction-ttc-s` выполняются те же TraCI-маневры
  (`changeLane` + `setMaxSpeed`) с анти-спам интервалом `--reaction-action-cooldown-s`.
- В `*-MSG.csv` для PHY-level инжекции пишутся события `CAM_DROP_PHY` / `CPM_DROP_PHY`
  (это позволяет строить временные графики потерь не только для `CAM_DROP_APP`).
- Добавлен strict ID-aware coupling для drop-событий:
  - в `GeoNet` PHY-drop callback передаёт `pkt_uid`, `txStationId`, `msgSeq`, `btpDestPort`;
  - в `emergencyVehicleAlert` каждое `*_DROP_PHY` имеет decision-событие в `CTRL.csv`
    по тому же `pkt_uid` (`*_drop_reaction` или `drop_decision_no_action`);
  - auto-артефакт `artifacts/drop_decision_timeline/*` строит CSV/PNG `DROP_PHY -> DECISION`.
- Incident-mode для "сломавшегося" автомобиля:
  - `--incident-enable=1`
  - `--incident-vehicle-id=<vehX>`
  - `--incident-time-s=<t>`
  - `--incident-stop-duration-s=<sec>`
  - `--incident-setstop-enable=0|1` (`0` = удерживать на месте без `setStop`, полезно для детерминированного ДТП-сценария)
  - `--incident-recover-max-speed-mps=<v>` (отрицательное значение = восстановить исходную скорость)

## Запуск одного прогона

```bash
scenarios/v2v-emergencyVehicleAlert-nrv2x/run.sh
```

Если нужен зафиксированный дипломный кейс одной командой (с подкапотными story-графиками SUMO+ns-3), используйте:

```bash
valid_scenario/run.sh
```

Пример "один плохой receiver в одной сцене" (SUMO GUI + collision remove + доказуемые drop->decision):

```bash
PLOT=0 EXPORT_RESULTS=0 EVENT_TIMELINE=1 ENABLE_COLLISION_OUTPUT=1 COLLISION_ACTION=remove COLLISION_CAUSALITY=1 COLLISION_CAUSALITY_FOCUS_VEHICLE=veh4 \
RUN_ARGS="--sumo-gui=1 --sim-time=40 --met-sup=1 --penetrationRate=1 --sumo-config=src/automotive/examples/sumo_files_v2v_map/map_incident_showcase.sumo.cfg --incident-enable=1 --incident-vehicle-id=veh2 --incident-time-s=6 --incident-stop-duration-s=20 --cam-reaction-target-lane=1 --cam-reaction-distance-m=45 --cpm-reaction-distance-m=30 --cpm-reaction-ttc-s=2.0 --drop-triggered-reaction-enable=0 --rx-drop-prob-phy-cam=0 --rx-drop-prob-phy-cpm=0 --target-loss-profile-enable=1 --target-loss-vehicle-id=veh4 --target-loss-rx-drop-prob-phy-cam=1.0 --target-loss-rx-drop-prob-phy-cpm=1.0 --crash-mode-enable=1 --crash-mode-vehicle-id=veh4 --crash-mode-no-action-threshold=10 --crash-mode-force-speed-mps=30 --crash-mode-duration-s=6 --crash-mode-min-time-s=6" \
scenarios/v2v-emergencyVehicleAlert-nrv2x/run.sh
```

Файлы showcase-потока:
- `src/automotive/examples/sumo_files_v2v_map/cars_incident_showcase.rou.xml`
- `src/automotive/examples/sumo_files_v2v_map/map_incident_showcase.sumo.cfg`

Пример под задачу "3 машины в полосе грузовика, 1-я перестраивается, 2-я (lossy) врезается и машины не исчезают":

```bash
PLOT=0 EXPORT_RESULTS=0 EVENT_TIMELINE=1 ENABLE_COLLISION_OUTPUT=1 \
COLLISION_ACTION=warn COLLISION_STOPTIME_S=1000 \
COLLISION_CAUSALITY=1 COLLISION_CAUSALITY_FOCUS_VEHICLE=veh4 \
RUN_ARGS="--sumo-gui=1 --sim-time=40 --met-sup=1 --penetrationRate=1 --sumo-config=src/automotive/examples/sumo_files_v2v_map/map_incident_threeflow.sumo.cfg --incident-enable=1 --incident-vehicle-id=veh2 --incident-time-s=6 --incident-stop-duration-s=20 --incident-setstop-enable=0 --cam-reaction-target-lane=1 --cam-reaction-distance-m=22 --reaction-force-lane-change-enable=1 --cpm-reaction-distance-m=0 --cpm-reaction-ttc-s=0 --drop-triggered-reaction-enable=0 --rx-drop-prob-phy-cam=0 --rx-drop-prob-phy-cpm=0 --target-loss-profile-enable=1 --target-loss-vehicle-id=veh4 --target-loss-rx-drop-prob-phy-cam=1.0 --target-loss-rx-drop-prob-phy-cpm=1.0 --crash-mode-enable=1 --crash-mode-vehicle-id=veh4 --crash-mode-no-action-threshold=10 --crash-mode-force-speed-mps=30 --crash-mode-duration-s=6 --crash-mode-min-time-s=6" \
scenarios/v2v-emergencyVehicleAlert-nrv2x/run.sh
```

Файлы three-flow демонстрации:
- `src/automotive/examples/sumo_files_v2v_map/cars_incident_threeflow.rou.xml`
- `src/automotive/examples/sumo_files_v2v_map/map_incident_threeflow.sumo.cfg`

## Event timeline для диплома (`pkt_uid`)

`run.sh` теперь автоматически строит timeline в `artifacts/drop_decision_timeline/`.
Для ручной пересборки по готовому прогону:

```bash
./.venv/bin/python analysis/scenario_runs/build_drop_decision_timeline.py \
  --run-dir analysis/scenario_runs/<YYYY-MM-DD>/<run_dir>
```

## Локальный запуск в Docker (Ubuntu + GPU)

Для быстрого развёртывания на чистой Ubuntu есть готовая обвязка:

```bash
scripts/docker-run-eva-sionna.sh
```

Для "одной команды" (установка Docker/toolkit + сборка + первый прогон):

```bash
scripts/quickstart-ubuntu-gpu.sh
```

Детальные шаги установки Docker/NVIDIA toolkit и дополнительные команды:
`docs/DOCKER_UBUNTU_GPU.md`.

По умолчанию:
- `--sumo-gui=0 --sim-time=40 --met-sup=1`
- включен `--netstate-dump-file` и анализ safety-прокси (`min gap`, `min TTC`, risky events)
- строятся графики

Полезные env-переменные:
- `RUN_ARGS` — доп. аргументы сценария
- `EXTRA_ARGS` — добавка к `RUN_ARGS`
- `CSV_PREFIX` — префикс CSV артефактов
- `NETSTATE_FILE` — путь к netstate XML
- `RISK_GAP_THRESHOLD`, `RISK_TTC_THRESHOLD` — пороги risky events
- `ENABLE_COLLISION_OUTPUT=0|1` — включить SUMO collision-output (`artifacts/eva-collision.xml`)
- `COLLISION_ACTION` — действие SUMO при collision (`warn`/`remove`/`teleport`)
- `COLLISION_CHECK_JUNCTIONS=0|1` — проверять collisions на junction (по умолчанию `1`)
- `COLLISION_STOPTIME_S=<sec>` — `collision.stoptime`; при `warn` позволяет держать столкнувшиеся авто на дороге (например, `1000`)
  Примечание: теперь collision-параметры работают и при `--sumo-config=...` (через TraCI additional options).
- `EXPORT_RESULTS=0|1` — дублировать результаты в export-папку
- `EXPORT_ROOT` — корень export-папки (по умолчанию `analysis/scenario_runs/chatgpt_exports`)
- `EXPORT_INCLUDE_RAW_CSV=0|1` — включать все CSV (может быть много файлов)
- `EVENT_TIMELINE=0|1` — строить `DROP_PHY -> DECISION` timeline (по умолчанию `1`)
- `EVENT_TIMELINE_DIR` — каталог для timeline артефактов
- `COLLISION_CAUSALITY=0|1` — строить causal report `loss -> no_action -> collision`
- `COLLISION_CAUSALITY_WINDOW_S` — lookback-окно перед collision (секунды)
- `COLLISION_CAUSALITY_FOCUS_VEHICLE=vehX` — фильтр collider по ID

## Sweep baseline vs lossy

```bash
scenarios/v2v-emergencyVehicleAlert-nrv2x/run_loss_sweep.sh
```

По умолчанию sweep по `LOSS_PROBS="0.0 0.3 0.6"`.
По умолчанию incident-mode включен через `INCIDENT_ARGS` в `run_loss_sweep.sh`.

Выбор слоя инжекции:
- `DROP_LAYER=app` (по умолчанию): использует `--rx-drop-prob-cam`
- `DROP_LAYER=phy`: использует `--rx-drop-prob-phy-cam`
- `DROP_LAYER=both`: использует оба

## Baseline vs lossy с общей тайм-линией

```bash
scenarios/v2v-emergencyVehicleAlert-nrv2x/run_baseline_vs_lossy_visual.sh
```

Скрипт:
- запускает baseline и lossy с одинаковым `RngRun`;
- строит сравнительный таймлайн:
  - `comparison/comparison_timeline.png`
  - `comparison/comparison_timeline.csv`
  - `comparison/comparison_summary.csv`
- `COMMON_EXTRA_ARGS` позволяет передать общие CLI-аргументы в оба прогона
  (например, `--sumo-config=/abs/path/aggressive.sumo.cfg`)
- для PHY-сценария доступны:
  - `BASE_DROP_PHY_CAM`, `LOSSY_DROP_PHY_CAM`
  - `BASE_DROP_PHY_CPM`, `LOSSY_DROP_PHY_CPM`

## RSSI -> safety sweep

```bash
scenarios/v2v-emergencyVehicleAlert-nrv2x/run_rssi_safety_sweep.sh
```

Для каждой точки `txPower` скрипт:
- запускает `v2v-cam-exchange-sionna-nrv2x` (без Sionna) и берет `RSSI/SNR/PRR`;
- запускает `v2v-emergencyVehicleAlert-nrv2x` и берет safety-метрики;
- строит:
  - `rssi_safety_summary.csv`
  - `rssi_safety_summary.png`
- `CAM_EXTRA_ARGS` / `EVA_EXTRA_ARGS` позволяют добавить общие аргументы для CAM/EVA прогонов

## Incident sweep c Sionna (terrain-aware channel)

```bash
scenarios/v2v-emergencyVehicleAlert-nrv2x/run_sionna_incident_sweep.sh
```

Скрипт:
- проверяет Python-зависимости `tensorflow/sionna/mitsuba/grpc`;
- поднимает локальный `sionna_v1_server_script.py`;
- запускает `v2v-emergencyVehicleAlert-nrv2x` с `--sionna=1` по сетке `TX_POWERS`;
- опционально добавляет контрольную ветку `non_sionna` (`COMPARE_NON_SIONNA=1`);
- строит:
  - `sionna_incident_summary.csv`
  - `sionna_incident_summary.png`

## Что сохраняется

- Лог: `analysis/scenario_runs/<date>/.../v2v-emergencyVehicleAlert-nrv2x.log`
- CSV по каждому ТС:
  - `*-CAM.csv`
  - `*-MSG.csv`
  - `*-CTRL.csv`
- Safety-прокси:
  - `artifacts/collision_risk/collision_risk_summary.csv`
  - `artifacts/collision_risk/collision_risk_timeseries.csv`
  - `artifacts/collision_risk/collision_risk_timeseries.png`
  - (опционально) `artifacts/eva-collision.xml` при `ENABLE_COLLISION_OUTPUT=1`
- ID-aware timeline:
  - `artifacts/drop_decision_timeline/event_timeline.csv`
  - `artifacts/drop_decision_timeline/summary.csv`
  - `artifacts/drop_decision_timeline/decision_delay_scatter.png`
  - `artifacts/drop_decision_timeline/decision_type_counts.png`
- Collision causality:
  - `artifacts/collision_causality/collision_causality.csv`
  - `artifacts/collision_causality/collision_causality.md`
- Графики сценария:
  - `figures/v2v-emergencyVehicleAlert-nrv2x/*.png`
- Для sweep:
  - `loss_sweep_summary.csv`
  - `loss_sweep_summary.png`
  - `loss_sweep_behavior_timing.png` (first/P90 control-action time, [s])
- Экспорт для загрузки в внешние инструменты:
  - `analysis/scenario_runs/chatgpt_exports/<run_path>/`
  - `EXPORT_MANIFEST.csv` внутри export-папки
