# -*- coding: utf-8 -*-
"""build_mapa.py — src/<viaje>/viaje.yaml → pages/<viaje>/mapa.html.

La barra lateral del mapa ES el itinerario: mismos días/filas/modales que
genera render.py (proyección 1:1 del YAML, verificada). El cromo del mapa
(casillas, colapso por día, mapa base Leaflet) lo agregan mapa.css/mapa.js
en el navegador — el HTML servido no cambia.

Por ahora: barra lateral + mapa base. Las capas (marcadores/rutas) vienen después.
"""
import json
import os
import sys

import yaml

import render
from common import resolve_trip

sys.stdout.reconfigure(encoding="utf-8", errors="replace")


# ------------------------------------------------- anclas precalculadas
# Para cada paso con `transit:` SIN geometría (el conector automático del
# mapa) se precalcula aquí el par {prev, next}: el punto del vecino con
# geometría más cercano DENTRO de su misma rama y su mismo día — la misma
# regla que neighborAnchors/sameBranch en mapa.js, pero en build (mapa.js
# los lee de GEO.anchors por id de fila y solo rastrea en vivo si faltan).

def _step_anchor_pt(s, end):
    """punto de anclaje de un paso: lugar → su gps; transporte → su último/
    primer vértice (según sea el vecino previo o el siguiente) — espejo de
    anchorPoint en mapa.js."""
    key = s.get("location") or s.get("transit")
    p = render._place_pt(key)
    if p:
        return [p[0], p[1]]
    pts = render._transit_pts(key)
    if pts:
        q = pts[-1] if end else pts[0]
        return [q[0], q[1]]
    return None


def _same_branch(path_el, path_cand):
    """espejo de sameBranch (mapa.js): el candidato es vecino válido si el
    paso base cuelga de cada conjunto de options ancestro del candidato por
    el MISMO contenedor (opción/plan); candidato fuera de todo conjunto
    siempre es válido. Las rutas son tuplas (conjunto, contenedor) de afuera
    hacia adentro."""
    for k, (set_id, cont_id) in enumerate(path_cand):
        if k >= len(path_el) or path_el[k] != (set_id, cont_id):
            return False       # fuera del conjunto, o en OTRA opción del mismo
    return True


def _collect_rows(day, num):
    """pasos con location/transit del día, aplanados en orden del documento:
    (id extendido, paso, ruta-de-rama) — la MISMA lista y los MISMOS ids
    dN-rMM[-gG[-oO]-sS] que emiten render_day/render_options/render_option."""
    out = []

    def visit(s, sid, path):
        if not isinstance(s, dict):
            return
        if s.get("location") or s.get("transit"):
            out.append((sid, s, path))
        for gi, o in enumerate(s.get("options") or [], 1):
            if not isinstance(o, dict):
                continue
            if "steps" in o:               # plan: el grupo mismo es el contenedor
                for si, sub in enumerate(o["steps"], 1):
                    visit(sub, f"{sid}-g{gi}-s{si}", path + ((sid, f"g{gi}"),))
            else:                          # tier: contenedor = cada opción
                for oi, x in enumerate(o.get("options") or [], 1):
                    if not isinstance(x, dict):
                        continue
                    for si, sub in enumerate(x.get("steps") or [], 1):
                        visit(sub, f"{sid}-g{gi}-o{oi}-s{si}",
                              path + ((sid, f"g{gi}-o{oi}"),))

    for i, s in enumerate(day.get("steps", [])):
        visit(s, f"d{num}-r{i + 1:02d}", ())
    return out


def anchors_tokens():
    """GEO['anchors']: id de fila → {prev, next} para cada transit sin coords
    (el rastreo queda acotado al día, como el conector automático)."""
    anchors = {}
    for num, day in enumerate(render.DAYS, 1):
        rows = _collect_rows(day, num)
        for i, (sid, s, path) in enumerate(rows):
            if s.get("location") or not s.get("transit"):
                continue                   # el conector automático es solo transit
            key = s["transit"]
            if render._place_pt(key) or render._transit_pts(key):
                continue                   # con geometría propia no hay conector
            prev = nxt = None
            for j in range(i - 1, -1, -1):
                if not _same_branch(path, rows[j][2]):
                    continue               # no anclar en OTRA opción
                prev = _step_anchor_pt(rows[j][1], True)
                if prev:
                    break
            for j in range(i + 1, len(rows)):
                if not _same_branch(path, rows[j][2]):
                    continue
                nxt = _step_anchor_pt(rows[j][1], False)
                if nxt:
                    break
            anchors[sid] = {"prev": prev, "next": nxt}
    return anchors


def spans_tokens(trip):
    """spans de TEXTO por id de fila y por entidad + sha git del YAML: con
    esto la página editada EN LÍNEA (dev-github.js) corta/empalma el archivo
    vía contents API con la MISMA semántica que el dev_server local, sin
    parsear YAML en el navegador. Ligado al blob sha: si el sitio va atrás
    del archivo, el editor lo detecta y espera el deploy."""
    import hashlib
    import dev_server as ds     # la lógica de spans (compose marks) vive ahí
    path = os.path.join(render_root(), "src", trip, "viaje.yaml")
    raw = open(path, "rb").read()
    sha = hashlib.sha1(b"blob %d\x00" % len(raw) + raw).hexdigest()
    text = raw.decode("utf-8")
    lines = text.splitlines(keepends=True)
    root = yaml.compose(text)
    steps = {}

    def walk(day_n, step_n, sub, s):
        sid = f"d{day_n}-r{step_n:02d}{sub}"
        try:
            seq, idx = ds._resolve_step_seq(root, day_n, step_n, sub)
            steps[sid] = list(ds._seq_item_span(seq, idx, len(lines)))
        except Exception:
            return
        for gi, o in enumerate(s.get("options") or [], 1):
            if not isinstance(o, dict):
                continue
            if "steps" in o:
                for si, sub_s in enumerate(o["steps"], 1):
                    if isinstance(sub_s, dict):
                        walk(day_n, step_n, f"{sub}-g{gi}-s{si}", sub_s)
            else:
                for oi, x in enumerate(o.get("options") or [], 1):
                    if isinstance(x, dict):
                        for si, sub_s in enumerate(x.get("steps") or [], 1):
                            if isinstance(sub_s, dict):
                                walk(day_n, step_n, f"{sub}-g{gi}-o{oi}-s{si}", sub_s)

    for dn, day in enumerate(render.DAYS, 1):
        for sn, s in enumerate(day.get("steps", []), 1):
            if isinstance(s, dict):
                walk(dn, sn, "", s)
    ents = {}
    data = yaml.safe_load(text)
    for kind in ("places", "transits", "lines"):
        for key in (data.get(kind) or {}):
            try:
                k, a, b, col = ds._entity_span(root, [kind], key, len(lines))
                ents[key] = [k, a, b, col]
            except Exception:
                pass
    return {"sha": sha, "repo": "ratgr/viajes-2",
            "path": f"src/{trip}/viaje.yaml", "branch": "main",
            "steps": steps, "entities": ents}


def _poi_entry(key, pt):
    """tupla de POI para el GEO: [lat, lon, clave, nombre, zona?] — la zona
    (polígono `zone:` del place: calle/barrio) va como 5º elemento opcional."""
    pl = render.PLACES.get(key, {})
    entry = [pt[0], pt[1], key, pl.get("name", key)]
    zone = pl.get("zone")
    if zone:
        zp = render.parse_pts(str(zone), f"places[{key}].zone")
        if zp and len(zp) >= 3:
            entry.append([[a, b] for a, b in zp])
    return entry


def geo_tokens():
    """geometría por clave YAML para el mapa: gps de places, coords de transits.
    (Se inyecta como JSON aparte: las coordenadas no son parte de las filas.)"""
    locs = {}
    for key, pl in render.PLACES.items():
        gps = pl.get("gps")
        if gps:
            pt = render.parse_pts(gps, f"places[{key}]")
            if not pt:
                continue          # malformado: ya quedó en DIAGNOSTICS
            locs[key] = [pt[0][0], pt[0][1]]
    transits = {}
    for key, tr in render.TRANSITS.items():
        coords = tr.get("coords")
        if coords:
            parsed = render.parse_pts(coords, f"transits[{key}]")
            if not parsed:
                continue
            pts = [[a, b] for a, b in parsed]
            entry = {"coords": pts, "color": tr.get("color", "#7a6f63"),
                     "mode": tr.get("mode", "walk")}
            # rieles: cada vértice ES una estación ([código, jp, romaji]) —
            # el mapa las pinta como paradas con nombre si las cuentas calzan
            stations = tr.get("stations")
            if stations:
                entry["stations"] = [
                    (s[2] or s[1]) if isinstance(s, list) and len(s) >= 3 else str(s)
                    for s in stations
                ]
            # stops: posiciones de estación cuando coords ya es el trazo DENSO
            # (geometría OSM) y perdió la alineación 1 vértice = 1 estación
            stops = tr.get("stops")
            if stops:
                sp = render.parse_pts(stops, f"transits[{key}].stops")
                if sp:
                    entry["stops"] = [[a, b] for a, b in sp]
            # puntos de interés del tramo: claves de places (separadas por
            # espacio) que se pintan JUNTO al trazo — pois: mirador tienda-x
            pois = tr.get("pois")
            if pois:
                lst = []
                for pk in str(pois).split():
                    pt = render._place_pt(pk)
                    if pt:
                        lst.append(_poi_entry(pk, pt))
                if lst:
                    entry["pois"] = lst
            transits[key] = entry
    # caja del viaje (vista inicial del mapa) + nombre del viaje (identidad
    # para el modo dev, en vez de olfatear la URL)
    pts = list(locs.values()) + [p for t in transits.values() for p in t["coords"]]
    # POIs de guía: places con `poi: <cluster>` agrupados por su cluster
    clusters = {}
    for key, pl in render.PLACES.items():
        cl = pl.get("poi")
        if not cl:
            continue
        pt = render._place_pt(key)
        if pt:
            clusters.setdefault(str(cl), []).append(_poi_entry(key, pt))
    geo = {"locations": locs, "transits": transits, "trip": _TRIP[0],
           "poiClusters": clusters,
           "anchors": anchors_tokens(), "edit": spans_tokens(_TRIP[0]),
           "buildSha": os.environ.get("GITHUB_SHA", "")}
    if pts:
        geo["bbox"] = [min(p[0] for p in pts), min(p[1] for p in pts),
                       max(p[0] for p in pts), max(p[1] for p in pts)]
    return {"<!--GEO-->": json.dumps(geo, ensure_ascii=False)}


_TRIP = [""]   # fijado por main antes del build (geo_tokens corre dentro)


def gen_pwa(trip):
    """sw.js con PRECACHE de TODO el release (el sitio entero funciona sin
    red: imágenes incluidas — Cache Storage, no localStorage: los archivos no
    caben ahí). Los tiles del mapa van en caché de runtime (red primero).
    Corre al final del build del mapa = último paso del pipeline."""
    import hashlib
    import json as _json
    pages_dir = os.path.join(render_root(), "pages", trip)
    files = []
    for base, _dirs, fns in os.walk(pages_dir):
        for fn in fns:
            if fn == "sw.js":
                continue
            p = os.path.join(base, fn)
            rel = os.path.relpath(p, pages_dir).replace(os.sep, "/")
            files.append((rel, os.path.getsize(p)))
    files.sort()
    # versión por COMMIT (CI) o por contenido real — nunca solo la lista de
    # archivos: una edición del mismo tamaño no cambiaría sw.js y los
    # navegadores se quedarían con la versión vieja para siempre
    ver = (os.environ.get("GITHUB_SHA") or "")[:12]
    if not ver:
        h = hashlib.sha1()
        for rel, _s in files:
            h.update(rel.encode())
            with open(os.path.join(pages_dir, rel.replace("/", os.sep)), "rb") as fh:
                h.update(fh.read())
        ver = h.hexdigest()[:12]
    lista = _json.dumps(["./"] + [f for f, _s in files], ensure_ascii=False)
    sw = """// generado por build_mapa.gen_pwa — NO editar a mano
const CACHE = 'viaje-%s';
const TILES = 'viaje-tiles';
const PRECACHE = %s;
self.addEventListener('install', (e) => {
  e.waitUntil((async () => {
    const c = await caches.open(CACHE);
    // en lotes y tolerante: una imagen caída no debe tirar la instalación.
    // cache:'no-cache' — GitHub Pages sirve max-age=600 y sin esto la
    // instalación nueva copiaría assets VIEJOS del caché HTTP (versión mixta)
    for (let i = 0; i < PRECACHE.length; i += 20) {
      await Promise.allSettled(PRECACHE.slice(i, i + 20).map((u) =>
        c.add(new Request(u, { cache: 'no-cache' }))));
    }
    self.skipWaiting();
  })());
});
self.addEventListener('activate', (e) => {
  e.waitUntil((async () => {
    for (const k of await caches.keys()) {
      if (k !== CACHE && k !== TILES) await caches.delete(k);
    }
    self.clients.claim();
  })());
});
self.addEventListener('fetch', (e) => {
  const url = new URL(e.request.url);
  if (e.request.method !== 'GET') return;
  if (url.hostname.endsWith('cartocdn.com')) {
    // tiles: red primero, caché de respaldo (offline se ve lo ya visitado)
    e.respondWith((async () => {
      const c = await caches.open(TILES);
      try {
        const r = await fetch(e.request);
        c.put(e.request, r.clone());
        return r;
      } catch (err) {
        const hit = await c.match(e.request);
        if (hit) return hit;
        throw err;
      }
    })());
    return;
  }
  if (url.origin === location.origin) {
    // el sitio: caché primero (instalado = completo), red de respaldo
    e.respondWith((async () => {
      const hit = await caches.match(e.request, { ignoreSearch: true });
      return hit || fetch(e.request);
    })());
  }
});
""" % (ver, lista)
    with open(os.path.join(pages_dir, "sw.js"), "w", encoding="utf-8", newline="\n") as f:
        f.write(sw)
    total = sum(s for _f, s in files)
    print(f"pwa: sw.js v{ver} · {len(files)} archivos precache · {total // 1024 // 1024} MB")


def render_root():
    import common
    return common.ROOT


def main():
    _TRIP[0] = resolve_trip(sys.argv)
    rc = render.build_and_verify(_TRIP[0], "plantilla-mapa.html", "mapa.html",
                                 extra=geo_tokens)
    if rc == 0:
        gen_pwa(_TRIP[0])
    return rc


if __name__ == "__main__":
    sys.exit(main())
