"""Формирование PDF-отчёта на сервере. Кириллица — через TTF (Noto/DejaVu/Arial)."""

from datetime import UTC, datetime
from pathlib import Path

from fpdf import FPDF

from app.schemas.analysis import AnalysisResults
from app.services.assessment_labels import ASSESSMENT_DISCLAIMER, ASSESSMENT_METHOD

FONT_CANDIDATES = [
    Path(__file__).resolve().parents[1] / "assets" / "fonts" / "NotoSans-Regular.ttf",
    Path(__file__).resolve().parents[1] / "assets" / "fonts" / "DejaVuSans.ttf",
    Path("C:/Windows/Fonts/arial.ttf"),
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    Path("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"),
]
BOLD_CANDIDATES = [
    Path(__file__).resolve().parents[1] / "assets" / "fonts" / "NotoSans-Bold.ttf",
    Path(__file__).resolve().parents[1] / "assets" / "fonts" / "DejaVuSans-Bold.ttf",
    Path("C:/Windows/Fonts/arialbd.ttf"),
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    Path("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"),
]


def resolve_font() -> tuple[Path, Path]:
    regular = next((path for path in FONT_CANDIDATES if path.is_file()), None)
    if regular is None:
        raise FileNotFoundError(
            "Не найден TTF-шрифт с кириллицей. Положите NotoSans-Regular.ttf в backend/app/assets/fonts/"
        )
    bold = next((path for path in BOLD_CANDIDATES if path.is_file()), regular)
    return regular, bold


class ReportPDF(FPDF):
    def __init__(self):
        super().__init__(format="A4", unit="mm")
        self.set_auto_page_break(auto=True, margin=18)
        regular, bold = resolve_font()
        self.add_font("Report", "", str(regular))
        self.add_font("Report", "B", str(bold))
        self.set_margins(16, 16, 16)

    def header(self):
        self.set_font("Report", "", 9)
        self.set_text_color(120, 130, 140)
        stamp = datetime.now(UTC).strftime("%d.%m.%Y UTC")
        self.cell(0, 8, f"Crisis Control · аналитический отчёт · {stamp}", new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(232, 237, 242)
        y = self.get_y()
        self.line(16, y, 194, y)
        self.ln(4)

    def footer(self):
        self.set_y(-12)
        self.set_font("Report", "", 8)
        self.set_text_color(120, 130, 140)
        self.cell(0, 8, f"{self.page_no()}/{{nb}}", align="C")


def _write(pdf: ReportPDF, text: str, *, size: int = 10, bold: bool = False, color=(27, 36, 48), h: float = 5.2):
    pdf.set_font("Report", "B" if bold else "", size)
    pdf.set_text_color(*color)
    pdf.multi_cell(0, h, text or "—", new_x="LMARGIN", new_y="NEXT")


def _heading(pdf: ReportPDF, text: str):
    pdf.ln(2)
    _write(pdf, text, size=13, bold=True, h=7)


def _body(pdf: ReportPDF, text: str):
    _write(pdf, text, size=10, h=5.2)
    pdf.ln(1)


def _muted(pdf: ReportPDF, text: str):
    _write(pdf, text, size=9, color=(123, 135, 148), h=4.8)
    pdf.ln(1)


def _table(pdf: ReportPDF, headers: list[str], rows: list[list[str]], widths: list[float] | None = None):
    if not rows:
        _muted(pdf, "Нет данных для таблицы.")
        return
    usable = 178
    widths = widths or [usable / len(headers)] * len(headers)
    pdf.set_font("Report", "B", 8)
    pdf.set_fill_color(247, 248, 250)
    pdf.set_text_color(123, 135, 148)
    for header, width in zip(headers, widths, strict=True):
        pdf.cell(width, 7, header, border=0, fill=True)
    pdf.ln()
    pdf.set_font("Report", "", 8)
    pdf.set_text_color(27, 36, 48)
    for index, row in enumerate(rows):
        if pdf.get_y() > 270:
            pdf.add_page()
        fill = index % 2 == 1
        if fill:
            pdf.set_fill_color(252, 253, 253)
        for value, width in zip(row, widths, strict=True):
            pdf.cell(width, 6, (value or "—")[:42], border=0, fill=fill)
        pdf.ln()
    pdf.ln(2)


def build_pdf(results: AnalysisResults, *, organization_name: str, dataset_name: str,
              quality: dict | None = None) -> bytes:
    run = results.run
    pdf = ReportPDF()
    pdf.alias_nb_pages()
    pdf.add_page()

    _write(pdf, "Crisis Control", size=18, bold=True, h=9)
    _write(pdf, "Отчёт по результатам аналитического исследования", size=12, h=6)
    pdf.ln(2)
    _body(pdf, f"Организация: {organization_name}")
    _body(pdf, f"Исследование №{run.id}. Набор: {dataset_name}.")
    _body(pdf, f"Анализируемый период: {run.period_from} — {run.period_to}.")
    _body(pdf, f"Дата проведения: {run.created_at}. Дата формирования отчёта: {datetime.now(UTC).date()}.")
    _muted(pdf, ASSESSMENT_DISCLAIMER)

    _heading(pdf, "1. Общая информация")
    names = ", ".join(item.name for item in run.indicators) or "—"
    _body(pdf, f"Показатели: {names}.")
    _body(pdf, f"Статус запуска: {run.status.value}.")

    _heading(pdf, "2. Качество данных")
    if quality:
        _body(pdf, (
            f"Значений: {quality.get('values_count', '—')}. "
            f"Пропусков: {quality.get('missing_count', '—')}. "
            f"Периодов: {quality.get('distinct_periods', '—')}."
        ))
        issues = quality.get("issues") or []
        if issues:
            _table(pdf, ["Код", "Сообщение"], [[str(item.get("code")), str(item.get("message"))] for item in issues[:20]], [40, 138])
        else:
            _muted(pdf, "Отдельных предупреждений по сохранённому набору нет.")
    else:
        _muted(pdf, "Сводка качества набора в отчёт не включена.")

    section = 3
    if results.conclusion:
        _heading(pdf, f"{section}. Краткое заключение")
        section += 1
        _body(pdf, results.conclusion.summary)
        for item in results.conclusion.highlights:
            _body(pdf, f"• {item}")
        if results.conclusion.limitations:
            _muted(pdf, "Ограничения:")
            for item in results.conclusion.limitations:
                _muted(pdf, f"• {item}")

    _heading(pdf, f"{section}. Оценка состояния")
    section += 1
    assessment = results.assessment
    narrative = results.assessment_narrative
    if assessment and assessment.score is not None:
        _body(pdf, f"Отображаемое значение: {float(assessment.score):.0f} из 100. {assessment.interpretation or ''}")
        if assessment.history_score is not None:
            _body(pdf, f"Историческая динамика: {float(assessment.history_score):.0f}.")
        if assessment.compliance_score is not None:
            _body(pdf, f"Соответствие заданным нормативам: {float(assessment.compliance_score):.0f}.")
        elif assessment.history_score is not None:
            _body(pdf, "Нормативы не заданы; балл по собственной истории.")
        if assessment.completeness is not None:
            _body(pdf, f"Полнота данных: {float(assessment.completeness) * 100:.0f} %.")
        if narrative:
            _body(pdf, narrative.brief)
            for line in narrative.details:
                _body(pdf, f"• {line}")
        _muted(pdf, assessment.methodology or ASSESSMENT_METHOD)
        if assessment.components:
            _table(
                pdf, ["Показатель", "Норм. балл", "Вклад"],
                [
                    [item.indicator_name, f"{float(item.normalized_score):.2f}",
                     "—" if item.contribution is None else f"{float(item.contribution):.2f}"]
                    for item in assessment.components
                ],
                [90, 44, 44],
            )
    else:
        _body(pdf, (assessment.message if assessment else None) or "Оценка не рассчитана.")

    ratio_items = results.ratios.items if results.ratios else []
    if ratio_items:
        _heading(pdf, f"{section}. Коэффициенты")
        section += 1
        _table(
            pdf, ["Коэффициент", "Факт", "Изм., %"],
            [
                [item.name, "—" if item.last_value is None else f"{float(item.last_value):.2f}",
                 "—" if item.pct_change is None else f"{float(item.pct_change):.1f}"]
                for item in ratio_items[:25]
            ],
            [90, 44, 44],
        )

    trend_items = results.trends.items if results.trends else []
    if trend_items:
        _heading(pdf, f"{section}. Тенденции")
        section += 1
        _table(
            pdf, ["Показатель", "Описание", "Изм., %"],
            [
                [item.indicator, (item.label or "—")[:40],
                 "—" if item.pct_change is None else f"{float(item.pct_change):.1f}"]
                for item in trend_items[:25]
            ],
            [50, 84, 44],
        )

    findings = results.findings or []
    alerts = results.alerts or []
    if findings or alerts:
        _heading(pdf, f"{section}. Проблемы и предупреждения")
        section += 1
        if findings:
            _table(
                pdf, ["Проблема", "Уровень", "Уверенность"],
                [[item.get("title") or "—", str(item.get("severity") or "—"),
                  str(item.get("confidence") or "—")] for item in findings[:20]],
                [98, 40, 40],
            )
        if alerts:
            _table(
                pdf, ["Уровень", "Сообщение"],
                [[str(item.get("level") or "—"), str(item.get("message") or "—")[:70]] for item in alerts[:20]],
                [40, 138],
            )

    items = results.anomalies.items if results.anomalies else []
    if items:
        _heading(pdf, f"{section}. Аномалии")
        section += 1
        if results.anomalies_narrative:
            _body(pdf, results.anomalies_narrative.brief)
        _table(
            pdf,
            ["Показатель", "Период", "Факт", "Характер"],
            [
                [item.indicator_name, str(item.period_start),
                 "—" if item.value is None else f"{float(item.value):.2f}",
                 "выше" if item.direction == "above" else "ниже"]
                for item in items[:40]
            ],
            [70, 36, 36, 36],
        )

    pairs = [item for item in (results.correlation.pairs if results.correlation else []) if item.coefficient is not None]
    if pairs:
        _heading(pdf, f"{section}. Корреляции")
        section += 1
        if results.correlation_narrative:
            _body(pdf, results.correlation_narrative.brief)
        pairs.sort(key=lambda item: abs(item.coefficient), reverse=True)
        _table(
            pdf, ["A", "B", "r", "n"],
            [
                [item.indicator_a, item.indicator_b, f"{item.coefficient:.2f}", str(item.n_observations)]
                for item in pairs[:20]
            ],
            [55, 55, 34, 34],
        )

    clusters = results.clustering.clusters if results.clustering else []
    if clusters:
        _heading(pdf, f"{section}. Кластеризация периодов")
        section += 1
        if results.clustering_narrative:
            _body(pdf, results.clustering_narrative.brief)
        _table(
            pdf, ["Группа", "Наблюдений", "Подпись"],
            [[str(item.cluster), str(item.size), item.label or "—"] for item in clusters],
            [40, 40, 98],
        )

    if results.forecast and results.forecast.series:
        _heading(pdf, f"{section}. Прогноз")
        section += 1
        if results.forecast_narrative:
            _body(pdf, results.forecast_narrative.brief)
        for series in results.forecast.series[:4]:
            _body(pdf, f"Показатель {series.indicator}, метод {series.method}, горизонт {len(series.points)}.")
            _table(
                pdf, ["Период", "Прогноз", "Нижняя", "Верхняя"],
                [
                    [
                        str(point.period_start),
                        f"{float(point.value):.2f}",
                        "—" if point.lower_bound is None else f"{float(point.lower_bound):.2f}",
                        "—" if point.upper_bound is None else f"{float(point.upper_bound):.2f}",
                    ]
                    for point in series.points
                ],
                [50, 42, 43, 43],
            )

    _heading(pdf, f"{section}. Ограничения")
    _muted(pdf, "В отчёт включены только рассчитанные процедуры.")

    return bytes(pdf.output())
