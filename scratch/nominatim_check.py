# -*- coding: utf-8 -*-
"""nominatim_check.py — cross-check: geocodifica el name de los places usados como
location en days (Nominatim, 1 req/1.2 s) y compara contra el gps del YAML.
Solo señal auxiliar: nombres genéricos no geocodifican. Salida: scratch/nominatim_results.jsonl
"""
import json, math, sys, time, urllib.parse, urllib.request

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import yaml

YAML_PATH = r"d:\dev\viajes\japon\viajes-2\src\2026-Japon\viaje.yaml"
OUT = r"d:\dev\viajes\japon\viajes-2\scratch\nominatim_results.jsonl"
UA = "viajes-2-qa/1.0 (ratgricardo@gmail.com)"
R = 6371000.0


def hav(a, b):
    la1, lo1, la2, lo2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 2 * R * math.asin(math.sqrt(h))


def main():
    d = yaml.safe_load(open(YAML_PATH, encoding="utf-8"))
    places = d["places"]
    day_locs = []
    for day in d["days"]:
        for st in day.get("steps", []):
            loc = st.get("location")
            if loc and loc not in day_locs:
                day_locs.append(loc)
    done = set()
    try:
        for line in open(OUT, encoding="utf-8"):
            done.add(json.loads(line)["key"])
    except FileNotFoundError:
        pass
    for key in day_locs:
        p = places.get(key)
        if not p or not p.get("gps") or key in done:
            continue
        gps = tuple(map(float, p["gps"].split(",")))
        name = p["name"]
        # limpia paréntesis para geocodificar mejor
        q = name.split("(")[0].strip()
        url = ("https://nominatim.openstreetmap.org/search?format=json&limit=1&countrycodes=jp&q="
               + urllib.parse.quote(q))
        rec = {"key": key, "name": name, "gps": p["gps"]}
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            res = json.load(urllib.request.urlopen(req, timeout=30))
            if res:
                hit = res[0]
                pos = (float(hit["lat"]), float(hit["lon"]))
                rec["found"] = hit.get("display_name", "")[:120]
                rec["osm_pos"] = [round(pos[0], 6), round(pos[1], 6)]
                rec["dist_m"] = round(hav(gps, pos))
            else:
                rec["found"] = None
        except Exception as e:
            rec["error"] = str(e)[:120]
        with open(OUT, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        print(key, rec.get("dist_m"), rec.get("found"), flush=True)
        time.sleep(1.3)
    print("DONE", flush=True)


if __name__ == "__main__":
    main()
