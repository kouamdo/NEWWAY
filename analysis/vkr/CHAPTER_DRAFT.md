# Черновик глав ВКР (версия 0.1)

## Глава 1. Введение (черновик)

Подключенный и беспилотный транспорт опирается на своевременный обмен V2X-сообщениями для кооперативного восприятия и координации маневров. Для NR-V2X Mode 2 sidelink, где распределение радиоресурсов выполняется децентрализованно, потери сообщений могут возникать даже при приемлемых средних сетевых KPI из-за локальной конкуренции, коллизий и неблагоприятных радиоусловий. В таких условиях возникает риск расхождения между «средней» оценкой качества связи и фактическим влиянием на поведение транспортных средств.

Цель работы состоит в исследовании того, как потери сообщений в 5G NR Mode 2 влияют на поведенческие реакции подключенного и беспилотного транспорта, и в формировании набора метрик, позволяющих корректно оценивать этот эффект.

Гипотеза работы: при росте потерь сообщений деградация поведения (задержка реакции, сокращение числа корректирующих действий) может быть существенной даже тогда, когда усредненные PRR/latency меняются слабо.

## Глава 3. Методика экспериментов (черновик)

Экспериментальный стенд реализован в ns-3/ms-van3t с интеграцией SUMO. Использованы пять сценариев, покрывающих разные уровни сложности: от минимальной валидации канала Mode 2 (`cttc-nr-v2x-demo-simple`) до traffic-aware и behavior-aware сценариев (`nr-v2x-west-to-east-highway`, `v2v-emergencyVehicleAlert-nrv2x`).

Ключевой сценарий для цели ВКР — `v2v-emergencyVehicleAlert-nrv2x`, расширенный incident-mode:
- принудительная остановка `incident_vehicle` через TraCI,
- sweep потерь CAM `rx-drop-prob-cam in {0.0, 0.4, 0.8}`,
- сбор как сетевых KPI, так и поведенческих KPI.

Сетевые KPI:
- Average PRR [-],
- Average latency [ms],
- per-node PRR распределения,
- overlap ratio [-], TB fail ratio [-] (для highway).

Поведенческие KPI:
- число управляющих реакций `control_actions` [count],
- времена реакций `first/p50/p90 control action` [s],
- surrogate safety: `min gap` [m], `min TTC` [s], risky events [count].

Критерий подтверждения гипотезы: монотонная или квази-монотонная связь между ростом потерь CAM и ухудшением поведенческих KPI при отсутствии сопоставимого изменения усредненных PRR/latency.

## Глава 4. Результаты и обсуждение (черновик)

По incident-sweep (`analysis/scenario_runs/2026-02-19/batch-main-161949/eva-loss-sweep-incident-v2/loss_sweep_summary.csv`) получено:
- observed CAM drop ratio: `0.000 -> 0.406 -> 0.802`;
- control actions: `99 -> 58 -> 13`;
- first control action: `3.84 s -> 4.33 s -> 11.93 s`.

При этом Average PRR (`~0.959`) и Average latency (`~12.3 ms`) почти не изменяются. Следовательно, для оценки влияния потерь на поведение автономного транспорта недостаточно усредненных communication KPI: требуется behavior-aware анализ.

Отдельно, в highway-сценарии зафиксированы `overlap ratio = 0.0547` и `TB fail ratio = 0.0316`, что подтверждает механизм возникновения потерь в нагрузочных условиях Mode 2.

Текущая конфигурация SUMO не привела к критическим событиям по surrogate safety (`risky_gap_events=0`, `risky_ttc_events=0`), поэтому для демонстрации «loss -> авария» нужен более конфликтный дорожный кейс. Однако уже на текущем наборе данных влияние потерь сообщений на поведение (реакции и их тайминг) подтверждено количественно.

### Дополнительный подтверждающий эксперимент (baseline vs lossy PHY)

В конфликтном platoon-кейсе (`analysis/scenario_runs/2026-02-21/eva-platoon-collision-proof3-131815`) выполнено прямое сравнение:
- `baseline`: `rx-drop-prob-phy-cam=0.0`;
- `lossy`: `rx-drop-prob-phy-cam=0.95`.

Получено:
- Average PRR: `0.901954 -> 0.624577`;
- CAM PHY drops (суммарно по узлам): `0 -> 10618`;
- суммарные control actions: `590 -> 32`;
- min TTC: `3.196 s -> 2.897 s`.

При пороге опасного сближения `TTC < 3.1 s`:
- baseline: `risky_ttc_events = 0`,
- lossy: `risky_ttc_events = 2`
(`analysis/scenario_runs/2026-02-21/eva-platoon-collision-proof3-131815/*/artifacts/collision_risk_ttc_3p1/collision_risk_summary.csv`).

Итог: в данном кейсе подтвержден переход в **опасное состояние** (safety-threshold crossing) при PHY-потерях CAM. Физические столкновения по `collision-output` не зафиксированы (`0/0`), поэтому на текущем этапе доказательство относится к уровню surrogate safety, а не к факту удара.

### Валидированный причинный сценарий «loss -> collision» (для демонстрации в ВКР)

Для закрытия требования по физическому ДТП реализован и зафиксирован отдельный воспроизводимый пакет:
- `valid_scenario/run.sh`
- `valid_scenario/README.md`

Сценарная постановка:
- в полосе инцидента движутся `veh3`, `veh4`, `veh5` за `veh2`;
- `veh2` принудительно останавливается в момент `t=6 s`;
- `veh4` получает таргетированные PHY-потери (`CAM/CPM=1.0`), strict mode: `drop_decision_no_action`;
- `veh3` и `veh5` не имеют таргетированных потерь и выполняют lane-change;
- `collision.action=warn` и `collision.stoptime=1000` удерживают столкнувшиеся авто на дороге.

На валидационном прогоне (`analysis/scenario_runs/2026-03-04/verify-threeflow-force-lc`):
- `veh3` впервые перестраивается в `t=7.14358 s` (`eva-veh3-CTRL.csv`);
- collision `veh4 -> veh2` фиксируется в `t=7.90 s` (`artifacts/eva-collision.xml`);
- `veh5` впервые перестраивается в `t=10.1341 s` (`eva-veh5-CTRL.csv`);
- causal report (`artifacts/collision_causality/collision_causality.csv`) для collider `veh4`:
  `causal_evidence = strong_no_action_only`, `missing_decision_events = 0`.

Таким образом, в этом кейсе получено не только surrogate safety, но и **факт физического столкновения** с пакетным доказательством причинной цепочки `DROP_PHY(pkt_uid) -> drop_decision_no_action -> COLLISION`.

Для визуального и количественного анализа «под капотом» автоматически строятся дипломные графики:
- `artifacts/valid_scenario_story/speed_lane_timeseries.png`;
- `artifacts/valid_scenario_story/gap_ttc_timeseries.png`;
- `artifacts/valid_scenario_story/ns3_events_per_second.png`;
- `artifacts/valid_scenario_story/event_chain_timeline.png` + `event_chain.csv`.
