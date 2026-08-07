# -*- coding: utf-8 -*-
"""zonas_poi.py — POIs que son CALLE o BARRIO reciben `zone:` (polígono).

Para cada POI listado: baja de Overpass las ways con ese nombre alrededor de
su gps, recorta los nodos a un radio máximo (≤ ~15 cuadras), ajusta un
rectángulo orientado por PCA con margen, y empalma `, zone: '...'` en la
línea flow del place (validando el YAML tras cada edición). Idempotente:
si el place ya tiene zone: se reescribe.
"""
import json
import math
import os
import re
import sys
import time
import urllib.parse
import urllib.request

import yaml

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "build"))
from common import resolve_trip, trip_paths

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
TRIP = resolve_trip(sys.argv)
SRC_DIR, _p, _c = trip_paths(TRIP)
PATH = os.path.join(SRC_DIR, "viaje.yaml")
UA = {"User-Agent": "viajes-2-zonas/1.0 (ratgricardo@gmail.com)"}

# clave → (regex de nombre OSM, radio de búsqueda m, recorte de nodos m, margen m)
ZONAS = {
    "golden-gai":        ("ゴールデン街", 250, 120, 18),
    "janjan-yokocho":    ("ジャンジャン横丁|南陽通商店街", 300, 200, 15),
    "yakitori-de-ameyoko": ("アメ横|アメヤ横丁", 350, 280, 18),
    "hondori-arcade":    ("本通", 300, 350, 15),
    "amerikamura":       ("アメリカ村|三角公園", 250, 220, 60),
    "shinsaibashi-suji": ("心斎橋筋", 300, 350, 12),
    "denden-town":       ("日本橋筋|でんでんタウン", 350, 320, 25),
    "machiya-dori-miyajima": ("町家通り", 300, 300, 12),
    "ishibei-koji":      ("石塀小路", 200, 130, 12),
    "kamishichiken":     ("上七軒", 300, 250, 14),
    "nishiki-ichiba":    ("錦市場|錦小路通", 300, 320, 12),
    "kappabashi-dogugai": ("かっぱ橋道具街|合羽橋", 350, 350, 15),
    "hoppy-dori":        ("ホッピー通り|公園本通り", 250, 180, 14),
    "yanaka-ginza":      ("谷中ぎんざ|谷中銀座", 300, 200, 14),
    "cat-street":        ("キャットストリート|旧渋谷川遊歩道路", 350, 300, 12),
    "komachi-dori":      ("小町通り", 300, 320, 12),
    "spain-zaka":        ("スペイン坂", 200, 120, 12),
    "gion-shirakawa-tatsumibashi": ("白川南通|白川筋", 250, 180, 14),
    "tsutenkaku-hondori": ("通天閣本通", 250, 200, 12),
    "shinsekai-ichiba": ("新世界市場", 200, 130, 12),
}
# sin way OSM confiable: rectángulos a mano (centro, largo m, ancho m, rumbo°)
MANUAL = {
    "shibuya-yokocho": (35.66052, 139.70207, 220, 30, 170),
    "denden-town": (34.6598, 135.50605, 600, 70, 184),
}

Y = yaml.safe_load(open(PATH, encoding="utf-8"))


def overpass(q):
    req = urllib.request.Request("https://overpass-api.de/api/interpreter",
                                 data=urllib.parse.urlencode({"data": q}).encode(), headers=UA)
    return json.load(urllib.request.urlopen(req, timeout=90))


def metros(centro, p):
    dy = (p[0] - centro[0]) * 111000.0
    dx = (p[1] - centro[1]) * 111000.0 * math.cos(math.radians(centro[0]))
    return dx, dy


def latlon(centro, dx, dy):
    return (round(centro[0] + dy / 111000.0, 6),
            round(centro[1] + dx / (111000.0 * math.cos(math.radians(centro[0]))), 6))


def rect_pca(centro, puntos, margen):
    """rectángulo orientado (4 esquinas lat,lon) que cubre los puntos."""
    xy = [metros(centro, p) for p in puntos]
    n = len(xy)
    mx = sum(x for x, _ in xy) / n
    my = sum(y for _, y in xy) / n
    sxx = sum((x - mx) ** 2 for x, _ in xy) / n
    syy = sum((y - my) ** 2 for _, y in xy) / n
    sxy = sum((x - mx) * (y - my) for x, y in xy) / n
    ang = 0.5 * math.atan2(2 * sxy, sxx - syy)
    ca, sa = math.cos(ang), math.sin(ang)
    us = [((x - mx) * ca + (y - my) * sa, -(x - mx) * sa + (y - my) * ca) for x, y in xy]
    u0, u1 = min(u for u, _ in us) - margen, max(u for u, _ in us) + margen
    v0, v1 = min(v for _, v in us) - margen, max(v for _, v in us) + margen
    esquinas = []
    for u, v in [(u0, v0), (u1, v0), (u1, v1), (u0, v1)]:
        dx = mx + u * ca - v * sa
        dy = my + u * sa + v * ca
        esquinas.append(latlon(centro, dx, dy))
    return esquinas


def rect_manual(lat, lon, largo, ancho, rumbo):
    ang = math.radians(90 - rumbo)  # rumbo geográfico → ángulo matemático
    ca, sa = math.cos(ang), math.sin(ang)
    esquinas = []
    for u, v in [(-largo / 2, -ancho / 2), (largo / 2, -ancho / 2),
                 (largo / 2, ancho / 2), (-largo / 2, ancho / 2)]:
        esquinas.append(latlon((lat, lon), u * ca - v * sa, u * sa + v * ca))
    return esquinas


def probar(texto):
    yaml.safe_load(texto)
    return texto


def poner_zone(texto, clave, zona):
    val = " ".join(f"{a},{b}" for a, b in zona)
    pat = re.compile(rf"^(  {re.escape(clave)}: \{{.*?)(, zone: '[^']*')?(\}})$", re.M)
    m = pat.search(texto)
    if not m:
        print(f"  !! no encontré la línea flow de {clave}")
        return texto
    nuevo = pat.sub(lambda mm: mm.group(1) + f", zone: '{val}'" + mm.group(3), texto, count=1)
    try:
        return probar(nuevo)
    except yaml.YAMLError as e:
        print(f"  !! {clave}: la edición rompía el YAML ({e}); saltada")
        return texto


texto = open(PATH, encoding="utf-8").read()
hechas = 0
for clave, (nombre, radio, recorte, margen) in ZONAS.items():
    pl = Y["places"].get(clave)
    if not pl or not pl.get("gps"):
        print(f"{clave}: sin place/gps — saltado")
        continue
    if re.search(rf"^  {re.escape(clave)}: \{{.*, zone: '", texto, re.M):
        print(f"{clave}: ya tiene zone — saltado")
        continue
    la, lo = (float(x) for x in str(pl["gps"]).split(","))
    q = (f'[out:json][timeout:60];way["name"~"{nombre}"](around:{radio},{la},{lo});'
         "(._;>;);out skel qt;")
    try:
        d = overpass(q)
    except Exception as e:
        print(f"{clave}: overpass falló ({e}) — saltado")
        continue
    nodos = [(e["lat"], e["lon"]) for e in d.get("elements", []) if e.get("type") == "node"]
    nodos = [p for p in nodos if math.hypot(*metros((la, lo), p)) <= recorte]
    if len(nodos) < 2:
        print(f"{clave}: {len(nodos)} nodos OSM — saltado (revisar a mano)")
        continue
    zona = rect_pca((la, lo), nodos, margen)
    antes = texto
    texto = poner_zone(texto, clave, zona)
    if texto is not antes:
        span = max(math.hypot(*metros((la, lo), p)) for p in zona)
        print(f"{clave}: zona de {len(nodos)} nodos · radio {span:.0f} m")
        hechas += 1
    time.sleep(10)

for clave, (la, lo, largo, ancho, rumbo) in MANUAL.items():
    zona = rect_manual(la, lo, largo, ancho, rumbo)
    antes = texto
    texto = poner_zone(texto, clave, zona)
    if texto is not antes:
        print(f"{clave}: rectángulo manual {largo}×{ancho} m")
        hechas += 1

probar(texto)
open(PATH, "w", encoding="utf-8", newline="").write(texto)
print(f"zonas escritas: {hechas} · YAML válido ✓")
