# -*- coding: utf-8 -*-
"""dev_server.py — servidor local de desarrollo (solo 127.0.0.1).

Sirve el directorio PADRE del repo (para ver pages/ y el app viejo) con
Cache-Control: no-store, y expone la API del modo dev del mapa — editar
pasos del YAML directamente desde la página:

    GET  /api/step?trip=X&day=N&step=M     YAML del paso (para el editor)
    POST /api/step {trip, day, step, yaml} valida y escribe src/<trip>/viaje.yaml
                                           (SIN rebuild: se editan varios y luego…)
    GET  /api/entity?trip=X&key=K[&kind=]  YAML de la entidad referenciada
                                           (busca en places → transits → lines)
    POST /api/entity {trip,kind,key,yaml}  escribe la entidad en su catálogo
    POST /api/step-insert {trip,day,step,where}  inserta un paso nuevo
                                           antes/después de la fila dada
    POST /api/step-move {trip,day,step,dir}      mueve el paso una posición
                                           (dir=-1 sube, dir=1 baja)
    POST /api/rebuild {trip}               reconstruye pages/<trip>/

La fila dN-rMM del HTML ES el paso M del día N del YAML (proyección 1:1),
así que la identidad de la edición sale del id de la fila.

Uso: python build/dev_server.py [puerto]      (default 8791)
"""
import contextlib
import json
import os
import subprocess
import sys
import threading
import urllib.parse
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

import yaml

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import ROOT, dump_yaml

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SERVE_DIR = os.path.dirname(ROOT)
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8791
CATALOGS = ("places", "transits", "lines")


def yaml_path(trip):
    p = os.path.abspath(os.path.join(ROOT, "src", trip, "viaje.yaml"))
    # separador final: sin él, '../srcotra' pasaba el filtro de prefijo
    if not p.startswith(os.path.join(ROOT, "src", "")):
        raise ValueError(f"viaje inválido: {trip}")
    return p


# el servidor es multihilo: el candado debe cubrir CADA secuencia completa
# leer-modificar-guardar (no solo la lectura y la escritura por separado —
# dos POST simultáneos se pisaban la edición en silencio). RLock: load/save
# también se usan solos.
_YAML_LOCK = threading.RLock()


def load(trip):
    with _YAML_LOCK:
        return yaml.safe_load(open(yaml_path(trip), encoding="utf-8"))


def save(trip, data):
    """escritura atómica: tmp + replace, bajo el lock."""
    path = yaml_path(trip)
    tmp = path + ".tmp"
    with _YAML_LOCK:
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(dump_yaml(data))
        os.replace(tmp, path)


@contextlib.contextmanager
def edit(trip):
    """leer-modificar-guardar ATÓMICO: candado sostenido todo el trayecto."""
    with _YAML_LOCK:
        Y = load(trip)
        yield Y
        save(trip, Y)


def steps_of(Y, day):
    """lista de pasos del día 1-based — con validación de rango (el indexado
    negativo de Python convertía day=0 en 'el último día' sin error)."""
    d = int(day)
    if not 1 <= d <= len(Y.get("days", [])):
        raise ValueError(f"día fuera de rango: {day}")
    return Y["days"][d - 1]["steps"]


def step_at(Y, day, step):
    steps = steps_of(Y, day)
    s = int(step)
    if not 1 <= s <= len(steps):
        raise ValueError(f"paso fuera de rango: {step}")
    return steps, s - 1


def rebuild(trip):
    # bajo el candado: un Guardar aterrizando entre los dos scripts producía
    # itinerario y mapa construidos de VERSIONES DISTINTAS del YAML
    with _YAML_LOCK:
        outs = []
        for script in ("build_itinerario.py", "build_mapa.py"):
            r = subprocess.run([sys.executable, os.path.join(ROOT, "build", script), trip],
                               capture_output=True, text=True, encoding="utf-8")
            outs.append(r.stdout.strip() or r.stderr.strip())
        return "\n".join(outs)


class Handler(SimpleHTTPRequestHandler):
    extensions_map = {**SimpleHTTPRequestHandler.extensions_map,
                      ".html": "text/html; charset=utf-8",
                      ".css": "text/css; charset=utf-8",
                      ".js": "text/javascript; charset=utf-8"}

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def _json(self, code, obj):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if not self.path.startswith("/api/"):
            return super().do_GET()
        u = urllib.parse.urlparse(self.path)
        q = dict(urllib.parse.parse_qsl(u.query))
        try:
            if u.path == "/api/step":
                steps, i = step_at(load(q["trip"]), q["day"], q["step"])
                self._json(200, {"ok": True, "yaml": dump_yaml(steps[i], flow=False)})
            elif u.path == "/api/entity":
                Y = load(q["trip"])
                key = q["key"]
                kinds = [q["kind"]] if q.get("kind") in CATALOGS else CATALOGS
                for kind in kinds:
                    if key in (Y.get(kind) or {}):
                        # width enorme (en DUMP): coords debe quedar en UNA línea (el
                        # editor de geometría del mapa la reescribe línea por línea)
                        self._json(200, {"ok": True, "kind": kind,
                                         "yaml": dump_yaml(Y[kind][key], flow=False)})
                        return
                self._json(404, {"error": f"'{key}' no está en {'/'.join(kinds)}"})
            else:
                self._json(404, {"error": "endpoint desconocido"})
        except Exception as e:
            self._json(400, {"error": str(e)})

    def do_POST(self):
        u = urllib.parse.urlparse(self.path)
        try:
            n = int(self.headers.get("Content-Length", 0))
            req = json.loads(self.rfile.read(n).decode("utf-8"))
            if u.path == "/api/step":
                step = yaml.safe_load(req["yaml"])
                if not isinstance(step, dict):
                    return self._json(400, {"error": "el YAML debe ser un mapeo (un paso)"})
                with edit(req["trip"]) as Y:
                    steps, i = step_at(Y, req["day"], req["step"])
                    steps[i] = step
                self._json(200, {"ok": True})
            elif u.path == "/api/entity":
                obj = yaml.safe_load(req["yaml"])
                if not isinstance(obj, dict):
                    return self._json(400, {"error": "el YAML debe ser un mapeo (una entidad)"})
                if req.get("kind") not in CATALOGS:
                    return self._json(400, {"error": f"kind debe ser uno de {CATALOGS}"})
                with edit(req["trip"]) as Y:
                    Y.setdefault(req["kind"], {})[req["key"]] = obj
                self._json(200, {"ok": True})
            elif u.path == "/api/step-insert":
                # inserta {title: (nuevo paso)} antes/después de la fila dada;
                # responde el número (1-based) del paso nuevo
                with edit(req["trip"]) as Y:
                    steps, i = step_at(Y, req["day"], req["step"])
                    pos = i if req.get("where") == "before" else i + 1
                    steps.insert(pos, {"title": "(nuevo paso)"})
                self._json(200, {"ok": True, "step": pos + 1})
            elif u.path == "/api/step-move":
                # mueve la fila una posición (dir=-1 sube, dir=1 baja)
                with edit(req["trip"]) as Y:
                    steps, i = step_at(Y, req["day"], req["step"])
                    j = i + int(req.get("dir", 0))
                    if not (0 <= j < len(steps) and i != j):
                        raise ValueError("movimiento fuera de rango")
                    steps.insert(j, steps.pop(i))
                self._json(200, {"ok": True, "step": j + 1})
            elif u.path == "/api/rebuild":
                self._json(200, {"ok": True, "build": rebuild(req["trip"])})
            else:
                self._json(404, {"error": "endpoint desconocido"})
        except Exception as e:
            self._json(400, {"error": str(e)})


if __name__ == "__main__":
    os.chdir(SERVE_DIR)
    print(f"dev server → http://127.0.0.1:{PORT}/viajes-2/pages/  (API /api/step)")
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
