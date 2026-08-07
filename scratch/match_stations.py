# -*- coding: utf-8 -*-
"""match_stations.py — compara cada estación de los transits del YAML contra nodos OSM
(descargados por fetch_osm.py). Reporta distancia al nodo real, no-encontrados y
problemas de orden. Salida: scratch/station_match.json + resumen stdout.
"""
import json, math, os, re, sys, unicodedata

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import yaml

YAML_PATH = r"d:\dev\viajes\japon\viajes-2\src\2026-Japon\viaje.yaml"
CACHE = r"d:\dev\viajes\japon\viajes-2\scratch\osm_cache"
OUT = r"d:\dev\viajes\japon\viajes-2\scratch\station_match.json"
R = 6371000.0


def hav(a, b):
    la1, lo1, la2, lo2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 2 * R * math.asin(math.sqrt(h))


def norm_jp(s):
    if not s:
        return ""
    s = unicodedata.normalize("NFKC", s).strip().replace(" ", "").replace("　", "")
    s = re.sub(r"駅$", "", s)
    return s


def load_nodes():
    nodes = []
    for f in os.listdir(CACHE):
        if not f.endswith(".json"):
            continue
        try:
            d = json.load(open(os.path.join(CACHE, f), encoding="utf-8"))
        except Exception:
            continue
        for el in d.get("elements", []):
            t = el.get("tags", {})
            name = t.get("name") or t.get("name:ja") or ""
            if not name:
                continue
            nodes.append({
                "name": name, "norm": norm_jp(name),
                "lat": el["lat"], "lon": el["lon"],
                "railway": t.get("railway"), "highway": t.get("highway"),
                "station": t.get("station"), "operator": t.get("operator", ""),
                "en": t.get("name:en", ""), "src": f[:-5],
            })
    return nodes


def parse_coords(s):
    return [tuple(map(float, tok.split(","))) for tok in s.split()]


def main():
    d = yaml.safe_load(open(YAML_PATH, encoding="utf-8"))
    nodes = load_nodes()
    print(f"{len(nodes)} nodos OSM cargados", flush=True)
    by_norm = {}
    for n in nodes:
        by_norm.setdefault(n["norm"], []).append(n)

    results = []
    for key, t in d["transits"].items():
        if not isinstance(t, dict) or not t.get("stations"):
            continue
        stations = t["stations"]
        pts = parse_coords(t["coords"]) if t.get("coords") else []
        stops = parse_coords(t["stops"]) if t.get("stops") else None
        exp = None
        exp_src = "n/a"
        if stops and len(stops) == len(stations):
            exp, exp_src = stops, "stops"
        elif pts and len(pts) == len(stations):
            exp, exp_src = pts, "coords"
        rec = {"key": key, "line": t.get("line"), "exp_src": exp_src, "stations": []}
        matched_pts = []
        for i, st in enumerate(stations):
            code, jp, ro = (st + ["", "", ""])[:3]
            e = exp[i] if exp else None
            cands = by_norm.get(norm_jp(jp), [])
            entry = {"i": i, "code": code, "jp": jp, "romaji": ro}
            if e:
                entry["exp"] = [round(e[0], 6), round(e[1], 6)]
            if not cands:
                entry["status"] = "no_osm_match"
                # busca por romaji en name:en
                ron = unicodedata.normalize("NFKD", ro or "")
                ron = "".join(c for c in ron if not unicodedata.combining(c)).lower().replace("-", "").replace(" ", "")
                for n in nodes:
                    en = n["en"].lower().replace("-", "").replace(" ", "").replace("station", "")
                    if en and (en == ron or ron.startswith(en) or en.startswith(ron)):
                        entry["status"] = "matched_by_en"
                        cands = [n]
                        break
            if cands:
                if e:
                    best = min(cands, key=lambda n: hav(e, (n["lat"], n["lon"])))
                    dist = hav(e, (best["lat"], best["lon"]))
                    entry["osm"] = [round(best["lat"], 6), round(best["lon"], 6)]
                    entry["osm_name"] = best["name"]
                    entry["osm_kind"] = best.get("railway") or best.get("highway")
                    entry["dist_m"] = round(dist)
                    entry["status"] = "ok" if dist <= 300 else "far"
                    matched_pts.append((i, (best["lat"], best["lon"])))
                else:
                    # sin posición esperada: al menos existe; toma el más cercano a la polilínea si hay
                    if pts:
                        best = min(cands, key=lambda n: min(hav(p, (n["lat"], n["lon"])) for p in pts))
                        dmin = min(hav(p, (best["lat"], best["lon"])) for p in pts)
                        entry["osm"] = [round(best["lat"], 6), round(best["lon"], 6)]
                        entry["osm_name"] = best["name"]
                        entry["dist_to_polyline_m"] = round(dmin)
                        entry["status"] = "exists" if dmin <= 1500 else "exists_far_from_line"
                    else:
                        entry["status"] = "exists_no_pos"
                        entry["n_cands"] = len(cands)
            rec["stations"].append(entry)

        # chequeo de orden con las posiciones OSM matcheadas
        if len(matched_pts) >= 3:
            first, last = matched_pts[0][1], matched_pts[-1][1]
            la0 = math.radians(first[0])
            def xy(p):
                return (math.radians(p[1] - first[1]) * math.cos(la0) * R,
                        math.radians(p[0] - first[0]) * R)
            fx, fy = xy(last)
            L = math.hypot(fx, fy) or 1.0
            ux, uy = fx / L, fy / L
            alongs = [(i, xy(p)[0] * ux + xy(p)[1] * uy) for i, p in matched_pts]
            bad = [alongs[j][0] for j in range(1, len(alongs)) if alongs[j][1] < alongs[j - 1][1] - 400]
            if bad:
                rec["order_suspect_idx"] = bad
        results.append(rec)

    json.dump(results, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    for r in results:
        probs = [s for s in r["stations"] if s["status"] not in ("ok", "exists")]
        flag = "!!" if probs or r.get("order_suspect_idx") else "ok"
        print(f"[{flag}] {r['key']} ({r['line']}) src={r['exp_src']}")
        for s in probs:
            print(f"     - {s['jp']} ({s['romaji']}): {s['status']} dist={s.get('dist_m')} osm={s.get('osm')}")
        if r.get("order_suspect_idx"):
            print(f"     - ORDEN sospechoso en idx {r['order_suspect_idx']}")


if __name__ == "__main__":
    main()
