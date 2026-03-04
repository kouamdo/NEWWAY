# valid_scenario

Валидированный сценарий для диплома/ВКР: доказуемый **bidirectional coupling ns-3 <-> SUMO**.

## Цель сценария

В одном прогоне получить причинно-связанную цепочку:

1. `veh3` (без потерь) получает предупреждения и перестраивается в безопасную полосу.
2. `veh4` (таргетно lossy receiver) получает `DROP_PHY -> drop_decision_no_action` и сталкивается с `veh2`.
3. `veh2` и `veh4` после столкновения **не исчезают** (формируют место ДТП/затор).
4. `veh5` (без потерь) позже перестраивается, обходя образовавшееся препятствие.

## Как запустить

Из корня репозитория:

```bash
valid_scenario/run.sh
```

Live GUI:

```bash
SUMO_GUI=1 valid_scenario/run.sh
```

Headless:

```bash
SUMO_GUI=0 valid_scenario/run.sh
```

Куда пишутся результаты по умолчанию:

- `$HOME/NEWWAY_runs/<YYYY-MM-DD>/valid_scenario`

## Что именно фиксируется параметрами

- `--sumo-config=.../map_incident_threeflow.sumo.cfg`
  - 3 машины позади инцидентного `veh2` в его полосе (`veh3`,`veh4`,`veh5`)
- `--target-loss-profile-enable=1 --target-loss-vehicle-id=veh4`
  - только `veh4` получает жесткие PHY потери (`CAM/CPM = 1.0`)
- `--drop-triggered-reaction-enable=0`
  - strict режим: drop-события не вызывают «скрытый» маневр, только `drop_decision_no_action`
- `--incident-setstop-enable=0`
  - инцидент удерживается на месте без `setStop`-сдвига вперед по маршруту
- `--reaction-force-lane-change-enable=1`
  - детерминирует lane-change по реакции
- `COLLISION_ACTION=warn` + `COLLISION_STOPTIME_S=1000`
  - столкнувшиеся авто остаются на дороге

## Артефакты для доказательства

После запуска формируются:

- `artifacts/eva-collision.xml` — факты столкновений в SUMO
- `artifacts/drop_decision_timeline/*` — ID-aware `pkt_uid: DROP_PHY -> DECISION`
- `artifacts/collision_causality/*` — causal report `loss -> no_action -> collision`
- `artifacts/valid_scenario_story/*` — дипломные графики «под капотом»

## Подкапотные графики (автоматически)

`valid_scenario/run.sh` вызывает:

- `analysis/scenario_runs/build_valid_scenario_story_plots.py`

и строит:

- `speed_lane_timeseries.png` — скорости/полосы `veh2..veh5`
- `gap_ttc_timeseries.png` — динамика gap/TTC для пар `veh4->veh2`, `veh5->veh4`
- `ns3_events_per_second.png` — DROP_PHY, no_action и lane-change решения по времени
- `event_chain_timeline.png` — сводная шкала `incident -> lane change -> collision -> lane change`
- `event_chain.csv` — та же шкала в табличной форме

## Для текста ВКР

Готовый расширенный текст сценария: `valid_scenario/VKR_SCENARIO_TEXT.md`.
