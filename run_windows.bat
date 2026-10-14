@echo off
cd /d "%~dp0"
if not exist .venv (
    echo First run: setting up, this takes a few minutes...
    py -3.12 -m venv .venv || python -m venv .venv
    call .venv\Scripts\activate.bat
    python -m pip install --upgrade pip
    pip install -r requirements.txt
) else (
    call .venv\Scripts\activate.bat
)
streamlit run app.py
pause
