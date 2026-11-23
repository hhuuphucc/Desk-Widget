#!/bin/bash
cd "$(dirname "$0")" || exit 1

if [ -x "./.venv/bin/python3" ]; then
  PY="./.venv/bin/python3"
elif [ -x "./venv/bin/python3" ]; then
  PY="./venv/bin/python3"
else
  PY="$(command -v python3)"
fi

if [ -z "$PY" ]; then
  echo "Khong tim thay Python 3. Hay cai Python 3.10+ (python.org hoac brew install python python-tk)."
  exit 1
fi

nohup "$PY" widget.py >/dev/null 2>&1 &
