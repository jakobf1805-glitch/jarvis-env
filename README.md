# J.A.R.V.I.S.

Ein lokaler deutschsprachiger Desktop-Assistent mit futuristischem Dashboard,
lokaler Spracheingabe (Vosk), lokaler KI-Stimme (Piper) und begrenzten,
bestätigungspflichtigen Computeraktionen. Das Dashboard ist nur über
**127.0.0.1** auf dem eigenen Rechner erreichbar.

## Was funktioniert bereits?

- Text- und Sprachbefehle im Dashboard
- Lokale deutsche Spracheingabe und lokale Piper-Stimme
- Ordner sowie Text-/Code-Dateien innerhalb von **Jarvis-Workspace**
- Google-Suche und Öffnen bestätigter Workspace-Dateien
- Linux-Desktop-App mit maximiertem Startfenster, **F11** für Vollbild und
  **Esc** zum Verlassen des Vollbilds

Jede Computeraktion wird im Fenster bestätigt. E-Mail und Kalender sind noch
nicht verbunden, weil dafür eine sichere OAuth-Anmeldung beim jeweiligen
Anbieter nötig ist.

## Sicherheit

Der API-Schlüssel gehört **nie** in Python-Dateien, die README, Git oder einen
Chat. J.A.R.V.I.S. liest ihn aus der Umgebungsvariable **OPENROUTER_API_KEY**
oder aus einer lokalen Datei außerhalb des Projektordners.

Die Datei **.gitignore** schließt Schlüssel, virtuelle Umgebungen, heruntergeladene
Modelle, Stimmen und lokale Arbeitsdaten aus. Vor einer öffentlichen
Veröffentlichung sollten alle früher versehentlich geteilten Schlüssel widerrufen
und neu erzeugt werden.

## Linux: frische Installation

Für die native Fenster-App werden auf Ubuntu zusätzlich GTK und WebKitGTK
benötigt:

~~~bash
sudo apt install python3-venv python3-gi gir1.2-webkit2-4.1
git clone https://github.com/DEIN-NAME/jarvis.git
cd jarvis
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements-core.txt
python download_models.py
~~~

Lege den OpenRouter-Schlüssel einmalig geschützt ab:

~~~bash
mkdir -p ~/.config/jarvis
read -rsp "OpenRouter API-Key: " jarvis_router_key; echo
printf '%s' "$jarvis_router_key" > ~/.config/jarvis/openrouter.key
chmod 600 ~/.config/jarvis/openrouter.key
unset jarvis_router_key
~~~

### Start im Browser

~~~bash
source .venv/bin/activate
python jarvis_dashboard.py --open-browser
~~~

Zum Beenden im Terminal **Strg+C** drücken.

### Start als Linux-Desktop-App

~~~bash
source .venv/bin/activate
python jarvis_app.py
~~~

Oder einmalig den Menüeintrag erstellen:

~~~bash
./install_jarvis_app.sh
~~~

Danach lässt sich „J.A.R.V.I.S.“ über die Ubuntu-Anwendungssuche starten.

## Spracheingabe

Unten rechts auf das Mikrofon klicken, sprechen und nochmals klicken. Der
erkannte Text wird zuerst im Eingabefeld angezeigt; dort kann er geprüft oder
korrigiert werden, bevor er mit „Senden“ an Jarvis geht. Das verhindert falsche
Computeraktionen bei einer unklaren Erkennung.

Für den Mikrofonknopf ist kein vorangestelltes „Jarvis“ nötig. Sage lieber
direkt: „Erstelle einen Ordner namens Testprojekt.“ Das verwendete kleine
Vosk-Modell ist schnell und lokal, kann Wörter aber falsch verstehen. Für
deutlich bessere Erkennung kann später optional ein lokales Whisper-Modell
integriert werden; auf älteren Rechnern wäre es merklich langsamer.

**wakeword_test.py** ist ein separater, optionaler Test für „Hey Jarvis“. Nicht
gleichzeitig mit der App starten, weil beide Programme auf das Mikrofon zugreifen.

~~~bash
python -m pip install -r requirements-wakeword.txt
python wakeword_test.py
~~~

## Windows

Der Dashboard-Kern läuft unter Windows im normalen Browser. Die Linux-Datei
**jarvis_app.py** ist bewusst keine Windows-App, weil sie GTK/WebKitGTK benutzt.

1. Das Repository klonen oder als ZIP herunterladen.
2. **setup_windows.bat** doppelklicken. Es erstellt **.venv**, installiert den
   Dashboard-Kern und lädt die Sprachmodelle.
3. In PowerShell den geschützten Schlüsselort öffnen:

   ~~~powershell
   New-Item -ItemType Directory -Force "$env:APPDATA\Jarvis"
   notepad "$env:APPDATA\Jarvis\openrouter.key"
   ~~~

   Den Schlüssel dort einfügen und die Datei speichern.
4. **start_windows.bat** doppelklicken. Es startet den lokalen Server und öffnet
   das Dashboard im Standardbrowser.

Eine native Windows-EXE ist ein möglicher späterer Schritt; sie muss auf Windows
gebaut und getestet werden.

## Für GitHub vorbereiten

Die großen Modelle und Stimmen werden mit **download_models.py** geladen und
nicht committed. Das Projekt nutzt derzeit die GPL-3.0-Lizenz in **COPYING**.

Nach einem letzten Sicherheitscheck kann ein lokales Repository erstellt werden:

~~~bash
git init -b main
git add .
git status
git commit -m "Initial public version of J.A.R.V.I.S."
~~~

Prüfe bei **git status** unbedingt, dass weder **.env**, Schlüssel-Dateien,
**bin/**, **.venv/**, **models/** noch **voices/** gelistet sind. Anschließend
im neuen leeren GitHub-Repository verbinden und hochladen:

~~~bash
git remote add origin https://github.com/DEIN-NAME/jarvis.git
git push -u origin main
~~~

## Lizenzen und Quellen

- Das Projekt steht unter GPL-3.0; siehe **COPYING**.
- Die Sprachmodelle haben eigene Lizenzen und werden nicht mit dem Repository
  ausgeliefert. Vosk-Modell: https://alphacephei.com/vosk/models; Piper-Stimme:
  https://huggingface.co/rhasspy/piper-voices.

