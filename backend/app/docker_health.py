"""Проверка живости контейнера: HTTP или HTTPS, если задан TLS_CERT_FILE."""

import os
import ssl
import sys
import urllib.request


def main() -> None:
    port = os.environ.get("PORT", "8000")
    path = os.environ.get("HEALTHCHECK_PATH", "/api/v1/health")
    if os.environ.get("TLS_CERT_FILE"):
        ca_file = os.environ.get("TLS_CA_FILE")
        if not ca_file:
            print("ОШИБКА: для HTTPS-проверки задайте TLS_CA_FILE", file=sys.stderr)
            sys.exit(1)
        context = ssl.create_default_context(cafile=ca_file)
        url = f"https://127.0.0.1:{port}{path}"
        try:
            urllib.request.urlopen(url, context=context, timeout=2)
        except OSError as exc:
            print(f"ОШИБКА: {type(exc).__name__}", file=sys.stderr)
            sys.exit(1)
        return
    urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=2)


if __name__ == "__main__":
    main()
