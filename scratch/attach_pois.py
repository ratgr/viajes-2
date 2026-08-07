# -*- coding: utf-8 -*-
"""attach_pois.py — engancha PUNTOS DE INTERÉS a las caminatas: todo place
del catálogo que quede a ≤ RADIO m del trazo de una caminata y que NO sea ya
una parada del itinerario (location de algún paso) se anota en la línea
`pois:` de ese transit (empalme de TEXTO: comentarios intactos). Idempotente:
reescribe la línea pois: completa cada corrida."""
import math
import os
import re
import sys

import yaml

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "build"))
from common import resolve_trip, trip_paths

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
TRIP = resolve_trip(sys.argv)
SRC_DIR, _p, _c = trip_paths(TRIP)
PATH = os.path.join(SRC_DIR, "viaje.yaml")
RADIO = 100.0

Y = yaml.safe_load(open(PATH, encoding="utf-8"))
text = open(PATH, encoding="utf-8").read()


def dist(a, b):
    dy = (b[0] - a[0]) * 111000
    dx = (b[1] - a[1]) * 111000 * math.cos(math.radians(a[0]))
    return math.hypot(dx, dy)


def seg_dist(p, a, b):
    den = dist(a, b) ** 2 or 1e-9
    t = ((p[0] - a[0]) * (b[0] - a[0]) * 111000 ** 2 +
         (p[1] - a[1]) * (b[1] - a[1]) * (111000 * math.cos(math.radians(a[0]))) ** 2) / den
    t = max(0.0, min(1.0, t))
    return dist(p, (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t))


# lugares que YA son paradas (location en cualquier paso, options incluidas)
used = set()
def scan(steps):
    for s in steps or []:
        if not isinstance(s, dict):
            continue
        if s.get("location"):
            used.add(s["location"])
        for o in s.get("options") or []:
            if isinstance(o, dict):
                scan(o.get("steps"))
                for x in o.get("options") or []:
                    if isinstance(x, dict):
                        if x.get("location"):
                            used.add(x["location"])
                        scan(x.get("steps"))
for day in Y.get("days", []):
    scan(day.get("steps"))

cand = {}
for k, pl in Y.get("places", {}).items():
    if k in used or not pl.get("gps"):
        continue
    try:
        la, lo = str(pl["gps"]).split(",")
        cand[k] = (float(la), float(lo))
    except ValueError:
        pass

print(f"candidatos (places sin usar como parada): {len(cand)}")
tot = 0
for tk, tr in Y.get("transits", {}).items():
    if tr.get("mode") != "walk" or not tr.get("coords"):
        continue
    try:
        pts = [tuple(map(float, p.split(","))) for p in str(tr["coords"]).split()]
    except ValueError:
        continue
    cerca = []
    for k, p in cand.items():
        d = min(seg_dist(p, pts[i - 1], pts[i]) for i in range(1, len(pts)))
        if d <= RADIO:
            cerca.append((d, k))
    if not cerca:
        continue
    cerca.sort()
    val = " ".join(k for _d, k in cerca)
    linea_flow = re.search(rf"^(  {re.escape(tk)}: \{{)", text, re.M)
    if linea_flow:
        # estilo flow: meter/reescribir pois: dentro de las llaves
        text = re.sub(rf"^(  {re.escape(tk)}: \{{[^\n]*?)(, pois: '[^']*')?(\}})$",
                      lambda m: m.group(1) + f", pois: '{val}'" + m.group(3),
                      text, count=1, flags=re.M)
    else:
        blk = re.search(rf"^(  {re.escape(tk)}:\n)((?:    .*\n)*)", text, re.M)
        if not blk:
            continue
        body = re.sub(r"^    pois:.*\n", "", blk.group(2), flags=re.M)
        body += f"    pois: {val}\n"
        text = text[:blk.start(2)] + body + text[blk.end(2):]
    tot += len(cerca)
    print(f"  {tk}: {', '.join(k for _d, k in cerca)}")

open(PATH, "w", encoding="utf-8", newline="").write(text)
print(f"pois enganchados: {tot}")
