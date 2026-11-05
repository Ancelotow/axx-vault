"""Isolated Xecrets process; plaintext is published only after authentication."""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import threading
from contextlib import contextmanager
from collections.abc import Iterator


class VaultError(Exception):
    pass


class Cancelled(VaultError):
    pass


def engine_path() -> Path:
    root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    return root / "engine" / ("XecretsCli.exe" if os.name == "nt" else "XecretsCli")


def quote_option(value: str) -> str:
    """Quote for Xecrets' own parser, including quotes and terminal backslashes.

    This is NOT shell quoting. No shell ever processes these arguments.
    The parser only treats a backslash as an escape immediately before a quote.
    """
    if "\0" in value:
        raise VaultError("Une valeur contient un caractère nul non pris en charge.")
    trailing = len(value) - len(value.rstrip("\\"))
    body = value[:-trailing] if trailing else value
    return '"' + body.replace('"', '\\"') + '"' + "\\" * trailing


def safe_name(original: str) -> str:
    """Treat encrypted metadata as untrusted and produce a portable basename."""
    name = original.replace("\\", "/").rsplit("/", 1)[-1]
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f\x7f]', "_", name).rstrip(" .")
    if not name or name in {".", ".."}:
        name = "document-dechiffre"
    if re.fullmatch(r"(?i:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])", name.split(".")[0]):
        name = "_" + name
    # Bound UTF-8 size while retaining a reasonable extension.
    if len(name.encode("utf-8")) > 220:
        suffix = Path(name).suffix[:20]
        stem = name[: -len(suffix)] if suffix else name
        while len((stem + suffix).encode("utf-8")) > 220:
            stem = stem[:-1]
        name = stem + suffix
    return name


def publish_file(staged: Path, destination: Path, cancel: threading.Event) -> Path:
    """Exclusive creation prevents replacing even a dangling destination symlink."""
    if cancel.is_set():
        raise Cancelled("Opération annulée.")
    # open('xb') is exclusive on both Windows and macOS.
    try:
        target = destination.open("xb")
    except FileExistsError:
        raise VaultError(f"Le fichier « {destination.name} » existe déjà. Choisissez un autre nom.") from None
    try:
        with target, staged.open("rb") as source:
            if os.name != "nt":
                os.fchmod(target.fileno(), 0o600)
            while block := source.read(1024 * 1024):
                if cancel.is_set():
                    raise Cancelled("Opération annulée.")
                target.write(block)
            target.flush()
            os.fsync(target.fileno())
            if cancel.is_set():
                raise Cancelled("Opération annulée.")
    except BaseException:
        destination.unlink(missing_ok=True)
        raise
    return destination


class Engine:
    def __init__(self, executable: Path | None = None):
        self.executable = executable or engine_path()

    def _run(self, args: list[str], password: str, work: Path, cancel: threading.Event) -> list[dict]:
        if not self.executable.is_file():
            raise VaultError("Le moteur de chiffrement manque. Compilez-le avec : python tools/build_engine.py")
        if not password:
            raise VaultError("Saisissez le mot de passe du fichier.")
        if cancel.is_set():
            raise Cancelled("Opération annulée.")
        options = ["--json-log", "--work-folder", str(work), "--password", password, *args]
        env = os.environ.copy()
        env["AXXVAULT_OPTIONS"] = " ".join(quote_option(x) for x in options)
        flags = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}
        try:
            process = subprocess.Popen(
                [str(self.executable), "--environment", "AXXVAULT_OPTIONS"],
                env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, **flags,
            )
        except OSError:
            raise VaultError("Impossible de démarrer le moteur de chiffrement.") from None
        finally:
            env.pop("AXXVAULT_OPTIONS", None)
        try:
            while True:
                if cancel.is_set():
                    process.kill()
                    process.communicate()
                    raise Cancelled("Opération annulée.")
                try:
                    _, stderr = process.communicate(timeout=0.15)
                    break
                except subprocess.TimeoutExpired:
                    continue
        finally:
            if process.poll() is None:
                process.kill()
                process.communicate()
        messages = []
        for line in stderr.decode("utf-8", errors="replace").splitlines():
            try:
                item = json.loads(line)
                if isinstance(item, dict):
                    messages.append(item)
            except ValueError:
                continue
        if process.returncode:
            # Do not expose engine logs: diagnostics may contain sensitive values.
            if process.returncode == 75:
                raise VaultError("Mot de passe incorrect, ou ce mot de passe ne donne pas accès au fichier.")
            if process.returncode in {2, 3, 5, 18, 21, 32, 33, 48, 81, 102}:
                raise VaultError("Accès au fichier impossible. Vérifiez ses droits et l’espace disque disponible.")
            if process.returncode == 12:
                raise Cancelled("Opération annulée.")
            raise VaultError("Opération impossible : fichier endommagé, format non pris en charge ou accès refusé "
                             f"(code {process.returncode}).")
        return messages

    @contextmanager
    def decrypted(self, source: Path, password: str, cancel: threading.Event) -> Iterator[Path]:
        source = source.resolve(strict=True)
        if not source.is_file():
            raise VaultError("Sélectionnez un fichier.")
        with tempfile.TemporaryDirectory(prefix="axxvault-") as directory:
            work = Path(directory)
            staged = work / "payload"
            messages = self._run(["--decrypt-file-to", str(source), str(staged)], password, work, cancel)
            names = [m["originalFileName"] for m in messages if isinstance(m.get("originalFileName"), str)]
            original = names[-1] if names else source.stem
            if not staged.is_file():
                raise VaultError("Le moteur n’a produit aucun fichier.")
            view_dir = work / "view"
            view_dir.mkdir(mode=0o700)
            result = view_dir / safe_name(original)
            staged.rename(result)
            yield result

    def decrypt(self, source: Path, folder: Path, password: str, cancel: threading.Event) -> Path:
        with self.decrypted(source, password, cancel) as staged:
            return publish_file(staged, folder / staged.name, cancel)

    def encrypt(self, source: Path, folder: Path, password: str, cancel: threading.Event) -> Path:
        source = source.resolve(strict=True)
        if not source.is_file():
            raise VaultError("Sélectionnez un fichier.")
        with tempfile.TemporaryDirectory(prefix="axxvault-") as directory:
            work = Path(directory)
            staged = work / "payload.axx"
            self._run(["--encrypt-file-to", str(source), str(staged), source.name], password, work, cancel)
            if not staged.is_file():
                raise VaultError("Le moteur n’a produit aucun fichier.")
            return publish_file(staged, folder / (source.name + ".axx"), cancel)

    def preview(self, source: Path, password: str, cancel: threading.Event) -> tuple[str, bytes]:
        with self.decrypted(source, password, cancel) as staged:
            if staged.stat().st_size > 32 * 1024 * 1024:
                raise VaultError("L’aperçu est limité à 32 Mo. Utilisez « Déchiffrer » pour ce fichier.")
            return staged.name, staged.read_bytes()
