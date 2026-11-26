import os

from app.ops.backup_archive import (
    BackupArchiveError, decrypt_blob, encrypt_blob, encryption_key_from_env, main, obsolete_archives,
)
from app.core.crypto import file_encryption_key


def test_backup_roundtrip_hides_plaintext():
    key = file_encryption_key("b" * 40)
    blob = encrypt_blob(key, b"PGDMP-secret-dump")
    assert b"PGDMP" not in blob
    assert blob.startswith(b"CAENC1")
    assert decrypt_blob(key, blob) == b"PGDMP-secret-dump"


def test_backup_wrong_key_is_rejected():
    blob = encrypt_blob(file_encryption_key("b" * 40), b"dump")
    try:
        decrypt_blob(file_encryption_key("c" * 40), blob)
    except BackupArchiveError as exc:
        assert "ключ" in exc.message
    else:
        raise AssertionError("ожидалась BackupArchiveError")


def test_rotation_keeps_newest_names(tmp_path):
    names = [f"crisis-analytics-2026102{index}T000000Z.dump.enc" for index in range(9)]
    for name in names:
        (tmp_path / name).write_bytes(b"x")
    removed = obsolete_archives(list(tmp_path.iterdir()), keep=7)
    assert len(removed) == 2
    assert {path.name for path in removed} == set(names[:2])


def test_cli_roundtrip_and_short_key(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("BACKUP_ENCRYPTION_KEY", "k" * 32)
    source = tmp_path / "in.bin"
    encrypted = tmp_path / "out.dump.enc"
    restored = tmp_path / "back.bin"
    source.write_bytes(b"payload")
    main(["encrypt", "--input", str(source), "--output", str(encrypted)])
    main(["decrypt", "--input", str(encrypted), "--output", str(restored)])
    assert restored.read_bytes() == b"payload"
    assert encryption_key_from_env()

    monkeypatch.setenv("BACKUP_ENCRYPTION_KEY", "short")
    try:
        main(["decrypt", "--input", str(encrypted), "--output", str(restored)])
    except SystemExit as exc:
        assert exc.code == 2
    else:
        raise AssertionError("ожидался выход с кодом 2")
    assert "BACKUP_ENCRYPTION_KEY" in capsys.readouterr().err
    assert os.environ["BACKUP_ENCRYPTION_KEY"] == "short"
