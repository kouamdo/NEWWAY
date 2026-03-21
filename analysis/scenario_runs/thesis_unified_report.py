#!/usr/bin/env python3
"""
Thesis Unified Report Generator.

Collects all experiment results and generates:
1. A unified summary table (CSV + Markdown)
2. A multi-experiment comparison figure
3. A thesis conclusions summary

Usage:
  python thesis_unified_report.py --report-dir <path> --date <YYYY-MM-DD>
"""
import argparse
import csv
import glob
import os
import sys
from datetime import datetime

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    HAS_MPL = True
except ImportError:
    HAS_MPL = False


def read_csv_safe(path):
    rows = []
    if not os.path.isfile(path):
        return rows
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            converted = {}
            for k, v in row.items():
                try:
                    converted[k] = float(v)
                except (ValueError, TypeError):
                    converted[k] = v
            rows.append(converted)
    return rows


def generate_markdown_report(report_dir, date_tag, all_data):
    """Generate thesis-ready Markdown report."""
    md_path = os.path.join(report_dir, f"THESIS_REPORT_{date_tag}.md")

    with open(md_path, "w") as f:
        f.write(f"# Результаты экспериментов магистерской ВКР\n\n")
        f.write(f"**Тема:** Исследование влияния потерь сообщений в 5G NR на поведение подключённого и беспилотного транспорта\n\n")
        f.write(f"**Дата проведения:** {date_tag}\n\n")
        f.write(f"**Платформа:** NEWWAY (ns-3 + SUMO + NR-V2X Mode 2)\n\n")
        f.write("---\n\n")

        # Experiment 1
        f.write("## Эксперимент 1: Столкновение на перекрёстке\n\n")
        f.write("**Сценарий:** 4-стороннее регулируемое пересечение, автономное ТС (veh_s1) полагается на CAM от поперечного потока.\n\n")
        f.write("**Гипотеза:** При потере CAM-сообщений автономное ТС не обнаружит поперечный транспорт и произойдёт T-bone столкновение.\n\n")
        exp1 = all_data.get("exp1_intersection_summary", [])
        if exp1:
            f.write("| Вероятность потерь | PRR (%) | Задержка (мс) | Мин. TTC (с) | Столкновения |\n")
            f.write("|---|---|---|---|---|\n")
            for r in exp1:
                f.write(f"| {r.get('loss_prob','?')} | {r.get('prr_percent','N/A')} | {r.get('avg_latency_ms','N/A')} | {r.get('min_ttc_s','N/A')} | {r.get('collisions','0')} |\n")
            f.write("\n")
        else:
            f.write("*Данные не найдены. Запустите эксперимент 1.*\n\n")

        # Experiment 2
        f.write("## Эксперимент 2: Экстренное торможение в колонне\n\n")
        f.write("**Сценарий:** Колонна из 6 ТС на автомагистрали, лидер экстренно останавливается. Замыкающие полагаются на CAM для координированного торможения.\n\n")
        f.write("**Гипотеза:** Потеря CAM-сообщений вызывает цепное столкновение в хвосте колонны.\n\n")
        exp2 = all_data.get("exp2_platoon_summary", [])
        if exp2:
            f.write("| Вероятность потерь | PRR (%) | Задержка (мс) | Мин. TTC (с) | Мин. дист. (м) | Столкновения |\n")
            f.write("|---|---|---|---|---|---|\n")
            for r in exp2:
                f.write(f"| {r.get('loss_prob','?')} | {r.get('prr_percent','N/A')} | {r.get('avg_latency_ms','N/A')} | {r.get('min_ttc_s','N/A')} | {r.get('min_gap_m','N/A')} | {r.get('collisions','0')} |\n")
            f.write("\n")
        else:
            f.write("*Данные не найдены. Запустите эксперимент 2.*\n\n")

        # Experiment 3
        f.write("## Эксперимент 3: Влияние параметров физического уровня 5G NR\n\n")
        f.write("**Сценарий:** Тот же инцидент на шоссе, но потери вызваны реальными параметрами NR (мощность, MCS, нумерология).\n\n")
        f.write("**Ключевой вывод:** Это центральный эксперимент, связывающий параметры 5G NR с безопасностью.\n\n")

        for sweep_name, sweep_title in [
            ("exp3a_txpower_sweep", "3a: Мощность передатчика (txPower)"),
            ("exp3b_mcs_sweep", "3b: Схема модуляции и кодирования (MCS)"),
            ("exp3c_numerology_sweep", "3c: Нумерология (μ)"),
        ]:
            exp3 = all_data.get(sweep_name, [])
            f.write(f"### {sweep_title}\n\n")
            if exp3:
                headers = list(exp3[0].keys())
                f.write("| " + " | ".join(headers) + " |\n")
                f.write("|" + "|".join(["---"] * len(headers)) + "|\n")
                for r in exp3:
                    f.write("| " + " | ".join(str(r.get(h, "N/A")) for h in headers) + " |\n")
                f.write("\n")
            else:
                f.write("*Данные не найдены.*\n\n")

        # Experiment 4
        f.write("## Эксперимент 4: Влияние плотности транспортного потока\n\n")
        f.write("**Сценарий:** Одна и та же дорожная ситуация с 7, 12, 60, 120 ТС.\n\n")
        f.write("**Гипотеза:** С ростом плотности ресурсные коллизии в NR увеличиваются, PRR падает, безопасность ухудшается.\n\n")
        exp4 = all_data.get("exp4_density_summary", [])
        if exp4:
            f.write("| Кол-во ТС | PRR (%) | Задержка (мс) | Мин. TTC (с) | Столкновения |\n")
            f.write("|---|---|---|---|---|\n")
            for r in exp4:
                f.write(f"| {r.get('vehicle_count','?')} | {r.get('prr_percent','N/A')} | {r.get('avg_latency_ms','N/A')} | {r.get('min_ttc_s','N/A')} | {r.get('collisions','0')} |\n")
            f.write("\n")
        else:
            f.write("*Данные не найдены. Запустите эксперимент 4.*\n\n")

        # Experiment 5
        f.write("## Эксперимент 5: Сравнение 802.11p и NR-V2X\n\n")
        f.write("**Сценарий:** Идентичная дорожная ситуация, одинаковые уровни потерь для обеих технологий.\n\n")
        exp5 = all_data.get("exp5_tech_comparison", [])
        if exp5:
            f.write("| Технология | Потери | PRR (%) | Задержка (мс) | Мин. TTC (с) | Столкновения |\n")
            f.write("|---|---|---|---|---|---|\n")
            for r in exp5:
                f.write(f"| {r.get('technology','?')} | {r.get('loss_prob','?')} | {r.get('prr_percent','N/A')} | {r.get('avg_latency_ms','N/A')} | {r.get('min_ttc_s','N/A')} | {r.get('collisions','0')} |\n")
            f.write("\n")
        else:
            f.write("*Данные не найдены. Запустите эксперимент 5.*\n\n")

        # Conclusions template
        f.write("---\n\n")
        f.write("## Выводы\n\n")
        f.write("1. **Перекрёсток (Эксп. 1):** Потеря CAM-сообщений > X% приводит к T-bone столкновениям на регулируемом перекрёстке.\n\n")
        f.write("2. **Колонна (Эксп. 2):** При потере > X% CAM замыкающие ТС в колонне не успевают затормозить, цепное столкновение.\n\n")
        f.write("3. **Параметры NR (Эксп. 3):** txPower < X дБм и MCS > Y вызывают естественные потери, приводящие к опасным ситуациям.\n\n")
        f.write("4. **Плотность (Эксп. 4):** При > X ТС ресурсные коллизии NR Mode 2 снижают PRR до критического уровня.\n\n")
        f.write("5. **Сравнение (Эксп. 5):** NR-V2X vs 802.11p — [заполнить по результатам].\n\n")
        f.write("---\n\n")
        f.write(f"*Отчёт сгенерирован автоматически: {datetime.now().isoformat()}*\n")

    print(f"Markdown report: {md_path}")
    return md_path


def generate_overview_figure(report_dir, all_data):
    """Generate a single overview figure summarizing all experiments."""
    if not HAS_MPL:
        return

    # Try to create a summary figure with key findings from each experiment
    fig, axes = plt.subplots(2, 3, figsize=(20, 12))
    fig.suptitle(
        "Влияние потерь 5G NR на безопасность транспорта — обзор всех экспериментов",
        fontsize=16, fontweight="bold"
    )

    exp_configs = [
        ("exp1_intersection_summary", "loss_prob", "Эксп. 1: Перекрёсток", axes[0, 0]),
        ("exp2_platoon_summary", "loss_prob", "Эксп. 2: Колонна", axes[0, 1]),
        ("exp3a_txpower_sweep", "txPower_dBm", "Эксп. 3a: txPower", axes[0, 2]),
        ("exp3b_mcs_sweep", "mcs", "Эксп. 3b: MCS", axes[1, 0]),
        ("exp4_density_summary", "vehicle_count", "Эксп. 4: Плотность", axes[1, 1]),
    ]

    for exp_name, x_key, title, ax in exp_configs:
        rows = all_data.get(exp_name, [])
        if not rows:
            ax.text(0.5, 0.5, "Нет данных", ha="center", va="center",
                    transform=ax.transAxes, fontsize=14)
            ax.set_title(title, fontsize=12)
            continue

        x_vals, prr_vals, coll_vals = [], [], []
        for r in rows:
            xv = r.get(x_key)
            pv = r.get("prr_percent")
            cv = r.get("collisions")
            if xv is not None and xv != "N/A":
                try:
                    x_vals.append(float(xv))
                    prr_vals.append(float(pv) if pv not in (None, "N/A") else None)
                    coll_vals.append(float(cv) if cv not in (None, "N/A") else None)
                except (ValueError, TypeError):
                    pass

        if x_vals:
            ax2 = ax.twinx()
            # PRR line
            valid_prr = [(x, p) for x, p in zip(x_vals, prr_vals) if p is not None]
            if valid_prr:
                xs, ps = zip(*valid_prr)
                ax.plot(xs, ps, "o-", color="#2196F3", linewidth=2, markersize=7, label="PRR")
            ax.set_ylabel("PRR (%)", color="#2196F3", fontsize=10)
            ax.set_ylim(bottom=0)

            # Collision bars
            valid_coll = [(x, c) for x, c in zip(x_vals, coll_vals) if c is not None]
            if valid_coll:
                xs, cs = zip(*valid_coll)
                ax2.bar(xs, cs, alpha=0.3, color="#F44336", width=0.05 * max(xs) if max(xs) > 0 else 0.1, label="Столкновения")
            ax2.set_ylabel("Столкновения", color="#F44336", fontsize=10)

        ax.set_title(title, fontsize=12, fontweight="bold")
        ax.grid(True, alpha=0.2)

    # Experiment 5: technology comparison
    ax5 = axes[1, 2]
    exp5 = all_data.get("exp5_tech_comparison", [])
    if exp5:
        techs = sorted(set(r.get("technology", "") for r in exp5))
        colors = {"NR-V2X": "#2196F3", "80211p": "#FF9800", "nrv2x": "#2196F3"}
        for tech in techs:
            tech_rows = [r for r in exp5 if r.get("technology") == tech]
            x = [r.get("loss_prob") for r in tech_rows]
            y = [r.get("prr_percent") for r in tech_rows]
            valid = [(xi, yi) for xi, yi in zip(x, y)
                     if xi is not None and yi is not None and xi != "N/A" and yi != "N/A"]
            if valid:
                xs, ys = zip(*valid)
                ax5.plot(xs, ys, "o-", color=colors.get(tech, "#666"), linewidth=2,
                         markersize=7, label=tech)
        ax5.legend(fontsize=9)
        ax5.set_ylabel("PRR (%)", fontsize=10)
        ax5.set_ylim(bottom=0)
    else:
        ax5.text(0.5, 0.5, "Нет данных", ha="center", va="center",
                 transform=ax5.transAxes, fontsize=14)
    ax5.set_title("Эксп. 5: NR-V2X vs 802.11p", fontsize=12, fontweight="bold")
    ax5.grid(True, alpha=0.2)

    plt.tight_layout(rect=[0, 0, 1, 0.94])
    out_path = os.path.join(report_dir, "thesis_overview.png")
    fig.savefig(out_path, dpi=200, bbox_inches="tight")
    plt.close(fig)
    print(f"Overview figure: {out_path}")


def main():
    parser = argparse.ArgumentParser(description="Thesis unified report generator")
    parser.add_argument("--report-dir", required=True)
    parser.add_argument("--date", required=True)
    args = parser.parse_args()

    # Collect all CSVs
    all_data = {}
    for csv_path in glob.glob(os.path.join(args.report_dir, "*.csv")):
        name = os.path.splitext(os.path.basename(csv_path))[0]
        all_data[name] = read_csv_safe(csv_path)

    # Also scan sibling experiment directories
    parent = os.path.dirname(args.report_dir)
    for exp_dir in glob.glob(os.path.join(parent, "thesis-exp*")):
        for csv_path in glob.glob(os.path.join(exp_dir, "exp*.csv")):
            name = os.path.splitext(os.path.basename(csv_path))[0]
            if name not in all_data:
                all_data[name] = read_csv_safe(csv_path)

    print(f"Found data for: {list(all_data.keys())}")

    # Generate report
    generate_markdown_report(args.report_dir, args.date, all_data)
    generate_overview_figure(args.report_dir, all_data)


if __name__ == "__main__":
    main()
