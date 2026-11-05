"""Build a pinned, unrestricted GPL Xecrets Cli from upstream sources."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import platform
import subprocess

ROOT = Path(__file__).resolve().parent.parent
SOURCES = {
    "xecrets-cli": ("https://github.com/xecrets/xecrets-cli.git", "f11d8142646228e67dee1a161f91a1f085a943fb"),
    "xecrets-net": ("https://github.com/axantum/xecrets-net.git", "1b9e6da70f4632d022107bfc69386df74f47569a"),
    "xecrets-slip39": ("https://github.com/xecrets/xecrets-slip39.git", "0574e08091927a3b156a5bcc1116490b1c3d5f44"),
}


def run(*args: str, cwd: Path = ROOT):
    subprocess.run(args, cwd=cwd, check=True)


def runtime() -> str:
    system = {"Darwin": "osx", "Windows": "win", "Linux": "linux"}[platform.system()]
    architecture = {"arm64": "arm64", "aarch64": "arm64", "amd64": "x64", "x86_64": "x64"}[platform.machine().lower()]
    return f"{system}-{architecture}"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime", default=runtime(), choices=["osx-arm64", "osx-x64", "win-x64", "win-arm64", "linux-x64", "linux-arm64"])
    parser.add_argument("--output", type=Path, default=ROOT / "engine")
    args = parser.parse_args()
    vendor = ROOT / "vendor"
    vendor.mkdir(exist_ok=True)
    for name, (url, revision) in SOURCES.items():
        folder = vendor / name
        if not folder.exists():
            folder.mkdir()
            run("git", "init", str(folder))
            run("git", "remote", "add", "origin", url, cwd=folder)
            run("git", "fetch", "--depth", "1", "origin", revision, cwd=folder)
            run("git", "checkout", "--detach", "FETCH_HEAD", cwd=folder)
        elif (folder / ".git").exists():
            actual = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=folder, text=True).strip()
            if actual != revision:
                raise SystemExit(f"Révision inattendue pour {name}. Utilisez un dossier vendor neuf.")
            changes = subprocess.check_output(["git", "status", "--porcelain", "--untracked-files=no"], cwd=folder, text=True)
            if changes:
                raise SystemExit(f"Sources modifiées pour {name}. Compilation interrompue.")
        # Source archives contain these folders without .git; they are already pinned.
    run("dotnet", "publish", str(vendor / "xecrets-cli/src/Xecrets.Cli/Xecrets.Cli.csproj"),
        "-c", "Release", "-r", args.runtime, "--self-contained", "true", "-o", str(args.output.resolve()),
        "-p:PublishAot=false", "-p:PublishSingleFile=true", "-p:PublishTrimmed=false", "-p:DebugType=None")
    manifest = {name: {"url": url, "commit": commit} for name, (url, commit) in SOURCES.items()}
    manifest["runtime"] = args.runtime
    (args.output / "SOURCES.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print("Moteur compilé :", args.output)


if __name__ == "__main__":
    main()
