$ErrorActionPreference = "Stop"
if (!(Test-Path .venv)) {
  python -m venv .venv
}
.\.venv\Scripts\python -m pip install -r backend\requirements.txt
.\.venv\Scripts\python backend\manage.py migrate
.\.venv\Scripts\python backend\manage.py runserver 127.0.0.1:8000
