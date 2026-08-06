# -*- coding: utf-8 -*-
"""migrate_yaml.py — crea/actualiza el viaje.yaml LOCAL de viajes-2 a partir de
../viajes-icons/viaje.yaml, aplicando la limpieza de datos aprobada:

  1. títulos sin ** — el título entero va en bold por diseño, los asteriscos
     eran ruido del pipeline viejo (y en el app familiar producían basura)
  2. pasos de transporte sin emoji inicial — el icono se deriva de `mode` al
     renderizar (build_itinerario.MODE_ICON), no vive en el texto

Los @[refs](clave) y el markdown de las notas se conservan tal cual.
Rerun cada vez que cambie viajes-icons/viaje.yaml.
"""
import os
import sys

import yaml

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
SD = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.abspath(os.path.join(SD, "..", "viajes-icons", "viaje.yaml"))
DST = os.path.join(SD, "viaje.yaml")

# emojis de transporte que pueden encabezar un título de transit (con o sin
# selector de variación); cualquier otro emoji (🏪 👋 👘 …) se queda
TRANSPORT = ("🚇", "🚶", "🚝", "🚌", "🧳", "✈️", "✈", "⛴️", "⛴", "🛳️", "🛳", "🚋", "🚊")

stats = {"ast": 0, "emoji": 0}
modes = set()


def strip_asterisks(node):
    if "title" in node and "*" in str(node["title"]):
        node["title"] = str(node["title"]).replace("*", "")
        stats["ast"] += 1


def strip_transport_emoji(node):
    t = str(node.get("title") or "")
    for e in TRANSPORT:
        if t.startswith(e):
            node["title"] = t[len(e):].lstrip()
            stats["emoji"] += 1
            return


def walk_steps(steps):
    for s in steps:
        if not isinstance(s, dict):
            continue
        strip_asterisks(s)
        if "transit" in s or s.get("mode"):
            strip_transport_emoji(s)
        if s.get("mode"):
            modes.add(s["mode"])
        for o in s.get("options") or []:
            if isinstance(o, dict):
                strip_asterisks(o)
                if "steps" in o:            # plan anidado
                    walk_steps(o["steps"])


Y = yaml.safe_load(open(SRC, encoding="utf-8"))
for tr in (Y.get("transits") or {}).values():
    if tr.get("mode"):
        modes.add(tr["mode"])
for day in Y.get("days", []):
    walk_steps(day.get("steps", []))

yaml.dump(Y, open(DST, "w", encoding="utf-8"), allow_unicode=True,
          sort_keys=False, default_flow_style=None, width=100000)
print(f"viaje.yaml local ← {SRC}")
print(f"  títulos sin asteriscos: {stats['ast']} · emojis de transporte quitados: {stats['emoji']}")
print(f"  modes presentes: {sorted(modes)}")
