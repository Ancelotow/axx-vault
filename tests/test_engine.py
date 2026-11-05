from pathlib import Path
import hashlib
import os
import threading

import pytest

from axxvault.engine import Cancelled, Engine, VaultError, engine_path, publish_file, safe_name


@pytest.fixture
def engine():
    if not engine_path().is_file():
        pytest.fail("Compilez le vrai moteur avec python tools/build_engine.py avant les tests.")
    return Engine()


@pytest.mark.integration
@pytest.mark.parametrize("password", [
    'Pâsswörd "secret" avec espaces',
    "secret-with-final-backslash\\",
    "trailing-double-backslash\\\\",
    '--wipe /tmp/nope ^ & $(echo nope) " \\"',
])
def test_roundtrip_and_original_name(engine, tmp_path, password):
    source = tmp_path / 'rapport été.txt'
    source.write_bytes("Bonjour !\nÉté 2026 🗝".encode())
    output = tmp_path / "encrypted"
    output.mkdir()
    encrypted = engine.encrypt(source, output, password, threading.Event())
    assert encrypted.name == source.name + ".axx"
    assert source.read_bytes() not in encrypted.read_bytes()
    name, data = engine.preview(encrypted, password, threading.Event())
    assert name == source.name
    assert data == source.read_bytes()
    restored = tmp_path / "restored"
    restored.mkdir()
    result = engine.decrypt(encrypted, restored, password, threading.Event())
    assert result.name == source.name
    assert result.read_bytes() == source.read_bytes()


@pytest.mark.integration
@pytest.mark.parametrize("fixture,password,sha256", [
    ("helloworld-key-a-txt.axx", "a", hashlib.sha256(b"HelloWorld").hexdigest()),
    ("short-txt-AES256.axx", "PâsswördètMëd§½ Lôñg|´¨", "2de4823aa40ed2a6d040e7ba67bf60e3b1ae5c1f1bc2391ba8435ec7d1597f49"),
    ("short-txt-V2AES128.axx", "PâsswördètMëd§½ Lôñg|´¨", "2de4823aa40ed2a6d040e7ba67bf60e3b1ae5c1f1bc2391ba8435ec7d1597f49"),
])
def test_independent_axcrypt_fixtures(engine, fixture, password, sha256):
    path = Path(__file__).parent / "fixtures" / fixture
    _, data = engine.preview(path, password, threading.Event())
    assert hashlib.sha256(data).hexdigest() == sha256


@pytest.fixture
def encrypted(engine, tmp_path):
    source = tmp_path / "secret.bin"
    # Larger than 1 MiB verifies that our GPL build has no programmatic size restriction.
    source.write_bytes(os.urandom(1024 * 1024 + 77))
    output = tmp_path / "encrypted"
    output.mkdir()
    password = "a long and correct secret"
    return source, engine.encrypt(source, output, password, threading.Event()), password


@pytest.mark.integration
def test_large_file(engine, encrypted, tmp_path):
    source, ciphertext, password = encrypted
    output = tmp_path / "restored"
    output.mkdir()
    result = engine.decrypt(ciphertext, output, password, threading.Event())
    assert result.read_bytes() == source.read_bytes()


@pytest.mark.integration
def test_invalid_password_leaves_no_output(engine, encrypted, tmp_path):
    source, ciphertext, _ = encrypted
    before = ciphertext.read_bytes()
    output = tmp_path / "restored"
    output.mkdir()
    with pytest.raises(VaultError, match="Mot de passe incorrect"):
        engine.decrypt(ciphertext, output, "incorrect password", threading.Event())
    assert list(output.iterdir()) == []
    assert ciphertext.read_bytes() == before
    assert source.exists()


@pytest.mark.integration
def test_tampering_leaves_no_plaintext(engine, encrypted, tmp_path):
    _, ciphertext, password = encrypted
    data = bytearray(ciphertext.read_bytes())
    data[-16] ^= 0x40
    ciphertext.write_bytes(data)
    output = tmp_path / "restored"
    output.mkdir()
    with pytest.raises(VaultError):
        engine.decrypt(ciphertext, output, password, threading.Event())
    assert list(output.iterdir()) == []


@pytest.mark.integration
def test_existing_file_never_overwritten(engine, encrypted, tmp_path):
    source, ciphertext, password = encrypted
    existing = source.read_bytes()
    with pytest.raises(VaultError, match="existe déjà"):
        engine.decrypt(ciphertext, tmp_path, password, threading.Event())
    assert source.read_bytes() == existing


@pytest.mark.integration
def test_actual_process_can_be_cancelled(engine, tmp_path):
    source = tmp_path / "large.bin"
    source.write_bytes(os.urandom(8 * 1024 * 1024))
    output = tmp_path / "encrypted"
    output.mkdir()
    cancel = threading.Event()
    timer = threading.Timer(0.03, cancel.set)
    timer.start()
    try:
        with pytest.raises(Cancelled):
            engine.encrypt(source, output, "a good enough password", cancel)
    finally:
        timer.join()
    assert list(output.iterdir()) == []
    assert source.stat().st_size == 8 * 1024 * 1024


@pytest.mark.integration
def test_preview_removes_staging_file(engine, encrypted):
    _, ciphertext, password = encrypted
    with engine.decrypted(ciphertext, password, threading.Event()) as path:
        assert path.exists()
        temporary = path.parent.parent
    assert not temporary.exists()


@pytest.mark.integration
def test_password_absent_from_process_arguments(engine, tmp_path, monkeypatch):
    import axxvault.engine as module
    real_popen = module.subprocess.Popen
    commands = []

    def capture(command, **kwargs):
        commands.append(command)
        return real_popen(command, **kwargs)

    monkeypatch.setattr(module.subprocess, "Popen", capture)
    source = tmp_path / "empty.txt"
    source.touch()
    output = tmp_path / "encrypted"
    output.mkdir()
    engine.encrypt(source, output, "password absent from argv", threading.Event())
    assert commands == [[str(engine.executable), "--environment", "AXXVAULT_OPTIONS"]]
    assert "AXXVAULT_OPTIONS" not in os.environ


def test_publish_refuses_dangling_symlink(tmp_path):
    if os.name == "nt":
        pytest.skip("Windows symlink privilege is not assumed")
    staged = tmp_path / "staged"
    staged.write_bytes(b"data")
    target = tmp_path / "target"
    target.symlink_to(tmp_path / "nonexistent")
    with pytest.raises(VaultError, match="existe déjà"):
        publish_file(staged, target, threading.Event())
    assert target.is_symlink()


@pytest.mark.parametrize("original,expected", [
    ("../../escape.txt", "escape.txt"),
    ("C:\\Windows\\evil.exe", "evil.exe"),
    ("/absolute/file.txt", "file.txt"),
    ("CON.txt", "_CON.txt"),
    ("..", "document-dechiffre"),
    ("name\x00.txt", "name_.txt"),
])
def test_metadata_names_cannot_escape_destination(original, expected):
    assert safe_name(original) == expected


def test_metadata_names_bound_utf8_size():
    result = safe_name("é" * 500 + ".txt")
    assert len(result.encode()) <= 220
    assert result.endswith(".txt")
