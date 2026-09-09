"""Native GTK-Fensterhülle für das lokale J.A.R.V.I.S.-Dashboard."""

import socket
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).parent
URL = "http://127.0.0.1:8765"

# Das virtuelle Environment enthält die Projektpakete; GTK/WebKitGTK werden
# auf Ubuntu als Systempakete bereitgestellt.
SYSTEM_PYTHON_PACKAGES = Path("/usr/lib/python3/dist-packages")
if SYSTEM_PYTHON_PACKAGES.exists():
    sys.path.append(str(SYSTEM_PYTHON_PACKAGES))

import gi  # noqa: E402

gi.require_version("Gdk", "3.0")
gi.require_version("Gtk", "3.0")
gi.require_version("WebKit2", "4.1")
from gi.repository import Gdk, GLib, Gtk, WebKit2  # noqa: E402


def dashboard_running() -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as connection:
        connection.settimeout(0.2)
        return connection.connect_ex(("127.0.0.1", 8765)) == 0


class JarvisWindow(Gtk.Window):
    def __init__(self):
        super().__init__(title="J.A.R.V.I.S.")
        self.set_default_size(1280, 800)
        self.set_size_request(800, 550)
        self._is_fullscreen = False
        # Beim Start den verfügbaren Bildschirm ausnutzen, aber die
        # Fensterknöpfe sichtbar lassen. F11 schaltet auf echtes Vollbild um.
        self.maximize()
        self.server_process = None
        if not dashboard_running():
            self.server_process = subprocess.Popen(
                [sys.executable, str(ROOT / "jarvis_dashboard.py")], cwd=ROOT
            )

        self.web_view = WebKit2.WebView()
        settings = self.web_view.get_settings()
        settings.set_enable_media(True)
        settings.set_enable_media_stream(True)
        settings.set_enable_webrtc(True)
        # Eine Desktop-Assistenten-App soll Antworten nicht erst nach jedem
        # Klick abspielen müssen. Das betrifft nur diese lokale WebView.
        settings.set_media_playback_requires_user_gesture(False)
        settings.set_media_playback_allows_inline(True)
        self.web_view.connect("permission-request", self.request_permission)
        self.web_view.connect("key-press-event", self.on_key_press)
        self.add(self.web_view)
        self.connect("key-press-event", self.on_key_press)
        self.connect("destroy", self.close)
        GLib.timeout_add(500, self.load_dashboard)

    def on_key_press(self, _widget, event):
        if event.keyval == Gdk.KEY_F11:
            if self._is_fullscreen:
                self.unfullscreen()
            else:
                self.fullscreen()
            self._is_fullscreen = not self._is_fullscreen
            return True
        if event.keyval == Gdk.KEY_Escape and self._is_fullscreen:
            self.unfullscreen()
            self._is_fullscreen = False
            return True
        return False

    def request_permission(self, _web_view, request):
        if not isinstance(request, WebKit2.UserMediaPermissionRequest):
            return False
        dialog = Gtk.MessageDialog(
            transient_for=self,
            flags=0,
            message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.YES_NO,
            text="Darf J.A.R.V.I.S. das Mikrofon verwenden?",
        )
        response = dialog.run()
        if response == Gtk.ResponseType.YES:
            request.allow()
        else:
            request.deny()
        dialog.destroy()
        return True

    def load_dashboard(self):
        if dashboard_running():
            # Eine Versionsnummer in der URL verhindert, dass WebKit eine alte
            # HTML/CSS-Ansicht nach einem Update weiterverwendet.
            dashboard = ROOT / "jarvis_dashboard.html"
            version = dashboard.stat().st_mtime_ns if dashboard.exists() else 0
            self.web_view.load_uri(f"{URL}/?v={version}")
            self.show_all()
            return False
        return True

    def close(self, *_args):
        if self.server_process and self.server_process.poll() is None:
            self.server_process.terminate()
        Gtk.main_quit()


if __name__ == "__main__":
    if "--check" in sys.argv:
        print("GTK/WebKitGTK verfügbar.")
    else:
        window = JarvisWindow()
        try:
            Gtk.main()
        except KeyboardInterrupt:
            # Strg+C im Terminal beendet die lokale App ohne einen unnötigen
            # Python-Traceback und räumt den gestarteten Dashboard-Server auf.
            window.close()
