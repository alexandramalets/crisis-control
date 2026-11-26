"""Шифрование резервной копии PostgreSQL (AES-256-GCM) и ротация файлов.

Формат файла: ASCII ``CAENC1`` + nonce 12 байт + шифртекст AES-GCM.
Ключ берётся из переменной окружения BACKUP_ENCRYPTION_KEY (не короче 32 символов)
тем же правилом, что и ключ исходных файлов: 32 байта как есть, иначе SHA-256.
"""

import argparse
import os
import sys
from pathlib import Path

from cryptography.exceptions import InvalidTag

from app.core.crypto import decrypt, encrypt, file_encryption_key

MAGIC = b"CAENC1"
NONCE_SIZE = 12


class BackupArchiveError(Exception):
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


def encryption_key_from_env() -> bytes:
    secret = os.environ.get("BACKUP_ENCRYPTION_KEY", "")
    if len(secret) < 32:
        raise BackupArchiveError("BACKUP_ENCRYPTION_KEY не задан или короче 32 символов")
    return file_encryption_key(secret)


def encrypt_blob(key: bytes, plaintext: bytes) -> bytes:
    ciphertext, nonce = encrypt(key, plaintext)
    return MAGIC + nonce + ciphertext


def decrypt_blob(key: bytes, blob: bytes) -> bytes:
    header = len(MAGIC) + NONCE_SIZE
    if not blob.startswith(MAGIC) or len(blob) < header + 16:
        raise BackupArchiveError("Файл не является зашифрованной резервной копией")
    try:
        return decrypt(key, blob[len(MAGIC):header], blob[header:])
    except InvalidTag as exc:
        raise BackupArchiveError("Не удалось расшифровать резервную копию: ключ не подходит или файл повреждён") from exc


def obsolete_archives(paths: list[Path], keep: int) -> list[Path]:
    """Лишние файлы сверх keep самых новых по имени (метка времени входит в имя)."""
    if keep < 1:
        raise BackupArchiveError("Число сохраняемых копий должно быть не меньше 1")
    archives = sorted((path for path in paths if path.is_file()), key=lambda path: path.name, reverse=True)
    return archives[keep:]


def _read_key() -> bytes:
    try:
        return encryption_key_from_env()
    except BackupArchiveError as exc:
        print(f"ОШИБКА: {exc.message}", file=sys.stderr)
        raise SystemExit(2) from exc


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Шифрование и ротация резервных копий")
    sub = parser.add_subparsers(dest="command", required=True)

    encrypt_cmd = sub.add_parser("encrypt")
    encrypt_cmd.add_argument("--input", required=True, type=Path)
    encrypt_cmd.add_argument("--output", required=True, type=Path)

    decrypt_cmd = sub.add_parser("decrypt")
    decrypt_cmd.add_argument("--input", required=True, type=Path)
    decrypt_cmd.add_argument("--output", required=True, type=Path)

    rotate_cmd = sub.add_parser("rotate")
    rotate_cmd.add_argument("--dir", required=True, type=Path)
    rotate_cmd.add_argument("--keep", required=True, type=int)

    args = parser.parse_args(argv)
    try:
        if args.command == "rotate":
            removed = obsolete_archives(list(args.dir.glob("*.dump.enc")), args.keep)
            for path in removed:
                path.unlink()
            print(f"Удалено устаревших копий: {len(removed)}")
            return
        key = _read_key()
        if args.command == "encrypt":
            args.output.write_bytes(encrypt_blob(key, args.input.read_bytes()))
            return
        args.output.write_bytes(decrypt_blob(key, args.input.read_bytes()))
    except BackupArchiveError as exc:
        print(f"ОШИБКА: {exc.message}", file=sys.stderr)
        raise SystemExit(1) from exc
    except OSError as exc:
        print(f"ОШИБКА: не удалось прочитать или записать файл ({exc.errno})", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
