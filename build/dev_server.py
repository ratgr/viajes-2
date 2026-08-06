# -*- coding: utf-8 -*-
"""dev_server.py — servidor local de desarrollo (solo 127.0.0.1).

Sirve el directorio PADRE del repo (para ver pages/ y el app viejo) con
Cache-Control: no-store, y expone la API del modo dev del mapa — editar
pasos del YAML directamente desde la página:

    GET  /api/step?trip=X&day=N&step=M     YAML del paso (para el editor)
    POST /api/step {trip, day, step, yaml} valida, escribe src/<trip>/viaje.yaml
                                           y reconstruye pages/<trip>/

La fila dN-rMM del HTML ES el paso M del día N del YAML (proyección 1:1),
así que la identidad de la edición sale del id de la fila.

Uso: python build/dev_server.py [puerto]      (default 8791)
"""
import json
import os
import subprocess
import sys
import urllib.parse
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

import yaml

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import ROOT

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SERVE_DIR = os.path.dirname(ROOT)
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8791
DUMP = dict(allow_unicode=True, sort_keys=False, default_flow_style=None, width=100000)


def yaml_path(trip):
    p = os.path.abspath(os.path.join(ROOT, "src", trip, "viaje.yaml"))
    if not p.startswith(os.path.join(ROOT, "src")):
        raise ValueError(f"viaje inválido: {trip}")
    return p


def load(trip):
    return yaml.safe_load(open(yaml_path(trip), encoding="utf-8"))


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
                                                   default_flow_style=False)})
            else:
                self._json(404, {"error": "endpoint desconocido"})
        except Exception as e:
            self._json(400, {"error": str(e)})

    def do_POST(self):
        u = urllib.parse.urlparse(self.path)
        try:
            if u.path != "/api/step":
                return self._json(404, {"error": "endpoint desconocido"})
            n = int(self.headers.get("Content-Length", 0))
            req = json.loads(self.rfile.read(n).decode("utf-8"))
            step = yaml.safe_load(req["yaml"])
            if not isinstance(step, dict):
                return self._json(400, {"error": "el YAML debe ser un mapeo (un paso)"})
            trip = req["trip"]
            Y = load(trip)
            Y["days"][int(req["day"]) - 1]["steps"][int(req["step"]) - 1] = step
            yaml.dump(Y, open(yaml_path(trip), "w", encoding="utf-8"), **DUMP)
            self._json(200, {"ok": True, "build": rebuild(trip)})
        except Exception as e:
            self._json(400, {"error": str(e)})


if __name__ == "__main__":
    os.chdir(SERVE_DIR)
    print(f"dev server → http://127.0.0.1:{PORT}/viajes-2/pages/  (API /api/step)")
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
