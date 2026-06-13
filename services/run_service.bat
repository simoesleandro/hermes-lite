@echo off
REM Inicia o Hermes Lite (Flask + Waitress na porta 5050)
cd /d "%~dp0.."
python app.py
pause
