"""Генерация демонстрационного набора показателей (36 месяцев, 2023-01 … 2025-12).

Детерминирован (фиксированное зерно). В данные заложены сценарии для проверки анализа:
плавный рост до середины 2025 года, затем снижение выручки и прибыли при росте
дебиторской задолженности и падении денежных средств, а также два единичных выброса.
Запуск: python sample-data/generate_demo.py
"""

import csv
import math
import random
from pathlib import Path

SEED = 42
MONTHS = 36
OUTPUT = Path(__file__).with_name("demo_indicators.csv")

COLUMNS = [
    "period", "revenue", "sales_volume", "profit", "receivables", "payables",
    "inventory", "cash", "cf_operating", "cf_investing", "cf_financing",
]


def month_label(index):
    year, month = divmod(index, 12)
    return f"{2023 + year}-{month + 1:02d}"


def main():
    rng = random.Random(SEED)
    rows = []
    for t in range(MONTHS):
        seasonal = 1 + 0.06 * math.sin(2 * math.pi * t / 12)
        crisis = max(0, t - 29)
        trend = 1 + 0.012 * t - 0.035 * crisis

        revenue = 950_000 * trend * seasonal * rng.uniform(0.97, 1.03)
        sales_volume = revenue / rng.uniform(410, 430)
        margin = 0.24 - 0.012 * crisis
        profit = revenue * margin * rng.uniform(0.95, 1.05)
        receivables = revenue * (0.28 + 0.025 * crisis) * rng.uniform(0.96, 1.04)
        payables = revenue * 0.22 * rng.uniform(0.95, 1.05)
        inventory = revenue * (0.35 + 0.01 * crisis) * rng.uniform(0.96, 1.04)
        cf_operating = profit * 0.9 - 0.15 * receivables * (crisis > 0)
        cf_investing = -revenue * rng.uniform(0.03, 0.06)
        cf_financing = revenue * rng.uniform(-0.02, 0.02)
        cash = 420_000 * (1 + 0.01 * t) - 28_000 * crisis * rng.uniform(0.9, 1.1)

        if t == 14:
            inventory *= 1.6
        if t == 22:
            receivables *= 1.5

        rows.append([month_label(t)] + [round(v, 2) for v in (
            revenue, sales_volume, profit, receivables, payables,
            inventory, cash, cf_operating, cf_investing, cf_financing,
        )])

    with OUTPUT.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(COLUMNS)
        writer.writerows(rows)
    print(f"Записано {len(rows)} строк в {OUTPUT}")


if __name__ == "__main__":
    main()
