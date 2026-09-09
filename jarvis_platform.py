"""Kleine, paketfreie Plattform-Helfer für den J.A.R.V.I.S.-Kern.

Das Dashboard soll sowohl unter Linux als auch unter Windows laufen können.
Dieses Modul enthält nur Betriebssystem-Unterschiede; die Sicherheitsprüfung
von Workspace-Pfaden bleibt weiterhin im Dashboard-Server.
"""

from __future__ import annotations

import ctypes
import os
import subprocess
import sys
from pathlib import Path


_CPU_SAMPLE: tuple[int, int] | None = None


def config_directory() -> Path:
    """Gibt den passenden privaten Konfigurationsordner zurück.

    ``JARVIS_CONFIG_DIR`` ist bewusst als Override vorhanden: Er erleichtert
    portable Installationen und Tests, ohne einen Schlüssel ins Projekt zu
    schreiben.
    """
    override = os.getenv("JARVIS_CONFIG_DIR")
    if override:
        return Path(override).expanduser()
    if sys.platform == "win32":
        return Path(os.getenv("APPDATA", Path.home() / "AppData" / "Roaming")) / "Jarvis"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "Jarvis"
    return Path(os.getenv("XDG_CONFIG_HOME", Path.home() / ".config")) / "jarvis"


def openrouter_key_file() -> Path:
    """Speicherort des lokalen OpenRouter-Schlüssels, plattformübergreifend."""
    return config_directory() / "openrouter.key"


def workspace_directory() -> Path:
    """Standard-Workspace; ein eigener Pfad kann über die Umgebung gesetzt werden."""
    override = os.getenv("JARVIS_WORKSPACE")
    return Path(override).expanduser() if override else Path.home() / "Jarvis-Workspace"


def open_with_default_application(path: Path) -> None:
    """Öffnet einen bereits geprüften lokalen Pfad mit der Standardanwendung.

    Der Aufrufer muss vorher sicherstellen, dass ``path`` im erlaubten
    Workspace liegt. Unter Windows existiert ``os.startfile`` nur zur Laufzeit,
    daher wird es nicht auf anderen Plattformen angesprochen.
    """
    if sys.platform == "win32":
        os.startfile(str(path))  # type: ignore[attr-defined]
        return
    command = ["open", str(path)] if sys.platform == "darwin" else ["xdg-open", str(path)]
    subprocess.Popen(command, start_new_session=True)


def _linux_cpu_times() -> tuple[int, int]:
    fields = [int(value) for value in Path("/proc/stat").read_text().splitlines()[0].split()[1:]]
    total = sum(fields)
    idle = fields[3] + (fields[4] if len(fields) > 4 else 0)
    return total, idle


def _linux_memory_percent() -> int:
    memory: dict[str, int] = {}
    for line in Path("/proc/meminfo").read_text().splitlines():
        key, value = line.split(":", 1)
        memory[key] = int(value.strip().split()[0])
    return round(100 * (1 - memory["MemAvailable"] / memory["MemTotal"]))


def _windows_cpu_times() -> tuple[int, int]:
    """Liest Windows-CPU-Zeitwerte ohne zusätzliche Python-Abhängigkeit."""

    class FileTime(ctypes.Structure):
        _fields_ = [("dwLowDateTime", ctypes.c_ulong), ("dwHighDateTime", ctypes.c_ulong)]

    idle = FileTime()
    kernel = FileTime()
    user = FileTime()
    if not ctypes.windll.kernel32.GetSystemTimes(ctypes.byref(idle), ctypes.byref(kernel), ctypes.byref(user)):
        raise OSError("GetSystemTimes ist fehlgeschlagen")

    def value(file_time: FileTime) -> int:
        return (file_time.dwHighDateTime << 32) + file_time.dwLowDateTime

    # Die Windows-Kernelzeit enthält die Idle-Zeit bereits.
    return value(kernel) + value(user), value(idle)


def _windows_memory_percent() -> int:
    """Liest die Speicherbelegung über die offizielle Windows-API."""

    class MemoryStatusEx(ctypes.Structure):
        _fields_ = [
            ("dwLength", ctypes.c_ulong),
            ("dwMemoryLoad", ctypes.c_ulong),
            ("ullTotalPhys", ctypes.c_ulonglong),
            ("ullAvailPhys", ctypes.c_ulonglong),
            ("ullTotalPageFile", ctypes.c_ulonglong),
            ("ullAvailPageFile", ctypes.c_ulonglong),
            ("ullTotalVirtual", ctypes.c_ulonglong),
            ("ullAvailVirtual", ctypes.c_ulonglong),
            ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
        ]

    status = MemoryStatusEx()
    status.dwLength = ctypes.sizeof(status)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
        raise OSError("GlobalMemoryStatusEx ist fehlgeschlagen")
    return int(status.dwMemoryLoad)


def system_load() -> dict[str, int]:
    """Liefert CPU- und Arbeitsspeicher-Auslastung für Linux/Windows.

    Bei unbekannten Plattformen oder einem nicht verfügbaren Systemwert wird
    0 geliefert. Dadurch bleibt die Benutzeroberfläche bedienbar statt an
    einer reinen Anzeige-Funktion zu scheitern.
    """
    global _CPU_SAMPLE
    try:
        if sys.platform == "win32":
            total, idle = _windows_cpu_times()
            memory = _windows_memory_percent()
        elif sys.platform.startswith("linux"):
            total, idle = _linux_cpu_times()
            memory = _linux_memory_percent()
        else:
            return {"cpu": 0, "memory": 0}

        cpu = 0
        if _CPU_SAMPLE is not None:
            previous_total, previous_idle = _CPU_SAMPLE
            delta_total = total - previous_total
            if delta_total:
                cpu = round(100 * (1 - (idle - previous_idle) / delta_total))
        _CPU_SAMPLE = (total, idle)
        return {"cpu": max(0, min(100, cpu)), "memory": max(0, min(100, memory))}
    except (IndexError, KeyError, OSError, ValueError):
        # Ein Dashboard darf wegen einer fehlenden Metrik nicht ausfallen.
        return {"cpu": 0, "memory": 0}
