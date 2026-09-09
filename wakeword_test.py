"""
Testet die Wake-Word-Erkennung mit openWakeWord und dem vortrainierten
"hey jarvis"-Modell. Läuft komplett lokal auf der CPU.

Vorher einmalig ausführen (lädt die Modelle herunter):
    python3 -c "import openwakeword; openwakeword.utils.download_models()"
"""

import pyaudio
import numpy as np
import openwakeword
from openwakeword.model import Model

# "hey_jarvis_v0.1" ist eines der mitgelieferten, vortrainierten Modelle.
model = Model(
    wakeword_model_paths=[openwakeword.models["hey_jarvis"]["model_path"]]
)

CHUNK = 1280  # 80ms bei 16kHz -> das Format, das openWakeWord erwartet
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000
THRESHOLD = 0.5  # ab diesem Score gilt das Wort als erkannt

audio = pyaudio.PyAudio()
stream = audio.open(
    format=FORMAT,
    channels=CHANNELS,
    rate=RATE,
    input=True,
    frames_per_buffer=CHUNK,
)

print("Lausche auf 'Hey Jarvis'... (Strg+C zum Beenden)")

try:
    while True:
        audio_chunk = np.frombuffer(
            stream.read(CHUNK, exception_on_overflow=False), dtype=np.int16
        )
        prediction = model.predict(audio_chunk)

        for wakeword, score in prediction.items():
            if score > THRESHOLD:
                print(f"✅ Wake-Word erkannt: {wakeword} (Score: {score:.2f})")

except KeyboardInterrupt:
    print("\nBeendet.")
finally:
    stream.stop_stream()
    stream.close()
    audio.terminate()
