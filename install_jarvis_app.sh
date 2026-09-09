#!/usr/bin/env bash
set -eu

project_dir="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
data_dir="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
python_path="$project_dir/.venv/bin/python"
if [ ! -x "$python_path" ]; then
    python_path="$project_dir/bin/python"
fi
if [ ! -x "$python_path" ]; then
    python_path="$(command -v python3)"
fi
mkdir -p "$data_dir"
sed -e "s|@PROJECT_DIR@|$project_dir|g" -e "s|@PYTHON@|$python_path|g" \
    "$project_dir/jarvis.desktop.in" > "$data_dir/jarvis.desktop"
chmod 644 "$data_dir/jarvis.desktop"
echo "J.A.R.V.I.S. wurde zum Anwendungsmenü hinzugefügt."
