# -*- coding: utf-8 -*-
"""build_mapa.py — src/<viaje>/viaje.yaml → pages/<viaje>/mapa.html.

La barra lateral del mapa ES el itinerario: mismos días/filas/modales que
genera render.py (proyección 1:1 del YAML, verificada). El cromo del mapa
(casillas, colapso por día, mapa base Leaflet) lo agregan mapa.css/mapa.js
en el navegador — el HTML servido no cambia.

Por ahora: barra lateral + mapa base. Las capas (marcadores/rutas) vienen después.
"""
import json
import os
import subprocess
import sys

import render
from common import resolve_trip

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
BUILD = os.path.dirname(os.path.abspath(__file__))


def geo_tokens():
    """geometría por clave YAML para el mapa: gps de places, coords de transits.
    (Se inyecta como JSON aparte: las coordenadas no son parte de las filas.)"""
    locs = {}
    for key, pl in render.PLACES.items():
        gps = pl.get("gps")
        if gps:
            la, lo = str(gps).split(",")
            locs[key] = [float(la), float(lo)]
    transits = {}
    for key, tr in render.TRANSITS.items():
        coords = tr.get("coords")
        if coords:
            pts = [[float(a), float(b)] for a, b in (p.split(",") for p in str(coords).split())]
            transits[key] = {"coords": pts, "color": tr.get("color", "#7a6f63"),
                             "mode": tr.get("mode", "walk")}
    geo = {"locations": locs, "transits": transits}
    return {"<!--GEO-->": json.dumps(geo, ensure_ascii=False)}


def main():
    trip = resolve_trip(sys.argv)
    render.build_page(trip, "plantilla-mapa.html", "mapa.html", extra=geo_tokens)
    r = subprocess.run([sys.executable, os.path.join(BUILD, "verify_roundtrip.py"),
                        trip, "mapa.html"],
                       capture_output=True, text=True, encoding="utf-8")
    print(r.stdout.strip() or r.stderr.strip())
    return r.returncode


if __name__ == "__main__":
    sys.exit(main())
