@echo off
cd /d "%~dp0backend"
if not exist .venv (
  py -m venv .venv
)
call .venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
if not exist .env copy .env.example .env
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
