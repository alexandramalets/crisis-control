"""Проверка соответствия версий зависимостей требованию ЛЗ п. 3.2.4.

Для каждого пакета выводит последнюю стабильную версию, опубликованную
не позднее CUTOFF, по данным PyPI и npm. Запуск: python scripts/check_versions.py
"""

import json
import urllib.request
from datetime import datetime

CUTOFF = datetime(2026, 1, 31, 23, 59, 59)

PYPI_PACKAGES = [
    "fastapi", "uvicorn", "pydantic", "pydantic-settings", "sqlalchemy", "alembic",
    "psycopg", "pyjwt", "argon2-cffi", "httpx", "python-multipart", "pandas", "numpy",
    "scipy", "scikit-learn", "statsmodels", "openpyxl", "cryptography", "pytest",
    "email-validator",
]
NPM_PACKAGES = [
    "react", "react-dom", "vite", "@vitejs/plugin-react", "recharts", "axios",
    "react-router-dom",
]

PRERELEASE_MARKERS = ("a", "b", "rc", "dev", "-", "alpha", "beta", "canary", "next")


def is_stable(version):
    return not any(marker in version for marker in PRERELEASE_MARKERS)


def version_key(version):
    return tuple(int(part) if part.isdigit() else 0 for part in version.split("."))


def pick_highest(candidates):
    """Наибольшая версия, а не последняя по дате: иначе выбираются патчи старых веток."""
    return max(candidates, key=lambda item: version_key(item[0]), default=None)


def fetch_json(url):
    with urllib.request.urlopen(url, timeout=30) as response:
        return json.load(response)


def latest_pypi(name):
    data = fetch_json(f"https://pypi.org/pypi/{name}/json")
    candidates = []
    for version, files in data["releases"].items():
        if not files or not is_stable(version):
            continue
        uploaded = min(datetime.fromisoformat(f["upload_time"]) for f in files)
        if uploaded <= CUTOFF:
            candidates.append((version, uploaded))
    return pick_highest(candidates)


def latest_npm(name):
    data = fetch_json(f"https://registry.npmjs.org/{name.replace('/', '%2F')}")
    candidates = []
    for version, published in data["time"].items():
        if version in ("created", "modified") or not is_stable(version):
            continue
        published_at = datetime.fromisoformat(published.replace("Z", ""))
        if published_at <= CUTOFF:
            candidates.append((version, published_at))
    return pick_highest(candidates)


def main():
    print(f"Последние стабильные версии на {CUTOFF:%d.%m.%Y}")
    for name in PYPI_PACKAGES:
        version, published = latest_pypi(name)
        print(f"PyPI  {name}=={version}  ({published:%Y-%m-%d})")
    for name in NPM_PACKAGES:
        version, published = latest_npm(name)
        print(f"npm   {name}@{version}  ({published:%Y-%m-%d})")


if __name__ == "__main__":
    main()
