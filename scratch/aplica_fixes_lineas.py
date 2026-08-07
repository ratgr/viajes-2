# -*- coding: utf-8 -*-
"""aplica_fixes_lineas.py — aplica los fixes de scratch/reporte_lineas.md al
viaje.yaml por empalme de texto (validando el YAML tras cada edición).
Correr SOLO cuando nadie más esté editando el YAML."""
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
texto = open(PATH, encoding="utf-8").read()
ok = fallas = 0


def valida(t):
    yaml.safe_load(t)
    return t


def bloque(t, clave):
    """[inicio, fin) del bloque de una entrada de 2º nivel ('  clave:')."""
    m = re.search(rf"^  {re.escape(clave)}:", t, re.M)
    if not m:
        return None
    m2 = re.search(r"^  \S|^\S", t[m.end():], re.M)
    return (m.start(), m.end() + (m2.start() if m2 else len(t) - m.end()))


def en_bloque(clave, viejo, nuevo, veces=1):
    global texto, ok, fallas
    span = bloque(texto, clave)
    if not span:
        print(f"  !! {clave}: bloque no encontrado")
        fallas += 1
        return
    seg = texto[span[0]:span[1]]
    if seg.count(viejo) != veces:
        print(f"  !! {clave}: '{viejo[:40]}' aparece {seg.count(viejo)} veces (esperaba {veces})")
        fallas += 1
        return
    cand = texto[:span[0]] + seg.replace(viejo, nuevo) + texto[span[1]:]
    try:
        texto = valida(cand)
        ok += 1
        print(f"  ok {clave}: {viejo[:34]} → {nuevo[:34]}")
    except yaml.YAMLError as e:
        print(f"  !! {clave}: edición rompía YAML ({e}); saltada")
        fallas += 1


# 1) d16-1 Shōnan-Shinjuku: 5 vértices basura (vértice i == estación i)
for viejo, nuevo in [
    ("35.619905,139.703567", "35.576624,139.660717"),   # Musashi-Kosugi
    ("35.628527,139.742672", "35.466207,139.623195"),   # Yokohama
    ("35.695362,139.841711", "35.430361,139.556762"),   # Higashi-Totsuka
    ("35.716965,139.694456", "35.401106,139.535079"),   # Totsuka
    ("35.689501,139.848863", "35.354309,139.531432"),   # Ōfuna
]:
    en_bloque("d16-1", viejo, nuevo)

# 2) d15-2 Keiyo: Maihama
en_bloque("d15-2", "35.616744,139.776085", "35.635631,139.882719")

# 3) d16-4 Yurikamome: Ariake
en_bloque("d16-4", "35.641511,139.796789", "35.634556,139.793256")

# 4) d5-4: stops era copia de coords → posiciones REALES de las 10 estaciones
STOPS_D54 = ("34.397667,132.475379 34.402083,132.457678 34.409960,132.450602 "
             "34.398048,132.427982 34.375716,132.392096 34.366927,132.368100 "
             "34.358027,132.335676 34.348964,132.324075 34.323073,132.314302 "
             "34.312009,132.302951")
span = bloque(texto, "d5-4")
if span:
    seg = texto[span[0]:span[1]]
    seg2, n = re.subn(r"^    stops: .*$", f"    stops: {STOPS_D54}", seg, count=1, flags=re.M)
    if n == 1:
        try:
            texto = valida(texto[:span[0]] + seg2 + texto[span[1]:])
            ok += 1
            print("  ok d5-4: stops reconstruidos (10 estaciones)")
        except yaml.YAMLError:
            fallas += 1
    else:
        print("  !! d5-4: línea stops no encontrada")
        fallas += 1

# 5) d5-7: el regreso también para en Shin-Hakushima (estación + vértice)
en_bloque("d5-7", "34.409960,132.450602 34.397667,132.475379",
          "34.409960,132.450602 34.402083,132.457678 34.397667,132.475379")
en_bloque("d5-7", "    - ['', 横川, Yokogawa]\n",
          "    - ['', 横川, Yokogawa]\n    - ['', 新白島, Shin-Hakushima]\n")

# 6) d6-4 / d6-5: Ajikawaguchi
for k in ("d6-4", "d6-5"):
    en_bloque(k, "34.669932,135.441938", "34.673624,135.444024")

# 7) d8-6 HARUKA: andén Umekita (menor)
en_bloque("d8-6", "34.705027,135.498427", "34.704000,135.493900")

# 8) buses declarados como tren
for k in ("d9-4", "d10-6", "d11-4", "d11-5", "d18-1"):
    en_bloque(k, "    mode: train\n", "    mode: bus\n")

# 9) d16-5 es la Chūō-Sōbu LOCAL (JB amarilla), no la rápida (JC naranja)
en_bloque("d16-5", "    line: JR Chūō Line (rápida)\n", "    line: JR Chūō-Sōbu local\n")
en_bloque("d16-5", "chip: JC", "chip: JB")
en_bloque("d16-5", "color: '#f15a22'", "color: '#ffd400'")

# 10) d10-6: lo opera Kyoto Bus PRIVADO (el pase municipal no aplica)
en_bloque("d10-6", "    line: Bus urbano de Kioto\n",
          "    line: Kyoto Bus 62/72/92/94 (privado — pase municipal NO aplica)\n")

# 11) nabezo-shinjuku: el pin caía en Akasaka (~3 km); sucursal Shinjuku 3-chōme
en_bloque("nabezo-shinjuku", "35.668070,139.740806", "35.690650,139.704950", veces=2)

# 12) torikizoku en el día 16 (Tokio) usaba el pin de Osaka → sucursal
#     Kotakibashi-dōri (pin oficial, tienda 734), a 3 min del hotel
i = texto.index("\ntransits:")
lugar = ("\n  torikizoku-shinjuku: {name: Torikizoku (Shinjuku Kotakibashi), gps: '35.694463,139.698646', "
         "maps: 'https://www.google.com/maps/search/?api=1&query=35.694463,139.698646', "
         "description: 'El mismo yakitori de cadena a ¥370 el pincho, sucursal Kotakibashi-dōri — a 3 min del hotel.', "
         "info: 'Recomendado por: Clásico de todas las guías', image: fachadas/torikizoku_os.jpg, "
         "hours: '17:00–01:00 aprox. (cadena)', hours_source: 'https://en.map.torikizoku.co.jp/detail/734/'}")
if "torikizoku-shinjuku" not in texto:
    try:
        texto = valida(texto[:i] + lugar + texto[i:])
        ok += 1
        print("  ok place torikizoku-shinjuku insertado")
    except yaml.YAMLError:
        fallas += 1
# el bloque del día 16 es la SEGUNDA aparición del patrón de la opción
viejo_opt = ("      - title: '@[Torikizoku](torikizoku)'\n")
if texto.count(viejo_opt) == 2:
    j = texto.rindex(viejo_opt)
    seg = texto[j:j + 400]
    seg = seg.replace("'@[Torikizoku](torikizoku)'", "'@[Torikizoku](torikizoku-shinjuku)'", 1)
    seg = seg.replace("{transit: to-torikizoku, title: To Torikizoku}",
                      "{transit: to-torikizoku-shinjuku, title: To Torikizoku}", 1)
    seg = seg.replace("{location: torikizoku}", "{location: torikizoku-shinjuku}", 1)
    seg = seg.replace("{transit: from-torikizoku, title: From Torikizoku}",
                      "{transit: from-torikizoku-shinjuku, title: From Torikizoku}", 1)
    try:
        texto = valida(texto[:j] + seg + texto[j + 400:])
        ok += 1
        print("  ok d16: opción Torikizoku → sucursal Shinjuku")
    except yaml.YAMLError as e:
        print(f"  !! d16 torikizoku: {e}")
        fallas += 1
else:
    print(f"  !! patrón de opción torikizoku aparece {texto.count(viejo_opt)} veces (esperaba 2)")
    fallas += 1

valida(texto)
open(PATH, "w", encoding="utf-8", newline="").write(texto)
print(f"\naplicados: {ok} · fallas: {fallas} · YAML final válido ✓")
