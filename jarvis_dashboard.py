"""Lokaler Server für das J.A.R.V.I.S.-Dashboard."""

import json
import os
import subprocess
import sys
import tempfile
import threading
import uuid
import webbrowser
from datetime import datetime
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import quote_plus, urlparse

from openai import OpenAI
from vosk import KaldiRecognizer, Model as VoskModel, SetLogLevel

from jarvis_platform import (
    open_with_default_application,
    openrouter_key_file,
    system_load,
    workspace_directory,
)

HOST, PORT = "127.0.0.1", 8765
ROOT = Path(__file__).parent
MODEL = os.getenv("JARVIS_MODEL", "openrouter/free")
VOSK_MODEL_PATH = ROOT / "models" / "vosk-model-small-de-0.15"
PIPER_VOICE = os.getenv("JARVIS_VOICE", "de_DE-thorsten-medium")
PIPER_DATA_DIR = ROOT / "voices"
KEY_FILE = openrouter_key_file()
WORKSPACE = workspace_directory()
PENDING_ACTIONS = {}
PENDING_ACTIONS_LOCK = threading.Lock()
INSTRUCTIONS = """Du bist J.A.R.V.I.S., ein ruhiger, kompetenter deutschsprachiger Assistent.
Antworte präzise. Für lokale Dateien, Code, Ordner, Programme oder Websuche nutzt du
immer die bereitgestellten Werkzeuge. Behaupte niemals, eine Aktion sei erledigt, bevor
deren Werkzeug-Ergebnis vorliegt. Alle Aktionen werden dem Nutzer vor der Ausführung
zur Bestätigung gezeigt. Verwende nur relative Pfade innerhalb des Jarvis-Workspace."""

TOOLS = [
    {"type": "function", "function": {"name": "list_files", "description": "Listet Dateien und Ordner im Jarvis-Workspace auf.", "parameters": {"type": "object", "properties": {"path": {"type": "string", "description": "Relativer Ordnerpfad, leer für den Workspace."}}, "required": ["path"]}}},
    {"type": "function", "function": {"name": "read_text_file", "description": "Liest eine Textdatei im Jarvis-Workspace.", "parameters": {"type": "object", "properties": {"path": {"type": "string", "description": "Relativer Dateipfad."}}, "required": ["path"]}}},
    {"type": "function", "function": {"name": "create_folder", "description": "Erstellt einen Ordner im Jarvis-Workspace.", "parameters": {"type": "object", "properties": {"path": {"type": "string", "description": "Relativer Ordnerpfad."}}, "required": ["path"]}}},
    {"type": "function", "function": {"name": "create_text_file", "description": "Erstellt oder überschreibt eine Text- oder Codedatei im Jarvis-Workspace.", "parameters": {"type": "object", "properties": {"path": {"type": "string", "description": "Relativer Dateipfad."}, "content": {"type": "string", "description": "Vollständiger Dateiinhalt."}}, "required": ["path", "content"]}}},
    {"type": "function", "function": {"name": "open_path", "description": "Öffnet eine Datei oder einen Ordner im Jarvis-Workspace mit der Standardanwendung.", "parameters": {"type": "object", "properties": {"path": {"type": "string", "description": "Relativer Pfad."}}, "required": ["path"]}}},
    {"type": "function", "function": {"name": "search_web", "description": "Öffnet eine Google-Suche im Standardbrowser.", "parameters": {"type": "object", "properties": {"query": {"type": "string", "description": "Suchanfrage."}}, "required": ["query"]}}},
]

def api_key() -> str:
    """Liest den Schlüssel aus der Umgebung oder einer Datei mit Modus 600."""
    return os.getenv("OPENROUTER_API_KEY", "") or (KEY_FILE.read_text().strip() if KEY_FILE.exists() else "")


def system_status() -> dict:
    """Liefert Live-Systemwerte unter Linux und Windows."""
    with PENDING_ACTIONS_LOCK:
        pending = len(PENDING_ACTIONS)
    return {**system_load(), "pending_actions": pending}


def workspace_path(relative_path: str) -> Path:
    """Lässt nur Pfade innerhalb des dafür vorgesehenen Workspace zu."""
    path = (WORKSPACE / relative_path).resolve()
    try:
        path.relative_to(WORKSPACE.resolve())
    except ValueError as error:
        raise ValueError("Der Pfad muss innerhalb von Jarvis-Workspace liegen.") from error
    return path


def action_label(name: str, arguments: dict) -> str:
    value = arguments.get("path", arguments.get("query", ""))
    labels = {
        "list_files": "Dateien auflisten",
        "read_text_file": "Textdatei lesen",
        "create_folder": "Ordner erstellen",
        "create_text_file": "Datei erstellen oder überschreiben",
        "open_path": "Datei oder Ordner öffnen",
        "search_web": "Websuche öffnen",
    }
    label = f"{labels.get(name, name)}: {value}"
    if name == "create_text_file":
        preview = str(arguments.get("content", ""))[:1_500]
        label += "\n\nInhalt-Vorschau:\n" + preview
    return label


def execute_action(name: str, arguments: dict) -> dict:
    """Führt ausschließlich die eng begrenzten, bestätigten Desktop-Aktionen aus."""
    WORKSPACE.mkdir(parents=True, exist_ok=True)
    if name == "list_files":
        path = workspace_path(arguments.get("path", ""))
        if not path.is_dir():
            raise ValueError("Dieser Ordner existiert nicht.")
        entries = sorted(item.name + ("/" if item.is_dir() else "") for item in path.iterdir())[:100]
        return {"message": "Inhalt von „%s“: %s" % (path.relative_to(WORKSPACE), ", ".join(entries) or "leer")}
    if name == "read_text_file":
        path = workspace_path(arguments["path"])
        if not path.is_file():
            raise ValueError("Diese Datei existiert nicht.")
        content = path.read_text(encoding="utf-8", errors="replace")[:20_000]
        return {"message": "Datei gelesen: %s\n\n%s" % (path.relative_to(WORKSPACE), content)}
    if name == "create_folder":
        path = workspace_path(arguments["path"])
        path.mkdir(parents=True, exist_ok=True)
        return {"message": "Ordner erstellt: %s" % path.relative_to(WORKSPACE)}
    if name == "create_text_file":
        path = workspace_path(arguments["path"])
        content = str(arguments["content"])
        if len(content) > 100_000:
            raise ValueError("Der Dateiinhalt ist zu groß.")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return {"message": "Datei gespeichert: %s" % path.relative_to(WORKSPACE)}
    if name == "open_path":
        path = workspace_path(arguments["path"])
        if not path.exists():
            raise ValueError("Dieser Pfad existiert nicht.")
        open_with_default_application(path)
        return {"message": "Geöffnet: %s" % path.relative_to(WORKSPACE)}
    if name == "search_web":
        query = str(arguments["query"]).strip()
        if not query:
            raise ValueError("Die Suchanfrage ist leer.")
        webbrowser.open("https://www.google.com/search?q=" + quote_plus(query))
        return {"message": "Google-Suche geöffnet: " + query}
    raise ValueError("Unbekanntes Werkzeug.")


def answer(message: str) -> dict:
    # OpenRouter implements the OpenAI chat-completions interface. The free
    # router chooses one currently available no-cost model for each request.
    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key(),
    )
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": INSTRUCTIONS},
            {"role": "user", "content": message},
        ],
        tools=TOOLS,
        tool_choice="auto",
    )
    assistant_message = response.choices[0].message
    actions = []
    for tool_call in assistant_message.tool_calls or []:
        try:
            arguments = json.loads(tool_call.function.arguments)
            if tool_call.function.name not in {tool["function"]["name"] for tool in TOOLS}:
                raise ValueError("Nicht erlaubtes Werkzeug")
            action_id = uuid.uuid4().hex
            with PENDING_ACTIONS_LOCK:
                PENDING_ACTIONS[action_id] = (tool_call.function.name, arguments)
            actions.append({"id": action_id, "label": action_label(tool_call.function.name, arguments)})
        except Exception as error:
            actions.append({"id": "", "label": "Ungültige Aktion: " + str(error)})
    text = assistant_message.content or ("Ich habe eine Aktion vorbereitet. Bitte bestätige sie." if actions else "Ich konnte gerade keine Antwort erzeugen.")
    return {"answer": text, "actions": actions}


def transcribe(audio_data: bytes) -> dict[str, object]:
    """Transkribiert 16-kHz-PCM lokal und liefert mögliche Alternativen."""
    recognizer = KaldiRecognizer(VOSK_MODEL, 16_000)
    recognizer.SetWords(True)
    recognizer.SetMaxAlternatives(3)
    recognizer.AcceptWaveform(audio_data)
    result = json.loads(recognizer.FinalResult())
    alternatives = []
    for item in result.get("alternatives", []):
        candidate = str(item.get("text", "")).strip()
        if candidate and candidate not in alternatives:
            alternatives.append(candidate)
    text = str(result.get("text", "")).strip() or (alternatives[0] if alternatives else "")
    if not text:
        raise RuntimeError("Ich konnte dich nicht verstehen. Bitte sprich etwas deutlicher.")
    return {"text": text, "alternatives": alternatives[:3]}


def synthesize(text: str) -> bytes:
    """Erzeugt eine WAV-Antwort mit der lokalen Piper-KI-Stimme."""
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as output:
        filename = output.name
    try:
        subprocess.run(
            [sys.executable, "-m", "piper", "--data-dir", str(PIPER_DATA_DIR),
             "-m", PIPER_VOICE, "-f", filename, "--", text[:2_000]],
            check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=60,
        )
        return Path(filename).read_bytes()
    finally:
        if os.path.exists(filename):
            os.unlink(filename)

class DashboardHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs): super().__init__(*args, directory=str(ROOT), **kwargs)
    def do_GET(self):
        request_path = urlparse(self.path).path
        if request_path == "/api/status":
            self.send_json({"ok": True, **system_status()})
            return
        if request_path not in ("/", "/index.html", "/jarvis_dashboard.html"):
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        self.path = "/jarvis_dashboard.html"
        return super().do_GET()
    def do_POST(self):
        if self.path not in ("/api/chat", "/api/transcribe", "/api/speech", "/api/action"):
            self.send_error(HTTPStatus.NOT_FOUND); return
        try:
            size = int(self.headers.get("Content-Length", "0"))
            payload = self.rfile.read(size)
            if self.path == "/api/transcribe":
                self.send_json({"ok": True, **transcribe(payload)})
            elif self.path == "/api/speech":
                text = str(json.loads(payload).get("text", "")).strip()
                self.send_audio(synthesize(text))
            elif self.path == "/api/action":
                request = json.loads(payload)
                action_id = str(request.get("id", ""))
                if not request.get("approved"):
                    self.send_json({"ok": True, "message": "Aktion abgelehnt."})
                    return
                with PENDING_ACTIONS_LOCK:
                    action = PENDING_ACTIONS.pop(action_id, None)
                if action is None:
                    raise ValueError("Diese Aktion ist abgelaufen oder ungültig.")
                name, arguments = action
                self.send_json({"ok": True, **execute_action(name, arguments)})
            else:
                message = str(json.loads(payload).get("message", "")).strip()
                if not message: raise ValueError("Bitte gib einen Befehl ein.")
                self.send_json({"ok": True, **answer(message), "time": datetime.now().strftime("%H:%M")})
        except Exception as error: self.send_json({"ok": False, "error": str(error)}, HTTPStatus.BAD_REQUEST)
    def send_json(self, payload, status=HTTPStatus.OK):
        body = json.dumps(payload, ensure_ascii=False).encode()
        self.send_response(status); self.send_header("Content-Type", "application/json; charset=utf-8"); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)
    def send_audio(self, body: bytes):
        self.send_response(HTTPStatus.OK); self.send_header("Content-Type", "audio/wav"); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)
    def end_headers(self):
        # Die WebKit-App darf keine alte Dashboard-Version aus dem Cache zeigen.
        self.send_header("Cache-Control", "no-store, max-age=0")
        self.send_header("Pragma", "no-cache")
        return super().end_headers()
    def log_message(self, format, *args): return

if __name__ == "__main__":
    if not api_key():
        raise SystemExit("OpenRouter-Key fehlt. Siehe README.md.")
    if not VOSK_MODEL_PATH.exists():
        raise SystemExit("Das lokale deutsche Sprachmodell fehlt. Siehe README.md.")
    SetLogLevel(-1)
    VOSK_MODEL = VoskModel(str(VOSK_MODEL_PATH))
    server = ThreadingHTTPServer((HOST, PORT), DashboardHandler)
    print(f"J.A.R.V.I.S. Dashboard läuft auf http://{HOST}:{PORT}")
    print("Zum Beenden: Strg+C")
    if "--open-browser" in sys.argv:
        webbrowser.open(f"http://{HOST}:{PORT}")
    try: server.serve_forever()
    except KeyboardInterrupt: print("\nDashboard beendet.")
    finally: server.server_close()
