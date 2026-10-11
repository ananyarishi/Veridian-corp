#!/usr/bin/env bash
set -e
cd "$(dirname "$0")/backend"
if [ ! -d .venv ]; then python3 -m venv .venv; fi
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
if [ ! -f .env ]; then cp .env.example .env; fi
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
