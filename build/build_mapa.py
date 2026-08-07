# -*- coding: utf-8 -*-
"""build_mapa.py — src/<viaje>/viaje.yaml → pages/<viaje>/mapa.html.

La barra lateral del mapa ES el itinerario: mismos días/filas/modales que
genera render.py (proyección 1:1 del YAML, verificada). El cromo del mapa
(casillas, colapso por día, mapa base Leaflet) lo agregan mapa.css/mapa.js
en el navegador — el HTML servido no cambia.

Por ahora: barra lateral + mapa base. Las capas (marcadores/rutas) vienen después.
"""
import json
import sys

import render
from common import resolve_trip

sys.stdout.reconfigure(encoding="utf-8", errors="replace")


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
            # stops: posiciones de estación cuando coords ya es el trazo DENSO
            # (geometría OSM) y perdió la alineación 1 vértice = 1 estación
            stops = tr.get("stops")
            if stops:
                sp = render.parse_pts(stops, f"transits[{key}].stops")
                if sp:
                    entry["stops"] = [[a, b] for a, b in sp]
            transits[key] = entry
    # caja del viaje (vista inicial del mapa) + nombre del viaje (identidad
    # para el modo dev, en vez de olfatear la URL)
    pts = list(locs.values()) + [p for t in transits.values() for p in t["coords"]]
    geo = {"locations": locs, "transits": transits, "trip": _TRIP[0]}
    if pts:
        geo["bbox"] = [min(p[0] for p in pts), min(p[1] for p in pts),
                       max(p[0] for p in pts), max(p[1] for p in pts)]
    return {"<!--GEO-->": json.dumps(geo, ensure_ascii=False)}


_TRIP = [""]   # fijado por main antes del build (geo_tokens corre dentro)


def main():
    _TRIP[0] = resolve_trip(sys.argv)
    return render.build_and_verify(_TRIP[0], "plantilla-mapa.html", "mapa.html",
                                   extra=geo_tokens)


if __name__ == "__main__":
    sys.exit(main())
