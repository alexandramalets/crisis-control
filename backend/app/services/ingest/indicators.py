"""Сопоставление столбцов файла со справочником показателей."""

import re
import unicodedata

from app.models import Indicator

PERIOD_ALIASES = {
    "period", "date", "месяц", "период", "дата", "time", "year_month", "год_месяц", "yearmonth",
}
CATEGORY_ALIASES = {
    "category", "категория", "подразделение", "department", "segment", "направление",
}
LONG_INDICATOR_ALIASES = {"indicator", "показатель", "indicator_code", "код", "code"}
LONG_VALUE_ALIASES = {"value", "значение", "amount", "сумма"}

SYNONYMS: dict[str, str] = {
    "выручка": "revenue",
    "объёмпродаж": "sales_volume",
    "объемпродаж": "sales_volume",
    "продажи": "sales_volume",
    "прибыль": "profit",
    "дебиторскаязадолженность": "receivables",
    "дебиторка": "receivables",
    "кредиторскаязадолженность": "payables",
    "кредиторка": "payables",
    "запасы": "inventory",
    "денежныесредства": "cash",
    "касса": "cash",
    "денежныйпотокотоперационнойдеятельности": "cf_operating",
    "операционныйденежныйпоток": "cf_operating",
    "денежныйпотокотинвестиционнойдеятельности": "cf_investing",
    "инвестиционныйденежныйпоток": "cf_investing",
    "денежныйпотокотфинансовойдеятельности": "cf_financing",
    "финансовыйденежныйпоток": "cf_financing",
}


def normalize_label(value: str) -> str:
    text = unicodedata.normalize("NFKC", value).casefold().replace("ё", "е")
    return re.sub(r"[^a-z0-9а-я]+", "", text)


def is_period_name(name: str) -> bool:
    return normalize_label(name) in {normalize_label(alias) for alias in PERIOD_ALIASES} or name.casefold() == "period"


def is_category_name(name: str) -> bool:
    return normalize_label(name) in {normalize_label(alias) for alias in CATEGORY_ALIASES}


def is_long_indicator_name(name: str) -> bool:
    return normalize_label(name) in {normalize_label(alias) for alias in LONG_INDICATOR_ALIASES}


def is_long_value_name(name: str) -> bool:
    return normalize_label(name) in {normalize_label(alias) for alias in LONG_VALUE_ALIASES}


class IndicatorCatalog:
    def __init__(self, indicators: list[Indicator]):
        self.by_code = {item.code: item for item in indicators}
        self._by_label: dict[str, Indicator] = {}
        for item in indicators:
            self._by_label[normalize_label(item.code)] = item
            self._by_label[normalize_label(item.name)] = item
        for synonym, code in SYNONYMS.items():
            if code in self.by_code:
                self._by_label.setdefault(synonym, self.by_code[code])

    def match(self, column: str) -> Indicator | None:
        return self.by_code.get(column.strip().casefold()) or self._by_label.get(normalize_label(column))
