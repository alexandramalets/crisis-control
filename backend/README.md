# Серверное приложение (backend)

FastAPI, SQLAlchemy 2, Alembic, PostgreSQL. Здесь находится вся бизнес-логика системы: авторизация, проверка прав доступа, хранение наборов данных, исследований и отчётов. Клиент только отображает данные.

## Структура

| Каталог | Назначение |
|---|---|
| `app/core/` | Конфигурация из переменных окружения (`config.py`), Argon2id и JWT (`security.py`), журналирование с маскировкой секретов (`logging.py`), единая обработка ошибок (`errors.py`) |
| `app/api/v1/` | Роутеры HTTP: `health`, `auth`, `organizations`, `reference`, `datasets`, `analyses`, `reports`; зависимости — `app/api/deps.py` |
| `app/schemas/` | Pydantic-схемы запросов и ответов |
| `app/integrations/` | Адаптер аналитического микросервиса (`analytics_client.py`): HTTP, тайм-аут, предохранитель |
| `app/services/` | Бизнес-логика и правила доступа (`access.py`) |
| `app/repositories/` | Запросы к БД; ограничение по владельцу встроено в запросы |
| `app/models/` | Модели SQLAlchemy (описание — [docs/DATABASE.md](../docs/DATABASE.md)) |
| `app/db/` | Подключение, миграции, команда настройки схемы |
| `alembic/versions/` | 0001 — схема, 0002 — справочники (роли, единицы, группы, 10 системных показателей), 0003 — тип процедуры `assessment` |

## Зависимости

- `requirements.txt` — прямые зависимости с закреплёнными версиями;
- `requirements.lock.txt` — полный набор с транзитивными зависимостями (состояние на январь 2026). Используется в Docker и для воспроизводимой установки;
- `requirements-dev.txt` — дополнительно pytest.

## Запуск без Docker (Windows 11, PowerShell)

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock.txt
Copy-Item .env.example .env     # заполнить DB_PASSWORD, ANALYTICS_SERVICE_KEY, JWT_SECRET_KEY
.\.venv\Scripts\python.exe -m app.db.setup   # создать или обновить схему БД
.\.venv\Scripts\python.exe -m app
```

Нужна доступная СУБД. Проще всего запустить её контейнер с опубликованным портом 5433 из корня проекта:

```powershell
docker compose -f docker-compose.yml -f docker-compose.db-port.yml up -d database
```

Значения `DB_PASSWORD` и `ANALYTICS_SERVICE_KEY` должны совпадать со значениями в корневом `.env`. В Docker Compose миграции применяются автоматически при запуске (`DB_MIGRATE_ON_STARTUP=true`).

## Первый пользователь

Учётные записи не создаются миграциями. Первого администратора создаёт команда; пароль запрашивается дважды и не отображается:

```powershell
# в Docker
docker compose exec backend python -m app.cli create-user --username admin --email admin@example.org --full-name "Администратор"
# без Docker
.\.venv\Scripts\python.exe -m app.cli create-user --username admin --email admin@example.org --full-name "Администратор"
```

Параметры: `--role analyst|admin` (по умолчанию `admin`), `--password-stdin` — прочитать пароль из стандартного ввода (для сценариев). Аргументом командной строки пароль не принимается. Требования: логин из 3–50 строчных латинских букв, цифр и `._-`; пароль не короче 8 символов и не совпадает с логином или email.

## Авторизация и доступ

- `POST /api/v1/auth/login` принимает `{"login": "<логин или email>", "password": "..."}`, возвращает access-токен (JWT HS256, 15 минут) и устанавливает refresh-токен в cookie `refresh_token` (`HttpOnly`, `SameSite=Strict`, `Path=/api/v1/auth`, 7 дней).
- Access-токен передаётся в заголовке `Authorization: Bearer <токен>`. В нём есть идентификатор сеанса: после `POST /auth/logout` токен перестаёт действовать сразу, а не по истечении срока.
- `POST /auth/refresh` выдаёт новую пару токенов; повторное предъявление уже использованного refresh-токена отзывает сеанс.
- После 5 неудачных попыток входа подряд учётная запись блокируется на 15 минут (`429`, заголовок `Retry-After`). На неверный логин и неверный пароль ответ одинаковый.
- Аналитик видит только свои организации и всё, что к ним относится. Чужой объект возвращает `404`, как несуществующий. Администратор читает данные всех пользователей, но не изменяет и не удаляет чужие объекты (`403`).
- Регистрация (`POST /auth/register`) включается переменной `ALLOW_REGISTRATION=true` и создаёт пользователя с ролью `analyst`.

## Эндпоинты

Полная документация — OpenAPI: `http://localhost:8000/api/docs` (или через клиентский узел `http://localhost:8080/api/docs`). Кнопка **Authorize** принимает access-токен.

| Метод | Путь | Назначение |
|---|---|---|
| GET | `/api/v1/health` | Процесс работает |
| GET | `/api/v1/health/ready` | Готовность: БД (включая версию схемы) и аналитический сервис |
| POST | `/api/v1/auth/login` | Вход |
| POST | `/api/v1/auth/refresh` | Обновление access-токена |
| POST | `/api/v1/auth/logout` | Завершение сеанса |
| POST | `/api/v1/auth/register` | Регистрация (если разрешена) |
| GET | `/api/v1/auth/me` | Профиль текущего пользователя |
| PUT | `/api/v1/auth/me/password` | Смена пароля (остальные сеансы завершаются) |
| GET, POST | `/api/v1/organizations` | Список и создание организаций |
| GET, PATCH, DELETE | `/api/v1/organizations/{id}` | Организация |
| GET | `/api/v1/reference/indicators` | Показатели |
| GET | `/api/v1/datasets/template` | Шаблон CSV или XLSX |
| POST | `/api/v1/datasets/preview` | Просмотр файла: столбцы, типы, первые строки |
| POST | `/api/v1/datasets/preview/validate` | Проверка качества (пропуски, дубликаты, некорректные значения) |
| POST | `/api/v1/organizations/{id}/datasets/import` | Сохранение проверенного файла |
| POST, GET | `/api/v1/organizations/{id}/datasets` | Создание набора JSON; наборы организации |
| GET | `/api/v1/datasets` | Доступные наборы (`organization_id`, `limit`, `offset`) |
| GET, DELETE | `/api/v1/datasets/{id}` | Набор данных: показатели, периоды, предупреждения; удаление |
| GET | `/api/v1/datasets/{id}/schema` | Схема набора |
| GET | `/api/v1/datasets/{id}/quality` | Сводка качества |
| GET | `/api/v1/datasets/{id}/values` | Значения (`indicators`, `from`, `to`) |
| GET | `/api/v1/analyses/methods` | Методы аналитического сервиса (`capabilities`) |
| POST | `/api/v1/analyses` | Комплексный анализ: проверка прав, загрузка набора, вызов микросервиса, сохранение |
| POST | `/api/v1/analyses/anomalies` \| `/correlation` \| `/clustering` \| `/forecast` \| `/assessment` | Запуск отдельной процедуры |
| GET | `/api/v1/analyses` | Исследования (`dataset_id`, `organization_id`, `status`) |
| GET | `/api/v1/analyses/{id}` | Исследование: показатели и веса, процедуры и параметры |
| GET | `/api/v1/analyses/{id}/results` | Сводный результат всех процедур |
| GET | `/api/v1/analyses/{id}/anomalies` \| `/correlations` \| `/clusters` \| `/forecasts` \| `/assessment` | Повторный просмотр результатов |
| POST | `/api/v1/analyses/{id}/rerun` | Повторный запуск (`parent_run_id`) |
| DELETE | `/api/v1/analyses/{id}` | Удаление исследования |
| GET | `/api/v1/reports` | Отчёты (`run_id`) |
| GET | `/api/v1/reports/{id}` | Сведения об отчёте |
| GET | `/api/v1/reports/{id}/content` | Файл отчёта |

Ошибки: `{"error": {"code", "message", "details"}}`, сообщения на русском языке. Коды: `401` — нет токена, токен недействителен или истёк (`code`: `not_authenticated`, `invalid_token`, `token_expired`, `session_revoked`); `403` — недостаточно прав; `404` — объект не найден или чужой; `409` — конфликт (дубликат); `413` — файл больше 10 МБ; `422` — ошибка проверки данных; `429` — временная блокировка входа; `502` — некорректный ответ аналитического сервиса; `503` — БД или аналитический сервис недоступны. При недоступности микросервиса успешный результат не подставляется: исследование сохраняется со статусом `failed`.

Вызов аналитического микросервиса идёт только через адаптер `app/integrations/analytics_client.py` (тайм-аут, повтор GET, ограничение размера тела, проверка JSON, предохранитель). Обработчики API к HTTP микросервиса не обращаются. Алгоритмы остаются в `analytics-service`. Документация контракта: [docs/ANALYTICS_API.md](../docs/ANALYTICS_API.md).

Загрузка файла: `POST /datasets/preview` (multipart `file`) → пользователь указывает столбец периода и показатели → `POST /datasets/preview/validate` → `POST /organizations/{id}/datasets/import`. Непрошедший проверку файл в PostgreSQL не пишется. Оригинал хранится в `DATA_DIR` в зашифрованном виде.

## Ошибки запуска

`python -m app` проверяет окружение до старта HTTP-сервера и завершается с понятным сообщением:

| Код выхода | Причина |
|---|---|
| 2 | Не заданы или некорректны переменные окружения (выводится список) |
| 3 | PostgreSQL недоступна после `DB_STARTUP_RETRIES` попыток |
| 4 | Порт `PORT` занят |
| 6 | Не удалось применить миграции (при `DB_MIGRATE_ON_STARTUP=true`) |

`python -m app.db.setup --check` возвращает 0, если схема на последней ревизии, и 5, если нет.

## Тесты

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest
```

Интеграционные тесты (`tests/integration/`) выполняются на отдельной тестовой БД PostgreSQL; без неё они пропускаются. Тесты пересоздают схему, поэтому имя БД обязано оканчиваться на `_test`.

```powershell
# один раз: тестовая БД в контейнере СУБД (порт 5433 опубликован через docker-compose.db-port.yml)
docker compose exec database createdb -U postgres -O crisis_app crisis_analytics_test
# пароль роли crisis_app — значение DB_PASSWORD из корневого .env
$env:TEST_DB_PASSWORD = "<DB_PASSWORD>"
.\.venv\Scripts\python.exe -m pytest
```

Необязательные переменные: `TEST_DB_HOST` (127.0.0.1), `TEST_DB_PORT` (5433), `TEST_DB_NAME` (crisis_analytics_test), `TEST_DB_USER` (crisis_app).

Дымовая проверка развёрнутого стенда через nginx — `scripts/smoke_api.py` (см. описание в файле).
