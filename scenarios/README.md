# Scenarios

Этот каталог хранит "операционные" материалы по сценариям: как собрать, как запустить, куда смотреть артефакты.
Исходники самих сценариев остаются в стандартных местах `src/automotive/examples/` и `src/nr/examples/nr-v2x-examples/`.

## Быстрый старт

1. (Опционально) укажите уже подготовленное дерево `ns-3-dev`:

```bash
export NS3_DIR=/path/to/ns-3-dev
```

2. Запустите нужный сценарий:

```bash
scenarios/cttc-nr-v2x-demo-simple/run.sh
scenarios/nr-v2x-west-to-east-highway/run.sh
scenarios/v2v-cam-exchange-sionna-nrv2x/run.sh
scenarios/v2v-coexistence-80211p-nrv2x/run.sh
scenarios/v2v-emergencyVehicleAlert-nrv2x/run.sh
valid_scenario/run.sh
```

Общие переменные окружения:
- `NS3_DIR` — путь к `ns-3-dev`
- `OUT_DIR` — куда складывать лог/артефакты
- `PLOT=0|1` — строить ли графики после прогона (по умолчанию `1`)
- `NS3_USER_OVERRIDE` — имя пользователя для вызова `./ns3` при запуске из root-shell (по умолчанию `ns3`)
- `NS3_CONFIGURE_ARGS` — аргументы для auto-`./ns3 configure` (по умолчанию `--enable-examples --build-profile=optimized --disable-werror`)
- `NS3_REQUIRE_OPTIMIZED=0|1` — требовать ли optimized profile при auto-configure (по умолчанию `1`)
- `NS3_SYNC_OVERLAY=0|1` — синхронизировать `src/` из overlay в `.bootstrap-ns3` перед сборкой (по умолчанию `1`)
- `EXPORT_RESULTS=0|1` — дублировать результаты в `analysis/scenario_runs/chatgpt_exports/` (по умолчанию `1`)
- `EXPORT_ROOT` — корень export-папки
- `EXPORT_INCLUDE_RAW_CSV=0|1` — включать все CSV в экспортный бандл

## Автоподготовка `ns-3-dev`

Теперь `run.sh` сценариев умеют автоматически поднимать локальное рабочее дерево `ns-3-dev`, если оно не найдено:
- проверяются пути:
  - `NS3_DIR` (если задан)
  - `<repo>/ns-3-dev`
  - `<repo>/.bootstrap-ns3/repo/ns-3-dev`
- если ничего не найдено, запускается bootstrap в `<repo>/.bootstrap-ns3`.
- после обнаружения дерева `ns-3-dev`, `run.sh` проверяет конфиг и при необходимости выполняет
  `./ns3 configure` (по умолчанию: `--enable-examples --build-profile=optimized --disable-werror`),
  чтобы целевые сценарии были доступны для сборки и не падали на debug-assert в default profile.

Управляющие переменные:
- `AUTO_BOOTSTRAP_NS3=0|1` — включить/выключить авто-bootstrap (по умолчанию `1`)
- `NS3_BOOTSTRAP_FORCE=0|1` — пересоздавать bootstrap-destination (по умолчанию `0`)
- `NS3_BOOTSTRAP_COPY_SOURCE=0|1` — копировать текущий overlay (включая uncommitted изменения, без `.git`) в disposable bootstrap repo (по умолчанию `1`)

Для сценария `v2v-emergencyVehicleAlert-nrv2x`:
- есть `run_loss_sweep.sh` для baseline/lossy sweep по `--rx-drop-prob-cam`
- автоматически считается safety-прокси из SUMO netstate (`min gap`, `min TTC`, risky events)
- автоматически строится ID-aware timeline `DROP_PHY -> DECISION` по `pkt_uid`
  (`artifacts/drop_decision_timeline/*.csv|*.png`, отключение: `EVENT_TIMELINE=0`)
- доступен incident-mode (`--incident-enable=1`) для кейса "сломавшееся авто + объезд"
- есть `run_baseline_vs_lossy_visual.sh` для наглядного сравнения baseline/lossy на общей тайм-линии
- есть `run_rssi_safety_sweep.sh` для исследования зависимости RSSI/PRR от `txPower` и связи с safety-метриками
- есть `run_sionna_incident_sweep.sh` для terrain-aware incident sweep (Sionna vs non-Sionna)

Отдельный зафиксированный дипломный кейс:
- `valid_scenario/run.sh` — единый воспроизводимый запуск
  (`veh3` перестраивается, `veh4` с потерями сталкивается с `veh2`, `veh5` перестраивается позже)
- автоматически строятся story-графики SUMO+ns-3 в
  `artifacts/valid_scenario_story/` (скорости/полосы, gap/TTC, ns-3 события, event-chain)

## Где результаты

- Логи и артефакты складываются в `analysis/scenario_runs/<YYYY-MM-DD>/`.
- Базы SQLite (`.db`) и CSV-артефакты попадают в `analysis/scenario_runs/<YYYY-MM-DD>/artifacts/`.
- После каждого `run.sh` автоматически строятся графики в `analysis/scenario_runs/<YYYY-MM-DD>/figures/`.

## Для исследовательских экспериментов

- Готовый список практических сценариев/модификаций для доказательства влияния потерь на поведение:
  `scenarios/RESEARCH_SCENARIOS.md`
- Полный аудит логов по всем прогонам:
  `./.venv/bin/python analysis/scenario_runs/analyze_all_logs.py --root analysis/scenario_runs --out-dir analysis/scenario_runs`
