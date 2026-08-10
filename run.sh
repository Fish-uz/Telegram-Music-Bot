#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
python -m pip install -r requirements.txt >/tmp/musicbot-pip.log 2>&1 || { cat /tmp/musicbot-pip.log; exit 1; }
if ! command -v ffmpeg >/dev/null 2>&1; then
  echo "FFmpeg no está instalado. Instálelo antes de ejecutar el bot." >&2
  exit 1
fi
python main.py
