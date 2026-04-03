@echo off
cd /d "%~dp0"
copy ..\main.py . >nul
call .venv\Scripts\activate.bat
docker build -t mybuilder .
docker run --rm -v "%cd%:/out" mybuilder cp /app/dist/Stenography /out/dist/
del main.py
echo Готово: %cd%\Stenography
pause