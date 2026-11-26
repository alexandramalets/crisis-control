# База данных

PostgreSQL 18. Схема таблиц создаётся миграциями Alembic из `backend/alembic`. Этот каталог содержит только то, что относится к самой СУБД.

| Путь | Назначение |
|---|---|
| `init/01-create-app-role.sh` | Создание роли приложения `APP_DB_USER` без прав суперпользователя. Выполняется один раз — при первом запуске контейнера с пустым томом данных |
| `backups/` | Зашифрованные резервные копии (`daily/`, `weekly/`). Каталог не хранится в git |

Учётные записи:

- `POSTGRES_USER` — администратор СУБД, используется только для обслуживания;
- `APP_DB_USER` — учётная запись серверного приложения, владелец таблиц, создаваемых миграциями.

Скрипт инициализации не выполняется повторно. Чтобы пересоздать базу с нуля (все данные будут удалены): `docker compose down -v`, затем `docker compose up -d`.

Для PostgreSQL на отдельном узле без Docker выполните аналогичные команды из `init/01-create-app-role.sh` вручную в `psql` и укажите адрес узла в `DB_HOST` серверного приложения.

## Резервное копирование и восстановление

Копии делает `scripts/backup.ps1`: `pg_dump -Fc` внутри контейнера `database`, затем шифрование AES-256-GCM ключом `BACKUP_ENCRYPTION_KEY` (не короче 32 символов, в `.env` или в окружении). Открытый дамп удаляется. Файл лежит в `backups/daily/crisis-analytics-<метка UTC>.dump.enc`. По воскресеньям UTC та же копия кладётся в `backups/weekly/`. Хранятся 7 ежедневных и 4 еженедельные копии, более старые удаляются.

Нужны запущенные контейнеры `database` и собранный образ `backend` (в нём выполняется `python -m app.ops.backup_archive`). Если `.env` создан до появления ключа, добавьте `BACKUP_ENCRYPTION_KEY` вручную или заново выполните `scripts\init-env.ps1` только на пустом проекте: с `-Force` скрипт перезаписывает все секреты.

```powershell
powershell -ExecutionPolicy Bypass -File scripts\backup.ps1
powershell -ExecutionPolicy Bypass -File scripts\restore.ps1 -Archive database\backups\daily\crisis-analytics-YYYYMMDDTHHMMSSZ.dump.enc
powershell -ExecutionPolicy Bypass -File scripts\schedule-backup.ps1
```

Восстановление останавливает `backend`, расшифровывает архив и выполняет `pg_restore --clean --if-exists`. Это заменяет объекты в текущей базе. Ненулевой код `pg_restore` означает, что восстановление нужно проверить по журналу контейнера `database`: предупреждения утилита тоже считает ошибкой. Расписание Планировщика заданий само не создаётся, пока не запущен `schedule-backup.ps1`.

Каталог данных PostgreSQL и каталог копий дополнительно защищаются шифрованием диска Windows (BitLocker). Числовые показатели в таблицах не шифруются: шифруется дамп и исходные файлы наборов. Подробности — в `docs/SECURITY.md`.
