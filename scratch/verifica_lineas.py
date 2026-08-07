# -*- coding: utf-8 -*-
"""verifica_lineas.py — QA de geometría de los transits con stations en viaje.yaml.

Checks por transit:
  - vértices duplicados (consecutivos e idénticos no-consecutivos)
  - retrocesos: proyección along-track sobre el rumbo general; caída > umbral
  - zigzag: giros >120° entre segmentos largos (>300 m)
  - ratio largo-polilínea / distancia-recta extremos
  - correspondencia coords/stations (len iguales o stops presentes)

Solo lectura del YAML. Salida: scratch/geometria.json + texto en stdout.
"""
import json, math, sys, io

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import yaml

YAML_PATH = r"d:\dev\viajes\japon\viajes-2\src\2026-Japon\viaje.yaml"
OUT = r"d:\dev\viajes\japon\viajes-2\scratch\geometria.json"

R = 6371000.0

def hav(a, b):
    la1, lo1, la2, lo2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 2 * R * math.asin(math.sqrt(h))

def parse_coords(s):
    pts = []
    for tok in s.split():
        la, lo = tok.split(",")
        pts.append((float(la), float(lo)))
    return pts

def bearing_xy(pts):
    """proyección plana local (m) respecto al primer punto"""
    la0 = math.radians(pts[0][0])
    out = []
    for la, lo in pts:
        x = math.radians(lo - pts[0][1]) * math.cos(la0) * R
        y = math.radians(la - pts[0][0]) * R
        out.append((x, y))
    return out

def analyze(key, t):
    res = {"key": key, "mode": t.get("mode"), "line": t.get("line"), "issues": []}
    coords_s = t.get("coords")
    stations = t.get("stations") or []
    res["n_stations"] = len(stations)
    if not coords_s:
        res["n_coords"] = 0
        res["issues"].append("SIN coords (no se puede validar geometría ni posiciones)")
        return res
    pts = parse_coords(coords_s)
    res["n_coords"] = len(pts)
    stops = parse_coords(t["stops"]) if t.get("stops") else None
    if stops:
        res["n_stops"] = len(stops)
        if len(stops) != len(stations):
            res["issues"].append(f"stops({len(stops)}) != stations({len(stations)})")
    elif stations and len(pts) != len(stations):
        res["issues"].append(f"coords({len(pts)}) != stations({len(stations)}) y no hay stops")

    # duplicados
    dups = [i for i in range(1, len(pts)) if pts[i] == pts[i - 1]]
    if dups:
        res["issues"].append(f"vértices duplicados consecutivos en idx {dups}")
    seen = {}
    rep = []
    for i, p in enumerate(pts):
        if p in seen and i - seen[p] > 1:
            rep.append((seen[p], i))
        seen[p] = i
    if rep:
        res["issues"].append(f"vértices repetidos no consecutivos (posible loop): {rep[:5]}")

    # longitudes
    seglens = [hav(pts[i - 1], pts[i]) for i in range(1, len(pts))]
    plen = sum(seglens)
    straight = hav(pts[0], pts[-1])
    res["len_m"] = round(plen)
    res["straight_m"] = round(straight)
    if straight > 500 and plen / straight > 2.2:
        res["issues"].append(f"ratio largo/recta = {plen/straight:.2f} (posible desvío enorme)")

    # retrocesos along-track
    if straight > 200:
        xy = bearing_xy(pts)
        dx, dy = xy[-1][0] - xy[0][0], xy[-1][1] - xy[0][1]
        L = math.hypot(dx, dy)
        ux, uy = dx / L, dy / L
        along = [p[0] * ux + p[1] * uy for p in xy]
        runmax = along[0]
        backs = []
        for i, a in enumerate(along):
            if runmax - a > 500:
                backs.append((i, round(runmax - a)))
            runmax = max(runmax, a)
        if backs:
            res["issues"].append(f"retrocesos >500 m contra el rumbo general en idx {backs[:6]}")

    # zigzag: giros bruscos entre segmentos largos
    zz = []
    for i in range(1, len(pts) - 1):
        if seglens[i - 1] > 300 and seglens[i] > 300:
            xy = bearing_xy([pts[i - 1], pts[i], pts[i + 1]])
            v1 = (xy[1][0] - xy[0][0], xy[1][1] - xy[0][1])
            v2 = (xy[2][0] - xy[1][0], xy[2][1] - xy[1][1])
            dot = v1[0] * v2[0] + v1[1] * v2[1]
            n1 = math.hypot(*v1); n2 = math.hypot(*v2)
            ang = math.degrees(math.acos(max(-1, min(1, dot / (n1 * n2)))))
            if ang > 120:
                zz.append((i, round(ang)))
    if zz:
        res["issues"].append(f"zigzag: giro >120° en vértices {zz[:6]}")

    # segmentos absurdamente largos para modo local (no shinkansen)
    if t.get("line") not in ("Shinkansen",) and stations:
        longsegs = [(i, round(s)) for i, s in enumerate(seglens) if s > 30000]
        if longsegs:
            res["issues"].append(f"segmentos >30 km en modo local: {longsegs}")
    return res


def main():
    d = yaml.safe_load(open(YAML_PATH, encoding="utf-8"))
    out = []
    for key, t in d["transits"].items():
        if not isinstance(t, dict) or not t.get("stations"):
            continue
        out.append(analyze(key, t))
    json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    for r in out:
        flag = "!!" if r["issues"] else "ok"
        print(f"[{flag}] {r['key']} ({r.get('line')}) len={r.get('len_m')} straight={r.get('straight_m')}")
        for iss in r["issues"]:
            print("     -", iss)

if __name__ == "__main__":
    main()
