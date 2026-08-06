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
            pt = render.parse_pts(gps, f"places[{key}]")
            if not pt:
                continue          # malformado: ya quedó en DIAGNOSTICS
            locs[key] = [pt[0][0], pt[0][1]]
    transits = {}
    for key, tr in render.TRANSITS.items():
        coords = tr.get("coords")
        if coords:
            parsed = render.parse_pts(coords, f"transits[{key}]")
            if not parsed:
                continue
            pts = [[a, b] for a, b in parsed]
            entry = {"coords": pts, "color": tr.get("color", "#7a6f63"),
                     "mode": tr.get("mode", "walk")}
            # rieles: cada vértice ES una estación ([código, jp, romaji]) —
            # el mapa las pinta como paradas con nombre si las cuentas calzan
            stations = tr.get("stations")
            if stations:
                entry["stations"] = [
                    (s[2] or s[1]) if isinstance(s, list) and len(s) >= 3 else str(s)
                    for s in stations
                ]
            transits[key] = entry
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
