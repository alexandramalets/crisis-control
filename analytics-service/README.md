# Интеллектуальный микросервис (analytics-service)

Отдельный процесс и контейнер. FastAPI, pandas, NumPy, SciPy, scikit-learn, statsmodels. Нет доступа к PostgreSQL и нет алгоритмов во frontend / основном backend: сервис принимает матрицу наблюдений по контракту `/analytics/v1` и возвращает результаты процедур.

Полное описание операций: [`docs/ANALYTICS_API.md`](../docs/ANALYTICS_API.md). OpenAPI: `GET /analytics/docs`.

## Запуск без Docker (Windows 11, PowerShell)

```powershell
cd analytics-service
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock.txt
Copy-Item .env.example .env     # заполнить ANALYTICS_SERVICE_KEY (то же значение, что у сервера)
.\.venv\Scripts\python.exe -m app
```

На отдельном узле: `ANALYTICS_SERVICE_URL=http://<адрес>:8001` на сервере; порт 8001 открывать только для серверного узла.

## Эндпоинты

| Путь | Доступ | Назначение |
|---|---|---|
| `GET /analytics/v1/health` | открыт | Состояние и версии научных библиотек |
| `GET /analytics/v1/capabilities` | `X-Service-Key` | Список процедур и параметры по умолчанию |
| `POST /analytics/v1/validate` | ключ | Проверка аналитических данных |
| `POST /analytics/v1/anomalies` | ключ | Медиана и MAD |
| `POST /analytics/v1/correlation` | ключ | Корреляции Пирсона |
| `POST /analytics/v1/clustering` | ключ | k-средних |
| `POST /analytics/v1/forecast` | ключ | Экспоненциальное сглаживание |
| `POST /analytics/v1/assessment` | ключ | Оценка состояния 0–100 |
| `POST /analytics/v1/analyze` | ключ | Конвейер выбранных процедур |
| `GET /analytics/docs` | открыт | OpenAPI |

## Ошибки запуска

| Код выхода | Причина |
|---|---|
| 2 | Не задан или слишком короткий `ANALYTICS_SERVICE_KEY` (не менее 32 символов) |
| 3 | Не установлена одна из научных библиотек |
| 4 | Порт `PORT` занят |

## Тесты

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest
```
