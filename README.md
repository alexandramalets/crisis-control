# Кризис. Аналитика

Программное средство анализа и визуализации многомерных данных в кризисном управлении (курсовой проект, БГУИР, кафедра ПИКС).

Три независимо запускаемых компонента и СУБД:

| Каталог | Компонент | Технологии | Порт |
|---|---|---|---|
| `frontend/` | Клиентское приложение | React 19, JavaScript, Vite 7, CSS, Recharts, Axios; nginx в Docker | 8080 |
| `backend/` | Серверное приложение (бизнес-логика) | Python 3.13, FastAPI, SQLAlchemy 2, Alembic, Pydantic 2, JWT, Argon2 | 8000 |
| `analytics-service/` | Интеллектуальный микросервис | Python 3.13, FastAPI, pandas, NumPy, SciPy, scikit-learn, statsmodels | 8001 |
| `database/` | PostgreSQL 18 (скрипты инициализации) | — | внутренний |

Остальные каталоги: `sample-data/` — демонстрационный набор показателей, `docs/` — архитектура и план работ, `scripts/` — служебные скрипты.

## Первый запуск (Docker Desktop, Windows 11)

Требуется Docker Desktop с запущенным движком.

```powershell
cd crisis-analytics
powershell -ExecutionPolicy Bypass -File scripts\init-env.ps1   # создаёт .env и генерирует секреты
docker compose up -d --build
docker compose ps                                               # все сервисы должны быть healthy
```

Откройте <http://localhost:8080>. На странице «Состояние системы» должны работать все четыре компонента.

Проверка из командной строки:

```powershell
Invoke-RestMethod http://localhost:8080/healthz                 # клиент (nginx)
Invoke-RestMethod http://localhost:8080/api/v1/health/ready     # сервер + БД + аналитика через прокси клиента
Invoke-RestMethod http://localhost:8000/api/v1/health           # сервер напрямую
Invoke-RestMethod http://localhost:8001/analytics/v1/health     # аналитический сервис
```

Схема БД создаётся автоматически при запуске сервера. Первого администратора создайте командой (пароль запрашивается без отображения):

```powershell
docker compose exec backend python -m app.cli create-user --username admin --email admin@example.org --full-name "Администратор"
```

Документация API (OpenAPI): <http://localhost:8080/api/docs>. Описание БД — `docs/DATABASE.md`, авторизации и эндпоинтов — `backend/README.md`.

Остановка: `docker compose down` (данные БД сохраняются в томе `pgdata`).

## Сети и порты

- Сеть `edge` объединяет клиент и сервер, сеть `internal` — сервер, СУБД и аналитический сервис. Клиент не имеет сетевого доступа к СУБД и аналитическому сервису.
- Порт СУБД на хост не публикуется. Для запуска сервера вне Docker используйте `docker-compose.db-port.yml` (порт 5433).
- Порты сервера и аналитического сервиса по умолчанию доступны только с этой машины (`127.0.0.1`). Адреса и порты меняются в `.env` (`*_BIND_ADDRESS`, `*_PUBLISHED_PORT`).

## Размещение на разных узлах

Каждый компонент собирается и запускается отдельно (`docker compose up -d <сервис>` или без Docker — см. README компонента). Компоненты связаны только адресами в конфигурации:

| Узел | Что запускается | Что указать |
|---|---|---|
| Клиентский | `frontend` | `BACKEND_UPSTREAM=http://<серверный узел>:8000` |
| Серверный | `backend`, `database` | `ANALYTICS_SERVICE_URL=http://<интеллектуальный узел>:8001`, `BACKEND_BIND_ADDRESS=0.0.0.0` |
| Интеллектуальный | `analytics-service` | `ANALYTICS_BIND_ADDRESS=0.0.0.0`; доступ к порту в брандмауэре — только с серверного узла |

`ANALYTICS_SERVICE_KEY` должен совпадать на серверном и интеллектуальном узлах. Локальный `docker compose` по умолчанию использует HTTP внутри сети Docker. Защищённое соединение между узлами и резервное копирование описаны в `docs/SECURITY.md`.

## Запуск без Docker

См. `backend/README.md`, `analytics-service/README.md` и `frontend/README.md`. Для запуска не нужна IDE: используются только Python, Node.js (для сборки клиента) и PowerShell.

## Версии зависимостей

Версии закреплены по состоянию на январь 2026 года (требование ЛЗ п. 3.2.4). Проверка: `python scripts\check_versions.py`. Python-зависимости, включая транзитивные, зафиксированы в `requirements.lock.txt`. Они получены командой `pip install --uploaded-prior-to 2026-02-01T00:00:00Z -r requirements.txt` и последующим `pip freeze`. Зависимости клиента зафиксированы в `frontend/package-lock.json`.

## Тесты

```powershell
cd backend;            .\.venv\Scripts\python.exe -m pytest
cd analytics-service;  .\.venv\Scripts\python.exe -m pytest
cd frontend;           npm test; npm run build
```

Интеграционные тесты backend на PostgreSQL требуют тестовую БД и переменную `TEST_DB_PASSWORD` (см. `backend/README.md`); без неё они пропускаются.
