"""Lädt die für den J.A.R.V.I.S.-Dashboard-Kern benötigten Modelle herunter.

Die Modell-Dateien werden absichtlich nicht in Git gespeichert: Sie sind groß
und haben eigene Lizenzen. Dieses Skript lädt sie aus ihren offiziellen Quellen.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent
MODELS_DIR = ROOT / "models"
VOICES_DIR = ROOT / "voices"
VOSK_NAME = "vosk-model-small-de-0.15"
VOSK_URL = f"https://alphacephei.com/vosk/models/{VOSK_NAME}.zip"
PIPER_VOICE = "de_DE-thorsten-medium"


def download_vosk() -> None:
    destination = MODELS_DIR / VOSK_NAME
    if destination.is_dir():
        print(f"Vosk-Modell bereits vorhanden: {destination}")
        return

    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="jarvis-vosk-") as temporary:
        archive_path = Path(temporary) / "model.zip"
        print("Lade deutsches Vosk-Modell herunter …")
        urllib.request.urlretrieve(VOSK_URL, archive_path)
        with zipfile.ZipFile(archive_path) as archive:
            root = MODELS_DIR.resolve()
            for member in archive.infolist():
                target = (MODELS_DIR / member.filename).resolve()
                if not target.is_relative_to(root):
                    raise RuntimeError("Unsicherer Pfad im Vosk-Archiv erkannt.")
            archive.extractall(MODELS_DIR)

    if not destination.is_dir():
        raise RuntimeError("Das Vosk-Archiv hatte nicht die erwartete Struktur.")
    print(f"Vosk-Modell bereit: {destination}")


def download_piper() -> None:
    voice_file = VOICES_DIR / f"{PIPER_VOICE}.onnx"
    if voice_file.is_file():
        print(f"Piper-Stimme bereits vorhanden: {voice_file}")
        return

    VOICES_DIR.mkdir(parents=True, exist_ok=True)
    print("Lade lokale Piper-Stimme herunter …")
    subprocess.run(
        [sys.executable, "-m", "piper.download_voices", "--data-dir", str(VOICES_DIR), PIPER_VOICE],
        check=True,
    )
    if not voice_file.is_file():
        raise RuntimeError("Die Piper-Stimme wurde nicht wie erwartet heruntergeladen.")
    print(f"Piper-Stimme bereit: {voice_file}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Lädt die lokalen J.A.R.V.I.S.-Sprachmodelle herunter.")
    parser.add_argument("--vosk-only", action="store_true", help="Nur die deutsche Spracherkennung laden.")
    parser.add_argument("--piper-only", action="store_true", help="Nur die lokale Stimme laden.")
    options = parser.parse_args()
    if options.vosk_only and options.piper_only:
        parser.error("Bitte nur eine der beiden Optionen verwenden.")
    if not options.piper_only:
        download_vosk()
    if not options.vosk_only:
        download_piper()


if __name__ == "__main__":
    main()
