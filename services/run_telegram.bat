@echo off
REM Bot Telegram bidirecional (long polling)
cd /d "%~dp0.."
python -m services.telegram_bot
pause
