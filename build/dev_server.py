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
    POST /api/rebuild {trip}               reconstruye pages/<trip>/

La fila dN-rMM del HTML ES el paso M del día N del YAML (proyección 1:1),
así que la identidad de la edición sale del id de la fila.

Uso: python build/dev_server.py [puerto]      (default 8791)
"""
import json
import os
import subprocess
import sys
import threading
import urllib.parse
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

import yaml

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import ROOT

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SERVE_DIR = os.path.dirname(ROOT)
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8791
DUMP = dict(allow_unicode=True, sort_keys=False, default_flow_style=None, width=100000)
CATALOGS = ("places", "transits", "lines")


def yaml_path(trip):
    p = os.path.abspath(os.path.join(ROOT, "src", trip, "viaje.yaml"))
    if not p.startswith(os.path.join(ROOT, "src")):
        raise ValueError(f"viaje inválido: {trip}")
    return p


# el servidor es multihilo: nunca leer el YAML mientras otro hilo lo escribe
_YAML_LOCK = threading.Lock()


def load(trip):
    with _YAML_LOCK:
        return yaml.safe_load(open(yaml_path(trip), encoding="utf-8"))


def save(trip, data):
    """escritura atómica: tmp + replace, bajo el lock."""
    path = yaml_path(trip)
    tmp = path + ".tmp"
    with _YAML_LOCK:
        with open(tmp, "w", encoding="utf-8") as f:
            yaml.dump(data, f, **DUMP)
        os.replace(tmp, path)


def rebuild(trip):
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
                step = load(q["trip"])["days"][int(q["day"]) - 1]["steps"][int(q["step"]) - 1]
                self._json(200, {"ok": True,
                                 "yaml": yaml.dump(step, allow_unicode=True, sort_keys=False,
                                                   default_flow_style=False, width=100000)})
            elif u.path == "/api/entity":
                Y = load(q["trip"])
                key = q["key"]
                kinds = [q["kind"]] if q.get("kind") in CATALOGS else CATALOGS
                for kind in kinds:
                    if key in (Y.get(kind) or {}):
                        # width enorme: coords debe quedar en UNA línea (el editor
                        # de geometría del mapa la reescribe línea por línea)
                        self._json(200, {"ok": True, "kind": kind,
                                         "yaml": yaml.dump(Y[kind][key], allow_unicode=True,
                                                           sort_keys=False, default_flow_style=False,
                                                           width=100000)})
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
                trip = req["trip"]
                Y = load(trip)
                Y["days"][int(req["day"]) - 1]["steps"][int(req["step"]) - 1] = step
                save(trip, Y)
                self._json(200, {"ok": True})
            elif u.path == "/api/entity":
                obj = yaml.safe_load(req["yaml"])
                if not isinstance(obj, dict):
                    return self._json(400, {"error": "el YAML debe ser un mapeo (una entidad)"})
                if req.get("kind") not in CATALOGS:
                    return self._json(400, {"error": f"kind debe ser uno de {CATALOGS}"})
                trip = req["trip"]
                Y = load(trip)
                Y.setdefault(req["kind"], {})[req["key"]] = obj
                save(trip, Y)
                self._json(200, {"ok": True})
            elif u.path == "/api/step-insert":
                # inserta {title: (nuevo paso)} antes/después de la fila dada;
                # responde el número (1-based) del paso nuevo
                trip = req["trip"]
                Y = load(trip)
                steps = Y["days"][int(req["day"]) - 1]["steps"]
                i = int(req["step"]) - 1
                if not 0 <= i < len(steps):
                    return self._json(400, {"error": "paso fuera de rango"})
                pos = i if req.get("where") == "before" else i + 1
                steps.insert(pos, {"title": "(nuevo paso)"})
                save(trip, Y)
                self._json(200, {"ok": True, "step": pos + 1})
            elif u.path == "/api/step-move":
                # mueve la fila una posición (dir=-1 sube, dir=1 baja)
                trip = req["trip"]
                Y = load(trip)
                steps = Y["days"][int(req["day"]) - 1]["steps"]
                i = int(req["step"]) - 1
                j = i + int(req.get("dir", 0))
                if not (0 <= i < len(steps) and 0 <= j < len(steps) and i != j):
                    return self._json(400, {"error": "movimiento fuera de rango"})
                steps.insert(j, steps.pop(i))
                save(trip, Y)
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
