@echo off
rem corrida rapida: genera pages/2026-Japon (build + verificacion 1:1)
cd /d "%~dp0"
python build/build_itinerario.py 2026-Japon %*
