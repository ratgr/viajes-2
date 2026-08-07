# -*- coding: utf-8 -*-
"""audita_places.py — inventario de campos faltantes en places: de viaje.yaml.

Reporta por place: gps/maps/description/image/hours/info, si la imagen
referenciada existe en static/, y clasifica por prioridad:
  A = usado como location en days (protagonista)
  B = POI (campo poi: presente, no protagonista)
  C = resto
Uso:  python scratch/audita_places.py [viaje]   (default 2026-Japon)
"""
import os
import sys
import yaml

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TRIP = sys.argv[1] if len(sys.argv) > 1 else "2026-Japon"
SRC = os.path.join(BASE, "src", TRIP)
PATH = os.path.join(SRC, "viaje.yaml")
STATIC = os.path.join(SRC, "static")

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
Y = yaml.safe_load(open(PATH, encoding="utf-8"))

# --- lugares usados como location en days (protagonistas)
used = set()
def scan(steps):
    for s in steps or []:
        if not isinstance(s, dict):
            continue
        if s.get("location"):
            used.add(s["location"])
        for o in s.get("options") or []:
            if isinstance(o, dict):
                if o.get("location"):
                    used.add(o["location"])
                scan(o.get("steps"))
                for x in o.get("options") or []:
                    if isinstance(x, dict):
                        if x.get("location"):
                            used.add(x["location"])
                        scan(x.get("steps"))
for day in Y.get("days", []):
    scan(day.get("steps"))

places = Y.get("places", {})
rows = []
for k, p in places.items():
    if not isinstance(p, dict):
        continue
    gps = str(p.get("gps") or "").strip()
    maps_ = str(p.get("maps") or "").strip()
    desc = str(p.get("description") or "").strip()
    img = str(p.get("image") or "").strip()
    hours = str(p.get("hours") or "").strip()
    hsrc = str(p.get("hours_source") or "").strip()
    info = str(p.get("info") or "").strip()
    img_ok = bool(img) and os.path.isfile(os.path.join(STATIC, img.replace("/", os.sep)))
    prio = "A" if k in used else ("B" if p.get("poi") else "C")
    rows.append(dict(key=k, prio=prio, gps=gps, maps=maps_, desc=desc, img=img,
                     img_ok=img_ok, hours=hours, hsrc=hsrc, info=info))

def count(pred):
    return sum(1 for r in rows if pred(r))

print(f"places totales: {len(rows)}  (A protagonistas: {count(lambda r: r['prio']=='A')}, "
      f"B pois: {count(lambda r: r['prio']=='B')}, C resto: {count(lambda r: r['prio']=='C')})")
print()
print("== resumen de faltantes ==")
print(f"  gps vacío:               {count(lambda r: not r['gps'])}")
print(f"  maps falta (gps sí hay): {count(lambda r: r['gps'] and not r['maps'])}")
print(f"  description falta:       {count(lambda r: not r['desc'])}")
print(f"  image falta:             {count(lambda r: not r['img'])}")
print(f"  image ROTA (no existe):  {count(lambda r: r['img'] and not r['img_ok'])}")
print(f"  hours falta:             {count(lambda r: not r['hours'])}")
print(f"  hours sin hours_source:  {count(lambda r: r['hours'] and not r['hsrc'])}")
print(f"  info falta:              {count(lambda r: not r['info'])}")
print()

for prio in "ABC":
    sub = [r for r in rows if r["prio"] == prio]
    incompletos = [r for r in sub if not r["maps"] or not r["desc"] or not r["img"]
                   or (r["img"] and not r["img_ok"]) or not r["hours"] or not r["info"]]
    print(f"== prioridad {prio} ({len(sub)} places, {len(incompletos)} con algo faltante) ==")
    for r in incompletos:
        faltas = []
        if not r["gps"]:
            faltas.append("GPS-VACIO")
        elif not r["maps"]:
            faltas.append("maps")
        if not r["desc"]:
            faltas.append("description")
        if not r["img"]:
            faltas.append("image")
        elif not r["img_ok"]:
            faltas.append(f"image-ROTA({r['img']})")
        if not r["hours"]:
            faltas.append("hours?")
        elif not r["hsrc"]:
            faltas.append("hours_source")
        if not r["info"]:
            faltas.append("info?")
        print(f"  {r['key']}: {', '.join(faltas)}")
    print()
