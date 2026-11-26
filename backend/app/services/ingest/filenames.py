"""Безопасные имена файлов: без путей, без обхода каталогов."""

import re
from pathlib import Path

_UNSAFE = re.compile(r"[^A-Za-z0-9._а-яА-ЯёЁ()-]+")


def original_filename(raw: str | None) -> str:
    """Только базовое имя. Путь и «..» отбрасываются.

    Обратные слэши нормализуются до Path.name: на Linux Path не считает их разделителем,
    и имя вида ``..\\..\\secret.csv`` иначе сохранилось бы целиком.
    """
    text = (raw or "").replace("\x00", "").replace("\r", "").replace("\n", "")
    text = text.replace("\\", "/")
    name = Path(text).name.strip()
    if not name or name in {".", ".."}:
        return "upload"
    return name[:200]


def safe_stem(filename: str) -> str:
    stem = Path(original_filename(filename)).stem
    cleaned = _UNSAFE.sub("_", stem).strip("._")
    return (cleaned or "upload")[:80]


def extension(filename: str) -> str:
    suffix = Path(original_filename(filename)).suffix.lower()
    return suffix.lstrip(".")
