"""Assemble a Windows x64 portable bundle, also from a macOS build host.

Uses the official embeddable Python distribution and native Windows Qt wheels.
This prepares Windows binaries but does not execute or test them on this host.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
import shutil
import subprocess
import sys
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parent.parent
PYTHON_URL = "https://www.python.org/ftp/python/3.14.10/python-3.14.10-embed-amd64.zip"
PYTHON_SHA256 = "90905e64a840557d8c1bc4f5b74db3d7ee85e3ffb217611cac1c7813acea4159"


def main():
    output = ROOT / "build/windows-engine"
    subprocess.run([sys.executable, str(ROOT / "tools/build_engine.py"), "--runtime", "win-x64", "--output", str(output)], check=True)
    stage = ROOT / "build/windows-portable/AxxVault"
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir(parents=True)
    cache = ROOT / "build/windows-downloads"
    cache.mkdir(exist_ok=True)
    embedded = cache / "python-3.14.10-embed-amd64.zip"
    if not embedded.exists():
        urllib.request.urlretrieve(PYTHON_URL, embedded)
    if hashlib.sha256(embedded.read_bytes()).hexdigest() != PYTHON_SHA256:
        raise SystemExit("Empreinte inattendue du runtime Python Windows.")
    runtime = stage / "runtime"
    with zipfile.ZipFile(embedded) as archive:
        archive.extractall(runtime)
    wheels = cache / "wheels"
    wheels.mkdir(exist_ok=True)
    subprocess.run([sys.executable, "-m", "pip", "download", "--only-binary=:all:",
                    "--platform", "win_amd64", "--python-version", "3.14", "--implementation", "cp",
                    "--dest", str(wheels), "-r", str(ROOT / "requirements.txt")], check=True)
    site = runtime / "Lib/site-packages"
    site.mkdir(parents=True)
    hashes = {embedded.name: PYTHON_SHA256}
    for wheel in wheels.glob("*.whl"):
        hashes[wheel.name] = hashlib.sha256(wheel.read_bytes()).hexdigest()
        with zipfile.ZipFile(wheel) as archive:
            archive.extractall(site)
    (runtime / "python314._pth").write_text("python314.zip\n.\nLib/site-packages\n../app\nimport site\n", encoding="utf-8")
    application = stage / "app"
    application.mkdir()
    shutil.copytree(ROOT / "axxvault", application / "axxvault", ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copy2(ROOT / "run.py", application)
    shutil.copytree(ROOT / "assets", application / "assets")
    (application / "engine").mkdir()
    shutil.copy2(output / "XecretsCli.exe", application / "engine")
    licenses = stage / "licenses"
    shutil.copytree(ROOT / "licenses", licenses)
    for file in ("LICENSE", "THIRD_PARTY.md", "README.md"):
        shutil.copy2(ROOT / file, stage)
    shutil.copy2(output / "SOURCES.json", licenses)
    (stage / "AxxVault.cmd").write_bytes(b'@echo off\r\nstart "" "%~dp0runtime\\pythonw.exe" "%~dp0app\\run.py" %*\r\n')
    (stage / "LIRE-MOI.txt").write_text(
        "AxxVault pour Windows 11 x64\n\n"
        "Extrayez TOUT le dossier, puis double-cliquez sur AxxVault.cmd.\n"
        "Python, Qt et le moteur sont inclus ; aucune installation ni connexion nécessaire.\n"
        "Ce paquet a été assemblé sur macOS et doit encore être validé sur Windows.\n"
        "Consultez README.md pour les fonctions, les formats et les limites.\n", encoding="utf-8")
    import json
    (licenses / "WINDOWS_DOWNLOADS.json").write_text(json.dumps(hashes, indent=2) + "\n", encoding="utf-8")
    (ROOT / "dist").mkdir(exist_ok=True)
    archive = shutil.make_archive(str(ROOT / "dist/AxxVault-Windows-x64-portable"), "zip", stage.parent, stage.name)
    print("Paquet Windows préparé (exécution à valider sur Windows) :", archive)


if __name__ == "__main__":
    main()
