#!/usr/bin/env bash
# Corre el bot localmente. Crea el venv la primera vez.
set -e
cd "$(dirname "$0")"
if [ ! -d .venv ]; then
  python3 -m venv .venv
  . .venv/bin/activate
  pip install -q --upgrade pip
  pip install -q -r requirements.txt
else
  . .venv/bin/activate
fi
python main.py
