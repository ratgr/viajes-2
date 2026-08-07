# -*- coding: utf-8 -*-
"""fetch_osm.py — descarga nodos de estaciones/paradas de OSM (Overpass) por bbox,
con caché en scratch/osm_cache/. Espacia consultas >=10 s y reintenta en 429/504.
"""
import json, os, sys, time, urllib.request, urllib.error

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
CACHE = r"d:\dev\viajes\japon\viajes-2\scratch\osm_cache"
os.makedirs(CACHE, exist_ok=True)
API = "https://overpass-api.de/api/interpreter"
UA = "viajes-2-qa/1.0 (ratgricardo@gmail.com)"

BBOXES = {
    # name: (S, W, N, E, incluye_bus)
    "osaka":     (34.62, 135.38, 34.83, 135.58, False),
    "nara":      (34.60, 135.55, 34.72, 135.86, False),
    "kyoto":     (34.92, 135.63, 35.07, 135.83, True),
    "hiroshima": (34.27, 132.25, 34.42, 132.50, False),
    "tokyo":     (35.52, 139.58, 35.80, 139.95, True),
    "shonan":    (35.28, 139.45, 35.56, 139.72, False),
}

# estaciones fuera de los bboxes (shinkansen): nombre jp -> coord aproximada del YAML
OUTLIERS = {
    "新神戸": (34.706288, 135.195468),
    "岡山": (34.666750, 133.918266),
    "名古屋": (35.170694, 136.881637),
    "新横浜": (35.507480, 139.617109),
}


def query(q, tag):
    path = os.path.join(CACHE, tag + ".json")
    if os.path.exists(path) and os.path.getsize(path) > 100:
        print(f"{tag}: cached", flush=True)
        return
    data = ("data=" + urllib.parse.quote(q)).encode()
    for attempt in range(5):
        try:
            req = urllib.request.Request(API, data=data, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=240) as r:
                body = r.read()
            json.loads(body)  # valida
            open(path, "wb").write(body)
            print(f"{tag}: OK {len(body)} bytes", flush=True)
            time.sleep(10)
            return
        except urllib.error.HTTPError as e:
            print(f"{tag}: HTTP {e.code}, retry {attempt+1}", flush=True)
            time.sleep(20 * (attempt + 1))
        except Exception as e:
            print(f"{tag}: {e}, retry {attempt+1}", flush=True)
            time.sleep(15 * (attempt + 1))
    print(f"{tag}: FAILED", flush=True)


def main():
    import urllib.parse  # noqa
    for name, (s, w, n, e, bus) in BBOXES.items():
        parts = [f'node["railway"~"^(station|halt|tram_stop)$"]({s},{w},{n},{e});']
        if bus:
            parts.append(f'node["highway"="bus_stop"]({s},{w},{n},{e});')
        q = f'[out:json][timeout:200];({"".join(parts)});out body;'
        query(q, name)
    # outliers en una sola consulta
    parts = []
    for jp, (la, lo) in OUTLIERS.items():
        parts.append(f'node["railway"="station"](around:3000,{la},{lo});')
    q = f'[out:json][timeout:120];({"".join(parts)});out body;'
    query(q, "outliers")


if __name__ == "__main__":
    import urllib.parse
    main()
