#!/bin/sh
# Включает TLS у PostgreSQL перед штатной точкой входа образа.
# Вызывается только из docker-compose.tls.yml. Без POSTGRES_TLS_DIR поведение образа не меняется.
set -eu
if [ -n "${POSTGRES_TLS_DIR:-}" ]; then
  mkdir -p /var/lib/postgresql/ssl
  cp "$POSTGRES_TLS_DIR/server.crt" /var/lib/postgresql/ssl/server.crt
  cp "$POSTGRES_TLS_DIR/server.key" /var/lib/postgresql/ssl/server.key
  chown postgres:postgres /var/lib/postgresql/ssl/server.crt /var/lib/postgresql/ssl/server.key
  chmod 644 /var/lib/postgresql/ssl/server.crt
  chmod 600 /var/lib/postgresql/ssl/server.key
  set -- "$@" -c ssl=on \
    -c ssl_cert_file=/var/lib/postgresql/ssl/server.crt \
    -c ssl_key_file=/var/lib/postgresql/ssl/server.key \
    -c ssl_min_protocol_version=TLSv1.2
fi
exec docker-entrypoint.sh "$@"
