#!/bin/sh
# corrida rápida: genera pages/2026-Japon (build + verificación 1:1)
cd "$(dirname "$0")" || exit 1
python build/build_itinerario.py 2026-Japon "$@"
