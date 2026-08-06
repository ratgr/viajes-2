# -*- coding: utf-8 -*-
"""render.py — el renderer compartido YAML → fragmentos HTML (días, filas,
options, modales) y el ensamblado de página sobre una plantilla con tokens.

Lo usan build_itinerario.py y build_mapa.py: el markup de los días es EL MISMO
en ambas páginas (proyección 1:1 del YAML, verify_roundtrip la comprueba);
cada página agrega su cromo por CSS/JS estático, no cambiando el HTML.

Uso: render.build_page(trip, "plantilla-X.html", "salida.html")
"""
import html
import math
import os
import re
import shutil

import yaml

from common import ASSETS, trip_paths

# estado del viaje activo (lo fija init)
PLACES = LINEAS = TRANSITS = None
DAYS = []
FOTO_BASE = ""
_LINE_BY_NAME = _LINE_BY_CHIP = None
TRANSIT_STEP = {}


def init(data, foto_base=""):
    """carga los catálogos del viaje en el módulo (los renderers los leen)."""
    global PLACES, LINEAS, TRANSITS, DAYS, FOTO_BASE
    global _LINE_BY_NAME, _LINE_BY_CHIP, TRANSIT_STEP
    PLACES = data.get("places", {})
    LINEAS = data.get("lineas", {})
    TRANSITS = data.get("transits", {})
    DAYS = data.get("days", [])
    FOTO_BASE = foto_base
    # identidad de línea (frecuencia/horarios) por nombre o por chip
    _LINE_BY_NAME = {v.get("nombre"): v for v in LINEAS.values() if v.get("frecuencia")}
    _LINE_BY_CHIP = {v.get("chip"): v for v in LINEAS.values() if v.get("frecuencia") and v.get("chip")}
    # primer step que usa cada transit (da el renglón Sale/Llega de su modal)
    DIAGNOSTICS.clear()
    TRANSIT_STEP = {}
    for day in DAYS:
        for step in day.get("steps", []):
            if "transit" in step:
                TRANSIT_STEP.setdefault(step["transit"], step)


# icono de un paso de transporte (derivado de mode; no vive en el título)
MODE_ICON = {"train": "🚇", "walk": "🚶", "monorail": "🚝", "flight": "✈️",
             "tramite": "🧳", "bus": "🚌", "ferry": "⛴️", "tour": "🚌"}
# vehículo → término japonés para la frase de auxilio del modal de línea
VEH_JP = {"tren": "電車", "bus": "バス", "barco": "船"}
VEH_RO = {"tren": "densha", "bus": "basu", "barco": "fune"}
REF_RE = re.compile(r"@\[(.+?)\]\((.+?)\)")



# ---------------------------------------------------------------- utilidades
def line_meta(tr):
    l = _LINE_BY_NAME.get(tr.get("linea")) or _LINE_BY_CHIP.get(tr.get("chip")) or {}
    return {k: l[k] for k in ("frecuencia", "primer_tren", "ultimo_tren", "frecuencia_fuente") if l.get(k)}


def dmin(s):
    """'1 h 05' → 65 · '15 min' → 15 · '2' → 2."""
    s = str(s or "")
    hm = re.search(r"(\d+)\s*h\s*(\d+)?", s)
    if hm:
        return int(hm.group(1)) * 60 + int(hm.group(2) or 0)
    m = re.search(r"(\d+)\s*min", s)
    if m:
        return int(m.group(1))
    m2 = re.search(r"(\d+)", s)
    return int(m2.group(1)) if m2 else 0


def add_min(hhmm, mins):
    """'21:45' + 10 → '21:55'."""
    m = re.match(r"^(\d{1,2}):(\d{2})$", str(hhmm or "").strip())
    if not m:
        return ""
    total = (int(m.group(1)) * 60 + int(m.group(2)) + int(mins or 0)) % (24 * 60)
    return f"{total // 60:02d}:{total % 60:02d}"


def hm_min(hhmm):
    """'07:15' → 435 · otra cosa → None."""
    m = re.match(r"^(\d{1,2}):(\d{2})$", str(hhmm or "").strip())
    return int(m.group(1)) * 60 + int(m.group(2)) if m else None


def fmt_hm(total):
    return f"{total // 60 % 24:02d}:{total % 60:02d}"


def fmt_dur(mins):
    """65 → '1 h 05' · 15 → '15 min'."""
    if mins < 60:
        return f"{mins} min"
    h, m = divmod(mins, 60)
    return f"{h} h {m:02d}" if m else f"{h} h"


DIAGNOSTICS = []   # pasos cuyo horario no se puede completar: problema del YAML

WALK_M_PER_MIN = 4000 / 60          # humano a 4 km/h


def _crow_m(a, b):
    """metros aprox entre dos (lat,lng) — equirectangular."""
    dy = (b[0] - a[0]) * 111000
    dx = (b[1] - a[1]) * 111000 * math.cos(math.radians(a[0]))
    return math.hypot(dx, dy)


def round_walk(mins):
    """redondeo de caminatas: al múltiplo de 5 que la encierra hasta 45;
    de ahí en adelante, al múltiplo de 15."""
    m5 = max(5, math.ceil(mins / 5) * 5)
    return m5 if m5 <= 45 else math.ceil(mins / 15) * 15


def walk_calc(coords_str):
    """(metros, minutos redondeados) del camino a pie."""
    pts = [tuple(float(x) for x in p.split(",")) for p in str(coords_str).split()]
    dist = sum(_crow_m(pts[i - 1], pts[i]) for i in range(1, len(pts)))
    return dist, round_walk(dist / WALK_M_PER_MIN)


def step_walk_geometry(s):
    """coords del paso si es una caminata (mode walk propio o de su transit)."""
    tr = TRANSITS.get(s.get("transit"), {}) if s.get("transit") else {}
    mode = s.get("mode") or tr.get("mode")
    coords = tr.get("coords") or s.get("coords")
    return coords if (mode == "walk" and coords) else None


def derive_schedule(steps, ctx=""):
    """Horario por paso, completado por SNAP a los vecinos:
      · sin inicio → snap ARRIBA (fin del paso anterior) o ABAJO (inicio del
        siguiente − duración propia)
      · sin duración → snap ABAJO (hueco hasta el próximo inicio explícito)
    Regla: cada paso debe quedar con 2 de {inicio, fin, duración}. Un LUGAR
    con solo inicio es un ancla válida (llegas y punto); cualquier otro paso
    incompleto es un problema del YAML → va a DIAGNOSTICS.
    Todo lo inferido se marca data-derived al render."""
    n = len(steps)
    info = []
    for i, s in enumerate(steps):
        if not isinstance(s, dict) or s.get("hidden-summary"):
            info.append(None)
            continue
        beg = hm_min(s.get("time"))
        has_dur = s.get("duration") not in (None, 0, "0")
        fo = {"begin": beg, "beg_exp": beg is not None, "beg_derived": False,
              "dur": dmin(s.get("duration")) if has_dur else None,
              "dur_derived": False, "end": None}
        # caminatas: la geometría dicta la duración (4 km/h + redondeo);
        # si el YAML trae otra cosa, es un diagnóstico
        coords = step_walk_geometry(s)
        if coords:
            dist, esperado = walk_calc(coords)
            if fo["dur"] is None:
                fo["dur"], fo["dur_derived"] = esperado, True
            elif fo["dur"] != esperado:
                title = str(s.get("title", ""))[:52]
                DIAGNOSTICS.append(f"{ctx} paso {i + 1} «{title}»: caminata dice "
                                   f"{fo['dur']} min pero el camino mide {dist:.0f} m "
                                   f"≈ {esperado} min a 4 km/h")
        info.append(fo)

    def next_begin(i):
        for j in range(i + 1, n):
            if info[j] and info[j]["beg_exp"]:
                return info[j]["begin"]
        return None

    # pasada adelante: inicio = fin del anterior; duración = hueco al siguiente
    cursor = None
    for i, fo in enumerate(info):
        if fo is None:
            continue
        if fo["begin"] is None and cursor is not None:
            fo["begin"], fo["beg_derived"] = cursor, True
        if fo["dur"] is None and fo["begin"] is not None:
            nb = next_begin(i)
            if nb is not None and nb > fo["begin"]:
                fo["dur"], fo["dur_derived"] = nb - fo["begin"], True
        if fo["begin"] is not None and fo["dur"]:
            fo["end"] = fo["begin"] + fo["dur"]
        cursor = fo["end"] if fo["end"] is not None else fo["begin"]
    # pasada atrás: con duración pero sin inicio → fin = inicio del siguiente
    for i in range(n - 1, -1, -1):
        fo = info[i]
        if fo is None or fo["begin"] is not None or not fo["dur"]:
            continue
        nb = next_begin(i)
        if nb is not None:
            fo["end"] = nb
            fo["begin"], fo["beg_derived"] = nb - fo["dur"], True
    # diagnóstico
    for i, (s, fo) in enumerate(zip(steps, info)):
        if fo is None:
            continue
        title = str(s.get("title", ""))[:52]
        if fo["begin"] is None:
            DIAGNOSTICS.append(f"{ctx} paso {i + 1} «{title}»: sin inicio anclable (ni arriba ni abajo)")
        elif not fo["dur"] and "location" not in s:
            DIAGNOSTICS.append(f"{ctx} paso {i + 1} «{title}»: solo inicio — falta duración o fin")
    return [{} if fo is None else
            {"start": fo["begin"], "start_derived": fo["beg_derived"],
             "dur": fo["dur"], "dur_derived": fo["dur_derived"], "end": fo["end"]}
            for fo in info]


class RefLog(set):
    """set que además recuerda el orden de primera aparición."""

    def __init__(self):
        super().__init__()
        self.order = []

    def add(self, k):
        if k not in self:
            self.order.append(k)
        super().add(k)


def md(s, refs=None):
    """markdown mínimo (**b**, *i*, saltos de línea) + refs @[alt](clave)."""
    if s is None:
        return ""
    s = html.escape(str(s).strip(), quote=False)

    def _ref(m):
        alt, key = m.group(1), m.group(2)
        if refs is not None:
            refs.add(key)
        tr = TRANSITS.get(key, {})
        chip = ""
        if tr.get("color"):
            cls = "line-chip" if tr.get("chip") else "line-chip dot"
            chip = f'<i class="{cls}" style="--lc:{tr["color"]}">{html.escape(tr.get("chip", ""))}</i>'
        return f'<a class="modal-link" href="#m-{key}">{chip}{alt}</a>'

    s = REF_RE.sub(_ref, s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
    s = re.sub(r"\*(.+?)\*", r"<i>\1</i>", s)
    return s.replace("\n", "<br>")


# ---------------------------------------------------------------- filas del día
def mode_icon(n):
    """icono del transporte como nodo de texto real (copiable), marcado derivado."""
    if "transit" not in n and not n.get("mode"):
        return ""
    mode = n.get("mode") or TRANSITS.get(n.get("transit"), {}).get("mode", "walk")
    ic = MODE_ICON.get(mode, "")
    return f'<i class="icon" data-derived="mode">{ic}</i> ' if ic else ""


def row_text(n, refs, sc=None):
    """<b.title> - <span.duration> - <span.note> — campos separados, no un blob.
    El separador vive DENTRO del span que sigue: ocultar un campo por CSS
    (p.ej. la nota en la barra del mapa) se lleva su separador consigo.
    Sin duration en el YAML, se emite la inferida (~hueco) marcada derivada."""
    sc = sc or {}
    parts = []
    if n.get("title"):
        title = str(n["title"]).replace("*", "")   # defensa; migrate_yaml ya los quita
        parts.append(f'<b class="title">{mode_icon(n)}{md(title, refs)}</b>')
    if n.get("duration") not in (None, 0, "0"):
        sep = '<span class="sep"> - </span>' if parts else ""
        parts.append(f'<span class="duration">{sep}{html.escape(str(n["duration"]))}</span>')
    elif sc.get("dur") and sc.get("dur_derived"):
        sep = '<span class="sep"> - </span>' if parts else ""
        parts.append(f'<span class="duration" data-derived="duracion">{sep}~{fmt_dur(sc["dur"])}</span>')
    if n.get("note"):
        sep = '<span class="sep"> - </span>' if parts else ""
        parts.append(f'<span class="note">{sep}{md(str(n["note"]).strip(), refs)}</span>')
    return "".join(parts)


def time_cell(n, sc=None):
    """hora explícita + (derivados: inicio encadenado si falta, y la hora-fin).
    El itinerario esconde lo derivado por CSS; el mapa muestra DESDE–HASTA."""
    sc = sc or {}
    t = str(n.get("time") or "")
    cls = "time fixed" if n.get("fixed") else "time"
    dt = f' datetime="{t}"' if re.match(r"^\d{1,2}:\d{2}$", t) else ""
    inner = html.escape(t)
    if not t and sc.get("start_derived"):
        inner = f'<span class="from" data-derived="inicio">{fmt_hm(sc["start"])}</span>'
    if sc.get("end") is not None and inner:
        inner += f'<span class="to" data-derived="fin">–{fmt_hm(sc["end"])}</span>'
    return f'<time class="{cls}"{dt}>{inner}</time>'


def resto_link(opt, refs):
    """opción hoja { location: acchichi, precio: ¥600 }."""
    key = opt.get("location")
    nombre = html.escape(PLACES.get(key, {}).get("nombre", key or "?"))
    if key:
        refs.add(key)
    lk = f'<a class="modal-link" href="#m-{key}">{nombre}</a>' if key else nombre
    precio = opt.get("precio")
    return lk + (f' <span class="precio">{html.escape(str(precio))}</span>' if precio else "")


def render_options(node, refs, ctx=""):
    """options unificadas: MISMO markup para tiers de comida y planes en
    paralelo (en el YAML son la misma clave). El CSS decide el render por
    item: con sub-steps (:has) = tarjeta plan, sin ellos = cajita tier."""
    items = []
    for o in node.get("options", []):
        if not isinstance(o, dict):
            continue
        if "steps" in o:
            plan_title = str(o.get("title", "")).replace("*", "")
            title = md(plan_title, refs)
            sched = derive_schedule(o["steps"], f'{ctx} plan «{plan_title[:24]}»')
            subs = "\n".join(render_li(s, refs, sc=sched[i], ctx=ctx) for i, s in enumerate(o["steps"]))
            items.append(f'<li><b>{title}</b><ul class="steps">\n{subs}\n</ul></li>')
        else:
            label = html.escape(str(o.get("title", "")))
            inner = " · ".join(resto_link(x, refs) for x in o.get("options", []))
            items.append(f'<li data-tier="{label}"><b>{label}</b>{inner}</li>')
    return '<ul class="options">' + "".join(items) + "</ul>"


def render_li(n, refs, row_id=None, sc=None, ctx=""):
    body = row_text(n, refs, sc)
    if "options" in n:
        body += render_options(n, refs, ctx or row_id or "")
    elif "transit" in n:
        # los trayectos van en gris para que resalten los lugares
        body = f'<span class="transit">{body}</span>'
    # la fila lleva TODO su paso YAML: claves como data-*, flags como clase
    attrs = f' id="{row_id}"' if row_id else ""
    if n.get("hidden-summary"):
        attrs += ' class="hidden-summary"'
    if n.get("location"):
        attrs += f' data-location="{html.escape(str(n["location"]))}"'
    elif n.get("transit"):
        attrs += f' data-transit="{html.escape(str(n["transit"]))}"'
    if n.get("mode"):
        attrs += f' data-mode="{html.escape(str(n["mode"]))}"'
    if n.get("solo_seleccion"):
        attrs += " data-solo-seleccion"
    return f'    <li{attrs}>{time_cell(n, sc)}<div class="body">{body}</div></li>'


def render_day(day, refs, num):
    """num = día 1..N → ancla corta #d1 (la fecha queda en data-fecha)."""
    titulo = html.escape(day.get("titulo", ""))
    note = html.escape(day.get("note", ""))
    ancla = html.escape(day.get("ancla", ""))
    fecha = day.get("date")
    fecha = fecha.isoformat() if hasattr(fecha, "isoformat") else str(fecha)
    head = (f'<header class="day-head"><h3>{titulo}</h3>'
            f'<span class="note">{note}</span>'
            f'<span class="ancla">Ancla: {ancla}</span></header>')
    # TODOS los pasos van al DOM (hidden-summary incluidos, ocultos por CSS):
    # la fila rNN es EXACTAMENTE el paso N del YAML
    sched = derive_schedule(day.get("steps", []), f"d{num}")
    lis = "\n".join(render_li(s, refs, f"d{num}-r{i + 1:02d}", sched[i], ctx=f"d{num}")
                    for i, s in enumerate(day.get("steps", [])))
    return (f'  <section class="day" id="d{num}" data-fecha="{fecha}">{head}\n'
            f'  <ul class="steps">\n{lis}\n  </ul></section>')


def nav_link(day, num):
    label = str(day.get("titulo", "")).split("·")[0].strip() or f"día {num}"
    return f'<a href="#d{num}">{html.escape(label)}</a>'


# ---------------------------------------------------------------- modales
def render_place_modal(key, pl):
    nombre = html.escape(pl.get("nombre", key))
    out = [f"<h3>{nombre}</h3>"]
    if pl.get("imagen"):
        im = pl["imagen"]
        src = im if im.startswith("http") else FOTO_BASE + im
        out.append(f'<img src="{html.escape(src)}" alt="{nombre}" loading="lazy">')
    if pl.get("descripcion"):
        out.append(f"<p>{md(pl['descripcion'])}</p>")
    if pl.get("informacion"):
        out.append(f'<p class="modal-note">{md(pl["informacion"])}</p>')
    if pl.get("horario"):
        src = ' <span class="src-tag">· Google Maps</span>' if pl.get("horario_fuente") == "maps" else ""
        out.append(f'<p class="modal-note">🕒 <b>Horario:</b> {html.escape(str(pl["horario"]))}{src}</p>')
    if pl.get("maps"):
        out.append(f'<a class="modal-btn" href="{html.escape(pl["maps"])}" target="_blank" rel="noopener">Abrir en Maps ↗</a>')
    inner = "\n  ".join(out)
    return f'<div class="modal" id="m-{key}">\n  {inner}\n</div>'


def render_line_modal(key, ident, ride=None, guia=None, horario=None):
    color = ident.get("color", "#555")
    chip = ident.get("chip", "")
    jp = html.escape(ident.get("nombre_jp", ""))
    nombre = html.escape(ident.get("nombre", key))
    rng = ""
    if horario and horario.get("desde") and horario.get("hasta"):
        rng = (f' <span class="h3-range" data-derived="horario">· {html.escape(str(horario["desde"]))}'
               f' – {html.escape(str(horario["hasta"]))}</span>')
    h = [f"<h3>{nombre}{rng}</h3>"]

    # banner con el nombre en japonés y el chip de la línea
    badge = f'<div class="badge-row"><span class="badge">{html.escape(chip)}</span></div>' if chip else ""
    h.append(f'<div class="line-banner"><div class="jp" lang="ja">{jp}</div>{badge}</div>')

    if ident.get("frecuencia"):
        row = f'🔄 Pasa <b>{html.escape(str(ident["frecuencia"]))}</b>'
        if ident.get("primer_tren") or ident.get("ultimo_tren"):
            row += (f' · 🚉 {html.escape(str(ident.get("primer_tren", "")))}'
                    f'–{html.escape(str(ident.get("ultimo_tren", "")))}')
        src = ident.get("frecuencia_fuente")
        h.append(f'<p class="freq{" has-src" if src else ""}">{row}</p>')
        if src:
            h.append(f'<div class="freq-src"><a href="{html.escape(str(src))}" '
                     f'target="_blank" rel="noopener">horario oficial ↗</a></div>')

    # renglón Sale {desde} · origen → destino · Llega {hasta} (calculado)
    if horario and (horario.get("desde") or horario.get("hasta")):
        o = html.escape(str(horario.get("origen", "")))
        d = html.escape(str(horario.get("destino", "")))
        desde = html.escape(str(horario.get("desde", "")))
        hasta = html.escape(str(horario.get("hasta", "")))
        h.append(f'<div class="ride" data-derived="horario">'
                 f'<span>🟢 <b>Sale {desde}</b><br><span class="stn">{o}</span></span>'
                 f'<span class="arrow">→</span>'
                 f'<span class="arr">🔴 <b>Llega {hasta}</b><br><span class="stn">{d}</span></span></div>')

    if ride:
        anden = ride.get("anden", ["", ""])
        veh = ride.get("vehiculo", "tren")
        ic, lab, word = {"barco": ("🛳️", "Embarcadero correcto", "muelle"),
                         "bus": ("🚏", "Parada correcta", "lado")}.get(veh, ("🧭", "Andén correcto", "andén"))
        h.append(f'<p class="platform">{ic} <b>{lab}:</b> letrero '
                 f'<b class="sign" lang="ja">{html.escape(str(anden[0]))}</b> — {html.escape(str(anden[1]))}</p>')
        if ride.get("reverso"):
            h.append(f'<p class="reverse">⚠️ Si la primera parada es '
                     f'<b>{html.escape(str(ride["reverso"]))}</b>, van al revés: bajarse y cruzar de {word}.</p>')
        est = ride.get("estaciones", [])
        if est:
            h.append('<div class="stations">')
            for i, st in enumerate(est):
                code, sjp, srom = (list(st) + ["", "", ""])[:3]
                tag = ' 🟢 <small data-derived="pos"><b>SUBIR</b></small>' if i == 0 else (
                    ' 🔴 <small data-derived="pos"><b>BAJAR</b></small>' if i == len(est) - 1 else "")
                dot = f'<span class="station-code">{html.escape(str(code))}</span> ' if code else "· "
                h.append(f'<div class="station">{dot}<b lang="ja">{html.escape(str(sjp))}</b> '
                         f'<span class="romaji">{html.escape(str(srom))}</span>{tag}</div>')
            h.append("</div>")
            # frase para enseñar el teléfono: «¿voy bien en este tren/bus/barco?»
            dest = est[-1]
            djp, drom = html.escape(str(dest[1])), html.escape(str(dest[2]))
            eki = "駅" if (veh == "tren" and "駅" not in str(dest[1]) and "ターミナル" not in str(dest[1])) else ""
            h.append(f'<div class="phrase" data-derived="frase">'
                     f'<div class="jp" lang="ja">すみません、{djp}{eki}へ行きたいです。この{VEH_JP.get(veh, "電車")}で合っていますか？</div>'
                     f'<div class="romaji">Sumimasen, {drom}{"-eki" if eki else ""} e ikitai desu. '
                     f'Kono {VEH_RO.get(veh, "densha")} de atte imasu ka?</div>'
                     f'<div class="gloss">«Disculpe, quiero ir a {drom}. ¿Voy bien en este {veh}?» — '
                     f'muéstrale el teléfono a cualquier local o uniformado.</div></div>')

    reconoce = html.escape(ident.get("reconoce", ""))
    tail = f'<b>Se reconoce:</b> {reconoce}{" — letra <b>" + html.escape(chip) + "</b>" if chip else ""}.'
    texto = guia or ident.get("extra", "")
    if texto:
        tail += f"<br><br>{md(texto)}"
    h.append(f'<p class="reconoce">{tail}</p>')   # en un elemento: el corte del popup lo puede ocultar
    inner = "\n  ".join(h)
    return f'<div class="modal" id="m-{key}" style="--lc:{color}">\n  {inner}\n</div>'


def render_modal(key):
    if key in PLACES:
        return render_place_modal(key, PLACES[key])
    if key in TRANSITS and TRANSITS[key].get("nombre_jp"):
        tr = TRANSITS[key]
        ident = {"nombre": tr.get("linea", key), "nombre_jp": tr.get("nombre_jp", ""),
                 "chip": tr.get("chip", ""), "color": tr.get("color", "#555"),
                 "reconoce": tr.get("reconoce", ""), **line_meta(tr)}
        ride = {k: tr[k] for k in ("anden", "reverso", "estaciones", "vehiculo") if k in tr}
        st = TRANSIT_STEP.get(key, {})
        horario = None
        if tr.get("estaciones") and st.get("time"):
            horario = {"origen": tr["estaciones"][0][2], "destino": tr["estaciones"][-1][2],
                       "desde": str(st["time"]), "hasta": add_min(st["time"], dmin(st.get("duration")))}
        return render_line_modal(key, ident, ride, tr.get("guia"), horario)
    if key in LINEAS:
        return render_line_modal(key, LINEAS[key])
    return f'<div class="modal" id="m-{key}"><h3>{html.escape(key)}</h3></div>'

# ---------------------------------------------------------------- ensamblado
def build_page(trip, template_name, out_name, extra=None):
    """src/<trip>/viaje.yaml + src/<trip>/<template> → pages/<trip>/<out>.
    `extra`: callable (corre tras init) que devuelve tokens adicionales."""
    src_dir, pages_dir, cfg = trip_paths(trip)
    data = yaml.safe_load(open(os.path.join(src_dir, "viaje.yaml"), encoding="utf-8"))
    init(data, cfg.get("foto_base", ""))

    refs = RefLog()
    days = "\n\n".join(render_day(d, refs, i + 1) for i, d in enumerate(DAYS))
    nav = "".join(nav_link(d, i + 1) for i, d in enumerate(DAYS))
    modals = "\n".join(render_modal(k) for k in refs.order)

    tokens = {"<!--NAV-->": nav, "<!--DAYS-->": days, "<!--MODALS-->": modals}
    if extra:
        tokens.update(extra())
    page = open(os.path.join(src_dir, template_name), encoding="utf-8").read()
    for token, value in tokens.items():
        assert token in page, f"{template_name} sin {token}"
        page = page.replace(token, value, 1)
    os.makedirs(pages_dir, exist_ok=True)
    with open(os.path.join(pages_dir, out_name), "w", encoding="utf-8") as f:
        f.write(page)
    # el release es autocontenido: css/js compartidos se copian junto a la página
    for asset in os.listdir(ASSETS):
        shutil.copyfile(os.path.join(ASSETS, asset), os.path.join(pages_dir, asset))
    print(f"pages/{trip}/{out_name} · {len(DAYS)} días · {len(refs.order)} modales · {len(page) // 1024} KB")
    if DIAGNOSTICS:
        print(f"⚠️ horario incompleto en el YAML ({len(DIAGNOSTICS)} pasos):")
        for d in DIAGNOSTICS:
            print("  ·", d)
