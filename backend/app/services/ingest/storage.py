"""Хранение загруженных файлов в каталоге сервера: staging и зашифрованные оригиналы."""

import json
import logging
import os
import shutil
import stat
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.core.config import Settings
from app.core.crypto import encrypt, file_encryption_key
from app.services.errors import NotFoundError, PermissionDeniedError
from app.services.ingest.filenames import original_filename, safe_stem

logger = logging.getLogger(__name__)

STAGING_META = "meta.json"
STAGING_FILE = "content.bin"
DATASETS_DIR = "datasets"
STAGING_DIR = "staging"
DIR_MODE = 0o700
FILE_MODE = 0o600


@dataclass
class StagingRecord:
    id: uuid.UUID
    user_id: int
    original_filename: str
    sha256: str
    size_bytes: int
    created_at: datetime
    path: Path


class FileStorage:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.root = settings.data_dir.resolve()
        self.staging = self.root / STAGING_DIR
        self.datasets = self.root / DATASETS_DIR

    def prepare(self) -> None:
        self._ensure_dir(self.root)
        self._ensure_dir(self.staging)
        self._ensure_dir(self.datasets)
        self._assert_writable(self.root)

    def put_staging(self, user_id: int, filename: str, content: bytes, digest: str) -> StagingRecord:
        self.prepare()
        self.cleanup_expired()
        staging_id = uuid.uuid4()
        directory = self.staging / str(staging_id)
        self._ensure_dir(directory)
        payload = directory / STAGING_FILE
        payload.write_bytes(content)
        self._chmod(payload, FILE_MODE)
        record = {
            "id": str(staging_id),
            "user_id": user_id,
            "original_filename": original_filename(filename),
            "sha256": digest,
            "size_bytes": len(content),
            "created_at": datetime.now(UTC).isoformat(),
        }
        meta = directory / STAGING_META
        meta.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
        self._chmod(meta, FILE_MODE)
        return self._record(directory, record)

    def get_staging(self, staging_id: uuid.UUID, user_id: int) -> tuple[StagingRecord, bytes]:
        directory = self._contained(self.staging, str(staging_id))
        meta_path = directory / STAGING_META
        file_path = directory / STAGING_FILE
        if not meta_path.is_file() or not file_path.is_file():
            raise NotFoundError("Загруженный файл не найден или срок его хранения истёк")
        record = json.loads(meta_path.read_text(encoding="utf-8"))
        created = datetime.fromisoformat(record["created_at"])
        if created + timedelta(minutes=self.settings.upload_staging_ttl_minutes) < datetime.now(UTC):
            shutil.rmtree(directory, ignore_errors=True)
            raise NotFoundError("Загруженный файл не найден или срок его хранения истёк")
        if record["user_id"] != user_id:
            raise PermissionDeniedError("Нет доступа к загруженному файлу")
        return self._record(directory, record), file_path.read_bytes()

    def drop_staging(self, staging_id: uuid.UUID) -> None:
        directory = self.staging / str(staging_id)
        if directory.exists() and self._is_relative_to(directory, self.staging):
            shutil.rmtree(directory, ignore_errors=True)

    def store_encrypted(self, dataset_id: int, content: bytes) -> tuple[bytes, bytes]:
        self.prepare()
        key = file_encryption_key(self.settings.dataset_encryption_key.get_secret_value())
        ciphertext, nonce = encrypt(key, content)
        path = self.dataset_path(dataset_id)
        path.write_bytes(nonce + ciphertext)
        self._chmod(path, FILE_MODE)
        return ciphertext, nonce

    def delete_dataset_file(self, dataset_id: int) -> None:
        path = self.dataset_path(dataset_id)
        if path.is_file() and self._is_relative_to(path, self.datasets):
            path.unlink()

    def dataset_path(self, dataset_id: int) -> Path:
        return self.datasets / f"{int(dataset_id)}.enc"

    def cleanup_expired(self) -> None:
        ttl = timedelta(minutes=self.settings.upload_staging_ttl_minutes)
        now = datetime.now(UTC)
        if not self.staging.is_dir():
            return
        for directory in self.staging.iterdir():
            meta = directory / STAGING_META
            if not meta.is_file():
                continue
            try:
                created = datetime.fromisoformat(json.loads(meta.read_text(encoding="utf-8"))["created_at"])
            except (OSError, ValueError, KeyError, json.JSONDecodeError):
                continue
            if created + ttl < now or _stale(directory, ttl):
                shutil.rmtree(directory, ignore_errors=True)

    def _contained(self, root: Path, name: str) -> Path:
        candidate = (root / name).resolve()
        if not self._is_relative_to(candidate, root.resolve()):
            raise NotFoundError("Загруженный файл не найден или срок его хранения истёк")
        return candidate

    def _ensure_dir(self, path: Path) -> None:
        path.mkdir(parents=True, exist_ok=True)
        self._chmod(path, DIR_MODE)

    @staticmethod
    def _chmod(path: Path, mode: int) -> None:
        try:
            os.chmod(path, mode)
        except OSError:
            logger.debug("Не удалось выставить права %o на %s", mode, path)

    def _assert_writable(self, path: Path) -> None:
        if not os.access(path, os.W_OK | os.R_OK | os.X_OK):
            raise PermissionError(f"Нет прав на запись в каталог данных {path}")

    @staticmethod
    def _is_relative_to(path: Path, root: Path) -> bool:
        try:
            path.resolve().relative_to(root.resolve())
            return True
        except ValueError:
            return False

    @staticmethod
    def _record(directory: Path, record: dict) -> StagingRecord:
        return StagingRecord(
            id=uuid.UUID(record["id"]),
            user_id=record["user_id"],
            original_filename=record["original_filename"],
            sha256=record["sha256"],
            size_bytes=record["size_bytes"],
            created_at=datetime.fromisoformat(record["created_at"]),
            path=directory / STAGING_FILE,
        )


def export_name(dataset_name: str, ext: str) -> str:
    return f"{safe_stem(dataset_name)}.{ext}"


def _stale(directory: Path, ttl: timedelta) -> bool:
    try:
        age = time.time() - directory.stat()[stat.ST_MTIME]
    except OSError:
        return False
    return age > ttl.total_seconds() * 2
