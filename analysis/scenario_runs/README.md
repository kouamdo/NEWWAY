# Scenario Runs

Каталог для воспроизводимых прогонов сценариев.

- Каждая дата хранится в отдельной папке: `analysis/scenario_runs/<YYYY-MM-DD>/`
- Внутри:
  - `*.log` — stdout/stderr конкретных запусков
  - `artifacts/` — SQLite/CSV и дополнительные выходные файлы сценариев
  - `figures/` — автоматически сгенерированные графики по сценариям
  - `run_summary.csv` — агрегированные KPI по запущенным сценариям
  - `REPORT.md` — интерпретация результатов под исследовательскую задачу

## Полезные утилиты

- `analysis/scenario_runs/make_plots.py` — построение графиков из `artifacts/`.
- `analysis/scenario_runs/analyze_netstate_collision_risk.py` — safety-прокси (`min gap`, `min TTC`, risky events) из SUMO `netstate`.
- `analysis/scenario_runs/compare_incident_baseline_loss.py` — сравнительный baseline/lossy таймлайн (drop ratio, control actions, gap/TTC, collisions).
- `analysis/scenario_runs/build_drop_decision_timeline.py` — ID-aware timeline по `pkt_uid`: `DROP_PHY -> DECISION` (+ `event_timeline.csv`, `summary.csv`, PNG).
- `analysis/scenario_runs/build_collision_causality_report.py` — causal audit `DROP/NO_ACTION -> COLLISION` по `eva-collision.xml` + timeline.
- `analysis/scenario_runs/build_valid_scenario_story_plots.py` — дипломные story-графики для валидированного EVA-кейса (SUMO + ns-3 на одной временной оси).
- `analysis/scenario_runs/analyze_all_logs.py` — полный аудит логов по `analysis/scenario_runs/*` в единый `log_audit_summary_<date>.csv` и `LOG_AUDIT_<date>.md`.
- `analysis/scenario_runs/export_results_bundle.py` — дублирование графиков/логов/summary в компактный export-бандл.
- `scenarios/v2v-emergencyVehicleAlert-nrv2x/run_loss_sweep.sh` — готовый sweep baseline/lossy для сценария с реакцией на экстренное авто.

Для построения графиков нужен `matplotlib` (в этом репозитории используется `./.venv/bin/python`).

## Быстрые команды

```bash
# 1) Сгенерировать timeline drop->decision для одного прогона
./.venv/bin/python analysis/scenario_runs/build_drop_decision_timeline.py \
  --run-dir analysis/scenario_runs/<YYYY-MM-DD>/<run_dir>

# 2) Построить story-графики по валидированному кейсу
./.venv/bin/python analysis/scenario_runs/build_valid_scenario_story_plots.py \
  --run-dir analysis/scenario_runs/<YYYY-MM-DD>/<run_dir>

# 3) Полный аудит логов по всем прогонам
./.venv/bin/python analysis/scenario_runs/analyze_all_logs.py \
  --root analysis/scenario_runs \
  --out-dir analysis/scenario_runs \
  --tag 2026-02-27
```

## Export-папка для выгрузки

- По умолчанию `run.sh` сценариев и `run_loss_sweep.sh` создают дубликат результатов в:
  `analysis/scenario_runs/chatgpt_exports/<relative_run_path>/`
- Внутри лежит `EXPORT_MANIFEST.csv` со списком выгруженных файлов.
- Отключение: `EXPORT_RESULTS=0`.
