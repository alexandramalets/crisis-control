#!/bin/sh
# Выполняется образом postgres один раз — при инициализации пустого каталога данных.
# Создаёт роль приложения без прав суперпользователя (принцип минимальных привилегий).
# Скрипт может подключаться через source в оболочку entrypoint, поэтому без set -eu.

: "${APP_DB_USER:?Не задана переменная APP_DB_USER}"
: "${APP_DB_PASSWORD:?Не задана переменная APP_DB_PASSWORD}"

psql -v ON_ERROR_STOP=1 \
     -v app_user="$APP_DB_USER" \
     -v app_password="$APP_DB_PASSWORD" \
     -v db_name="$POSTGRES_DB" \
     --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<'EOSQL'
CREATE ROLE :"app_user" LOGIN PASSWORD :'app_password'
    NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION;
REVOKE ALL ON DATABASE :"db_name" FROM PUBLIC;
GRANT CONNECT, TEMPORARY ON DATABASE :"db_name" TO :"app_user";
GRANT USAGE, CREATE ON SCHEMA public TO :"app_user";
EOSQL
