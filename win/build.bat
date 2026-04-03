@echo off
cd /d "%~dp0"
.venv\Scripts\activate
pyinstaller --onefile --name "Stenography" ..\main.py
pause