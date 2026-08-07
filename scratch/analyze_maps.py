# -*- coding: utf-8 -*-
"""analyze_maps.py — clasifica maps_results.jsonl: ok/neutral/error, localidades, anomalías."""
import json, re, sys, unicodedata
from collections import Counter

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
F = sys.argv[1]

COORD = re.compile(r"^\s*\d+°\d+'[\d.]+\"[NS]")

rows = [json.loads(l) for l in open(F, encoding="utf-8")]
print("total:", len(rows))
cnt = Counter()
localities = Counter()
anomalies = []
for r in rows:
    h1 = (r.get("h1") or "").strip()
    panel = r.get("panel") or ""
    st = r.get("status")
    if st == "nav_error" or not h1:
        cnt["error_o_sin_h1"] += 1
        anomalies.append((r["key"], st, h1, panel[:120]))
        continue
    if COORD.match(h1):
        cnt["neutral_pin_coordenadas"] += 1
        m = re.search(r"[A-Z0-9]{4,8}\+[A-Z0-9]{2,4}\s+([^,]+(?:, [^,]+)?), Japan", panel)
        if m:
            localities[m.group(1).strip()] += 1
        else:
            localities["(sin localidad legible)"] += 1
            anomalies.append((r["key"], "sin_localidad", h1, panel[:120]))
    else:
        cnt["h1_con_nombre"] += 1
        anomalies.append((r["key"], "nombre_resuelto", h1, r.get("name")))

print(cnt)
print("\nLocalidades:")
for loc, c in localities.most_common():
    print(f"  {c:4d}  {loc}")
print("\nAnomalías:")
for a in anomalies:
    print(" ", a)
