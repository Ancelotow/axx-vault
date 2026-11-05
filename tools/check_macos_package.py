"""Check the signed macOS bundle and its embedded engine after packaging."""
from pathlib import Path
import os
import subprocess
import sys
import threading

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from axxvault.engine import Engine


def main():
    bundle = ROOT / "dist/AxxVault.app"
    subprocess.run(["codesign", "--verify", "--deep", "--strict", str(bundle)], check=True)
    engine = Engine(bundle / "Contents/Frameworks/engine/XecretsCli")
    _, data = engine.preview(ROOT / "tests/fixtures/helloworld-key-a-txt.axx", "a", threading.Event())
    if data != b"HelloWorld":
        raise SystemExit("Échec du déchiffrement avec le moteur empaqueté.")
    env = os.environ.copy()
    env["QT_QPA_PLATFORM"] = "offscreen"
    process = subprocess.Popen([str(bundle / "Contents/MacOS/AxxVault")], env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        stdout, stderr = process.communicate(timeout=3)
        raise SystemExit(f"L’application s’est arrêtée prématurément ({process.returncode}) : "
                         + stderr.decode("utf-8", errors="replace"))
    except subprocess.TimeoutExpired:
        print("Démarrage de l’application empaquetée : OK")
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.communicate()
    print("Signature locale et déchiffrement avec le moteur empaqueté : OK")


if __name__ == "__main__":
    main()
