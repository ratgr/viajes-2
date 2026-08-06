# -*- coding: utf-8 -*-
"""build_mapa.py — src/<viaje>/viaje.yaml → pages/<viaje>/mapa.html.

La barra lateral del mapa ES el itinerario: mismos días/filas/modales que
genera render.py (proyección 1:1 del YAML, verificada). El cromo del mapa
(casillas, colapso por día, mapa base Leaflet) lo agregan mapa.css/mapa.js
en el navegador — el HTML servido no cambia.

Por ahora: barra lateral + mapa base. Las capas (marcadores/rutas) vienen después.
"""
import os
import subprocess
import sys

import render
from common import resolve_trip

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
BUILD = os.path.dirname(os.path.abspath(__file__))


def main():
    trip = resolve_trip(sys.argv)
    render.build_page(trip, "plantilla-mapa.html", "mapa.html")
    r = subprocess.run([sys.executable, os.path.join(BUILD, "verify_roundtrip.py"),
                        trip, "mapa.html"],
                       capture_output=True, text=True, encoding="utf-8")
    print(r.stdout.strip() or r.stderr.strip())
    return r.returncode


if __name__ == "__main__":
    sys.exit(main())
