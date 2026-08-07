# -*- coding: utf-8 -*-
"""cruza_ciudad.py — caza pasos NO-tren/avión que cruzan ciudad: caminatas o
conectores largos y opciones (restaurantes, típicamente cadenas) cuyo pin cae
lejos del área del día. Solo reporta; no edita."""
import math
import os
import sys

import yaml

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "build"))
from common import resolve_trip, trip_paths

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
TRIP = resolve_trip(sys.argv)
SRC_DIR, _p, _c = trip_paths(TRIP)
Y = yaml.safe_load(open(os.path.join(SRC_DIR, "viaje.yaml"), encoding="utf-8"))

LARGO_CAMINATA_KM = 2.0     # caminata/conector más largo que esto = sospechoso
LEJOS_OPCION_KM = 4.0       # opción a más de esto del centro del día = cadena mal resuelta


def pt(key):
    pl = Y["places"].get(key) or {}
    g = str(pl.get("gps") or "").strip()
    if not g:
        return None
    try:
        la, lo = (float(x) for x in g.split(","))
        return (la, lo)
    except ValueError:
        return None


def km(a, b):
    dy = (b[0] - a[0]) * 111.0
    dx = (b[1] - a[1]) * 111.0 * math.cos(math.radians(a[0]))
    return math.hypot(dx, dy)


def tr_len_km(key):
    tr = Y["transits"].get(key) or {}
    c = str(tr.get("coords") or "").strip()
    if not c:
        return None, tr.get("mode")
    pts = []
    for p in c.split():
        la, lo = (float(x) for x in p.split(","))
        pts.append((la, lo))
    total = sum(km(pts[i - 1], pts[i]) for i in range(1, len(pts)))
    return total, tr.get("mode")


def walk_steps(steps, dentro_opcion, out):
    for s in steps or []:
        if not isinstance(s, dict):
            continue
        out.append((s, dentro_opcion))
        for grupo in s.get("options") or []:
            if not isinstance(grupo, dict):
                continue
            walk_steps(grupo.get("steps"), True, out)
            for op in grupo.get("options") or []:
                if isinstance(op, dict):
                    out.append((op, True))
                    walk_steps(op.get("steps"), True, out)


for di, day in enumerate(Y.get("days", []), 1):
    filas = []
    walk_steps(day.get("steps"), False, filas)
    # centro del día = mediana de las locations PRINCIPALES (fuera de opciones)
    pts_dia = [pt(s.get("location")) for s, en_op in filas
               if not en_op and s.get("location") and pt(s.get("location"))]
    if not pts_dia:
        continue
    lat_c = sorted(p[0] for p in pts_dia)[len(pts_dia) // 2]
    lon_c = sorted(p[1] for p in pts_dia)[len(pts_dia) // 2]
    centro = (lat_c, lon_c)
    avisos = []
    for s, en_op in filas:
        loc = s.get("location")
        if loc:
            p = pt(loc)
            if p and en_op and km(centro, p) > LEJOS_OPCION_KM:
                avisos.append(f"OPCIÓN LEJOS: {loc} a {km(centro, p):.1f} km del centro del día (¿cadena/sucursal equivocada?)")
        t = s.get("transit")
        if t:
            largo, mode = tr_len_km(t)
            if largo is not None and mode not in ("train", "flight", "bus", "ferry", "monorail", "tour") and largo > LARGO_CAMINATA_KM:
                avisos.append(f"CAMINATA LARGA: {t} ({mode}) mide {largo:.1f} km")
    if avisos:
        print(f"— {day.get('title', f'día {di}')} (centro {lat_c:.4f},{lon_c:.4f})")
        for a in dict.fromkeys(avisos):
            print("   ", a)
