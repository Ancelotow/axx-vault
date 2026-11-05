"""Create a standalone application on the current OS. No cross compilation."""
from pathlib import Path
import os
import platform
import shutil
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from make_icon import make_icons
from PySide6.QtWidgets import QApplication


def main():
    executable = ROOT / "engine" / ("XecretsCli.exe" if os.name == "nt" else "XecretsCli")
    if not executable.is_file():
        raise SystemExit("Compilez le moteur avec python tools/build_engine.py avant de créer le paquet.")
    app = QApplication([])
    assets = ROOT / "assets"
    image = make_icons(assets)
    icon = assets / "icon.ico"
    if sys.platform == "darwin":
        iconset = ROOT / "build/AxxVault.iconset"
        iconset.mkdir(parents=True, exist_ok=True)
        for size in (16, 32, 128, 256, 512):
            for factor in (1, 2):
                image.scaled(size * factor, size * factor).save(str(iconset / f"icon_{size}x{size}{'@2x' if factor == 2 else ''}.png"))
        icon = assets / "icon.icns"
        subprocess.run(["iconutil", "-c", "icns", str(iconset), "-o", str(icon)], check=True)
    args = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--windowed", "--onedir",
            "--name", "AxxVault", "--icon", str(icon), "--osx-bundle-identifier", "org.axxvault.desktop",
            "--add-binary", f"{executable}{os.pathsep}engine",
            "--add-data", f"{ROOT / 'LICENSE'}{os.pathsep}licenses",
            "--add-data", f"{ROOT / 'THIRD_PARTY.md'}{os.pathsep}licenses",
            "--add-data", f"{ROOT / 'licenses'}{os.pathsep}licenses",
            "--add-data", f"{assets / 'icon.png'}{os.pathsep}assets",
            "--exclude-module", "PySide6.QtWebEngineCore", "--exclude-module", "PySide6.QtWebEngineWidgets",
            str(ROOT / "run.py")]
    if (ROOT / "engine/SOURCES.json").exists():
        args[-1:-1] = ["--add-data", f"{ROOT / 'engine/SOURCES.json'}{os.pathsep}licenses"]
    subprocess.run(args, cwd=ROOT, check=True)
    if sys.platform == "darwin":
        import plistlib
        bundle = ROOT / "dist/AxxVault.app"
        plist = bundle / "Contents/Info.plist"
        info = plistlib.loads(plist.read_bytes())
        info["CFBundleShortVersionString"] = "1.0.0"
        info["CFBundleDocumentTypes"] = [{"CFBundleTypeName": "AxCrypt encrypted file", "CFBundleTypeExtensions": ["axx"],
                                         "CFBundleTypeRole": "Viewer", "LSHandlerRank": "Alternate"}]
        plist.write_bytes(plistlib.dumps(info))
        subprocess.run(["codesign", "--force", "--deep", "--sign", "-", str(bundle)], check=True)
        archive = ROOT / f"dist/AxxVault-macOS-{platform.machine()}.zip"
        subprocess.run(["ditto", "-c", "-k", "--sequesterRsrc", "--keepParent", str(bundle), str(archive)], check=True)
    else:
        archive = Path(shutil.make_archive(str(ROOT / f"dist/AxxVault-{platform.system()}-{platform.machine()}"), "zip", ROOT / "dist", "AxxVault"))
    # Corresponding sources accompany the binary, including all pinned GPL sources.
    source_archive = ROOT / "dist/AxxVault-sources.zip"
    with zipfile.ZipFile(source_archive, "w", zipfile.ZIP_DEFLATED) as zipped:
        ignored = {".git", ".venv", "engine", "build", "dist", "__pycache__", ".pytest_cache", "bin", "obj"}
        for directory, folders, files in os.walk(ROOT):
            folders[:] = [name for name in folders if name not in ignored]
            for name in files:
                path = Path(directory) / name
                if path.suffix not in {".pyc", ".pdb", ".spec"} and name != ".DS_Store":
                    zipped.write(path, Path("AxxVault") / path.relative_to(ROOT))
    print("Application :", archive)
    print("Sources correspondantes :", source_archive)


if __name__ == "__main__":
    main()
