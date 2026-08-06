# -*- coding: utf-8 -*-
"""build_itinerario.py — viaje.yaml → itinerario.html (página independiente).

Reescritura limpia del bloque que compile_itinerario.py inyecta en japon.html:
mismo contenido y mismas métricas visuales, pero con clases con nombre y sin
estilos inline — el color de cada línea de tren viaja en la variable `--lc`.

    python build_itinerario.py   →   escribe itinerario.html junto a este archivo
"""
import os
import re
import sys
import html

import yaml

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
SD = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(SD, "viaje.yaml")   # copia local limpia (migrate_yaml.py la resincroniza)
OUT = os.path.join(SD, "itinerario.html")
OUT_CSS = os.path.join(SD, "itinerario.css")
OUT_JS = os.path.join(SD, "itinerario.js")
FOTO_BASE = "https://ratgr.github.io/viajes-icons/"

data = yaml.safe_load(open(SRC, encoding="utf-8"))
PLACES = data.get("places", {})
LINEAS = data.get("lineas", {})
TRANSITS = data.get("transits", {})
DAYS = data.get("days", [])

# identidad de línea (frecuencia/horarios) por nombre o por chip
_LINE_BY_NAME = {v.get("nombre"): v for v in LINEAS.values() if v.get("frecuencia")}
_LINE_BY_CHIP = {v.get("chip"): v for v in LINEAS.values() if v.get("frecuencia") and v.get("chip")}


def line_meta(tr):
    l = _LINE_BY_NAME.get(tr.get("linea")) or _LINE_BY_CHIP.get(tr.get("chip")) or {}
    return {k: l[k] for k in ("frecuencia", "primer_tren", "ultimo_tren", "frecuencia_fuente") if l.get(k)}


# primer step que usa cada transit (para el renglón Sale/Llega del modal)
TRANSIT_STEP = {}
for _d in DAYS:
    for _s in _d.get("steps", []):
        if "transit" in _s:
            TRANSIT_STEP.setdefault(_s["transit"], _s)

# ---------------------------------------------------------------- utilidades
VEH_JP = {"tren": "電車", "bus": "バス", "barco": "船"}
VEH_RO = {"tren": "densha", "bus": "basu", "barco": "fune"}
# el icono de un paso de transporte se deriva de su mode (ya no vive en el título)
MODE_ICON = {"train": "🚇", "walk": "🚶", "monorail": "🚝", "flight": "✈️",
             "tramite": "🧳", "bus": "🚌", "ferry": "⛴️", "tour": "🚌"}
REF_RE = re.compile(r"@\[(.+?)\]\((.+?)\)")


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
    m = re.match(r"^(\d{1,2}):(\d{2})$", str(hhmm or "").strip())
    if not m:
        return ""
    total = (int(m.group(1)) * 60 + int(m.group(2)) + int(mins or 0)) % (24 * 60)
    return f"{total // 60:02d}:{total % 60:02d}"


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
    """markdown mínimo (**b** *i*, saltos de línea) + refs @[alt](clave)."""
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
FIXED_TITLES = []   # títulos que traían *asteriscos* (emphasis roto en el viejo)


def mode_icon(n):
    """icono del paso de transporte, derivado de su mode (step o transit).
    Es un nodo de texto real (copiable), marcado como derivado."""
    if "transit" not in n and not n.get("mode"):
        return ""
    mode = n.get("mode") or TRANSITS.get(n.get("transit"), {}).get("mode", "walk")
    ic = MODE_ICON.get(mode, "")
    return f'<i class="icon" data-derived="mode">{ic}</i> ' if ic else ""


def row_text(n, refs):
    """<b.title> - <span.duration> - <span.note> — campos separados, no un blob."""
    parts = []
    if n.get("title"):
        title = str(n["title"])
        # defensa: el yaml local ya viene sin asteriscos (migrate_yaml.py)
        if "*" in title:
            FIXED_TITLES.append(title)
            title = title.replace("*", "")
        parts.append(f'<b class="title">{mode_icon(n)}{md(title, refs)}</b>')
    dur = n.get("duration")
    if dur not in (None, 0, "0"):
        parts.append(f'<span class="duration">{html.escape(str(dur))}</span>')
    if n.get("note"):
        parts.append(f'<span class="note">{md(str(n["note"]).strip(), refs)}</span>')
    return " - ".join(parts)


def time_cell(n):
    t = str(n.get("time") or "")
    cls = "time fixed" if n.get("fixed") else "time"
    dt = f' datetime="{t}"' if re.match(r"^\d{1,2}:\d{2}$", t) else ""
    return f'<time class="{cls}"{dt}>{html.escape(t)}</time>'


def resto_link(opt, refs):
    """opción hoja { location: acchichi, precio: ¥600 }."""
    key = opt.get("location")
    pl = PLACES.get(key, {})
    nombre = html.escape(pl.get("nombre", key or "?"))
    if key:
        refs.add(key)
    lk = f'<a class="modal-link" href="#m-{key}">{nombre}</a>' if key else nombre
    precio = opt.get("precio")
    return lk + (f' <span class="precio">{html.escape(str(precio))}</span>' if precio else "")


def render_options(node, refs):
    """options unificadas: MISMO markup para tiers de comida y planes en
    paralelo (igual que en el YAML son la misma clave). El CSS decide el
    render por item: con sub-steps (:has) = tarjeta plan, sin = cajita tier."""
    items = []
    for o in node.get("options", []):
        if not isinstance(o, dict):
            continue
        if "steps" in o:
            title = md(str(o.get("title", "")).replace("*", ""), refs)
            subs = "\n".join(render_li(s, refs) for s in o["steps"])
            items.append(f'<li><b>{title}</b><ul class="steps">\n{subs}\n</ul></li>')
        else:
            label = html.escape(str(o.get("title", "")))
            inner = " · ".join(resto_link(x, refs) for x in o.get("options", []))
            items.append(f'<li data-tier="{label}"><b>{label}</b>{inner}</li>')
    return '<ul class="options">' + "".join(items) + "</ul>"


def render_li(n, refs, row_id=None):
    if "options" in n:
        body = row_text(n, refs) + render_options(n, refs)
    else:
        body = row_text(n, refs)
    # los trayectos van en gris para que resalten los lugares
    if "transit" in n and "options" not in n:
        body = f'<span class="transit">{body}</span>'
    # la fila lleva TODO su paso YAML: claves como data-*, flags como clase —
    # el HTML es una proyección completa (verify_roundtrip.py lo comprueba)
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
        attrs += ' data-solo-seleccion'
    return f'    <li{attrs}>{time_cell(n)}<div class="body">{body}</div></li>'


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
    # TODOS los pasos van al DOM (los hidden-summary con su clase, el CSS los
    # oculta) → la fila rNN es EXACTAMENTE el paso N del YAML
    steps = day.get("steps", [])
    lis = "\n".join(render_li(s, refs, f"d{num}-r{i + 1:02d}") for i, s in enumerate(steps))
    return (f'  <section class="day" id="d{num}" data-fecha="{fecha}">{head}\n'
            f'  <ul class="steps">\n{lis}\n  </ul></section>')


# ---------------------------------------------------------------- modales
def render_place_modal(key, pl):
    nombre = html.escape(pl.get("nombre", key))
    out = [f'<h3>{nombre}</h3>']
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
    h = [f'<h3>{nombre}{rng}</h3>']

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

    # renglón Sale {desde} · origen → destino · Llega {hasta}
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
                dot = (f'<span class="station-code">{html.escape(str(code))}</span> ') if code else "· "
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
    h.append(tail)
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


# ---------------------------------------------------------------- página
CSS = """
/* ---------- tema (colores idénticos a japon.html, una sola declaración) ---------- */
:root {
  color-scheme: light dark;
  --paper:       light-dark(#faf7f1, #17141c);
  --paper-2:     light-dark(#f1ece2, #201c26);
  --ink:         light-dark(#241f1c, #ebe4dc);
  --ink-soft:    light-dark(#6e6459, #a49a8e);
  --line:        light-dark(#e2dacc, #37313f);
  --shu:         light-dark(#b23a2a, #e0705c);
  --shu-soft:    light-dark(#f4e0da, #3d221d);
  --ai:          light-dark(#2f4a6e, #8fb0d9);
  --ai-soft:     light-dark(#dde5f0, #1f2a38);
  --matcha:      light-dark(#6d7d52, #a3b585);
  --matcha-soft: light-dark(#e4e8d8, #262e1e);
  --gold:        light-dark(#a07c2e, #c9a55a);
  --card:        light-dark(#ffffff, #201c26);
}
/* toggle manual: fija el esquema y light-dark() responde solo */
:root[data-theme="light"] { color-scheme: light; }
:root[data-theme="dark"] { color-scheme: dark; }

/* ---------- base ---------- */
* { box-sizing: border-box; }
body { background: var(--paper); color: var(--ink); font-family: "Segoe UI", "Avenir Next", system-ui, sans-serif; line-height: 1.55; margin: 0; padding: 0 20px 80px; }
.wrap { max-width: 1060px; margin: 0 auto; }

/* ---------- barra de días (sticky) ---------- */
.day-nav { position: sticky; top: 0; z-index: 30; display: flex; gap: 6px; overflow-x: auto; background: var(--paper); border-bottom: 1px solid var(--line); margin: 0 -20px 16px; padding: 8px 12px; scrollbar-width: none; }
.day-nav::-webkit-scrollbar { display: none; }
.day-nav a { flex: 0 0 auto; border: 1px solid var(--line); background: var(--paper-2); color: var(--ink-soft); border-radius: 999px; padding: 5px 11px; font: 700 12px "Segoe UI", system-ui, sans-serif; text-decoration: none; white-space: nowrap; }
.day-nav a.on { background: var(--shu); color: #fff; border-color: var(--shu); }
h2, h3 { font-family: "Palatino Linotype", Palatino, "Book Antiqua", serif; text-wrap: balance; }
h2 { font-size: 25px; margin: 0 0 4px; font-weight: 500; }
.intro { color: var(--ink-soft); font-size: 14.5px; margin: 0 0 20px; max-width: 80ch; }
a { color: var(--shu); }

/* ---------- día ---------- */
.day { margin-top: 22px; scroll-margin-top: 54px; }
.day-head { display: flex; align-items: baseline; gap: 12px; flex-wrap: wrap; border-bottom: 2px solid var(--ink); padding-bottom: 5px; }
.day-head h3 { margin: 0; font-size: 17.5px; font-weight: 600; }
.day-head .note { color: var(--ink-soft); font-size: 13.5px; font-style: italic; }
.day-head .ancla { margin-left: auto; font-size: 11px; font-weight: 700; letter-spacing: .1em; text-transform: uppercase; color: var(--gold); border: 1px solid var(--gold); border-radius: 999px; padding: 2px 10px; white-space: nowrap; }

/* ---------- pasos (una fila por hora) ---------- */
.steps { margin: 6px 0 0; padding: 0; list-style: none; }
/* solo las filas directas: los li de .fork y .plan-grid anidados NO son filas */
.steps > li { display: grid; grid-template-columns: 64px minmax(0, 1fr); gap: 12px; padding: 8px 0; border-bottom: 1px solid var(--line); font-size: 14px; scroll-margin-top: 58px; }
.steps > li.flash { animation: row-flash 1.8s ease-out 1; }
@keyframes row-flash { 0%, 55% { background: var(--shu-soft); } 100% { background: transparent; } }
/* pasos solo-mapa: presentes en el DOM (proyección 1:1 del YAML), no se ven */
.steps li.hidden-summary { display: none; }
.title .icon { font-style: normal; }
.steps .time { color: var(--ink-soft); font-variant-numeric: tabular-nums; font-size: 12px; padding-top: 2px; white-space: nowrap; letter-spacing: .06em; font-weight: 600; }
.steps .time.fixed { color: var(--shu); }
.steps b { font-weight: 600; }
.steps .transit { color: var(--ink-soft); }

/* ---------- options: tiers de comida Y planes en paralelo ----------
   Mismo markup (ul.options > li), como en el YAML son la misma clave.
   Un li CON sub-.steps (:has) es un plan-tarjeta; sin ellos, un tier-cajita. */
.options { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 8px; margin: 6px 0 0; padding: 0; list-style: none; }
/* angosto: carrusel horizontal (touch + arrastre de mouse), nunca apilar */
@media (max-width: 900px) {
  .options, .options:has(> li > .steps) { display: flex; overflow-x: auto; scroll-snap-type: x proximity; -webkit-overflow-scrolling: touch; scrollbar-width: none; cursor: grab; }
  .options::-webkit-scrollbar { display: none; }
  .options > li { flex: 0 0 auto; min-width: 64%; max-width: 85%; scroll-snap-align: center; }
  .options > li:has(> .steps) { min-width: 86%; max-width: 86%; }
}
.options > li { font-size: 13px; border-radius: 4px; padding: 6px 10px; }
.options > li > b:first-child { font-size: 11px; letter-spacing: .1em; text-transform: uppercase; display: block; }
/* tiers hoja: color por tier; cualquier otro tier (🏮 barrio) = neutro punteado */
.options > li[data-tier] { background: var(--paper-2); border: 1px dashed var(--line); }
.options > li[data-tier] > b:first-child { color: var(--ink-soft); }
.options > li[data-tier="Take"] { background: var(--matcha-soft); border: none; }
.options > li[data-tier="Take"] > b:first-child { color: var(--matcha); }
.options > li[data-tier="Ai"] { background: var(--ai-soft); border: none; }
.options > li[data-tier="Ai"] > b:first-child { color: var(--ai); }
.options > li[data-tier="Shu"] { background: var(--shu-soft); border: none; }
.options > li[data-tier="Shu"] > b:first-child { color: var(--shu); }
/* planes anidados: tarjetas grandes, acento por posición */
.options:has(> li > .steps) { grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 12px; margin-top: 8px; }
.options > li:has(> .steps) { font-size: inherit; border: 1px solid var(--line); border-radius: 8px; padding: 6px 10px 8px; }
.options > li:has(> .steps) > b:first-child { font-size: 13.5px; letter-spacing: 0; text-transform: none; border-bottom: 1px solid var(--line); padding-bottom: 4px; margin-bottom: 2px; }
.options > li:has(> .steps):nth-child(1) { background: light-dark(#f4eefa, #2a2233); }
.options > li:has(> .steps):nth-child(1) b { color: light-dark(#7b4fa6, #c9a9e6); }
.options > li:has(> .steps):nth-child(2) { background: light-dark(#fff6df, #2e2712); }
.options > li:has(> .steps):nth-child(2) b { color: light-dark(#a1750a, #e0c072); }
.options > li:has(> .steps):nth-child(n+3) { background: light-dark(#fdeef3, #301b24); }
.options > li:has(> .steps):nth-child(n+3) b { color: light-dark(#c2537c, #e79bbb); }
.options .steps > li { grid-template-columns: 52px minmax(0, 1fr); font-size: 13px; padding: 4px 0; }

/* ---------- links a modal + chips de línea ---------- */
.modal-link { color: inherit; text-decoration: underline dotted; text-underline-offset: 2px; cursor: pointer; }
.modal-link:hover { color: var(--shu); }
.line-chip { display: inline-block; min-width: 15px; height: 15px; border-radius: 50%; background: var(--lc); color: #fff; font-size: 10px; font-weight: 800; text-align: center; line-height: 15px; margin-right: 3px; font-style: normal; vertical-align: -2px; padding: 0 2px; }
.line-chip.dot { width: 11px; min-width: 11px; height: 11px; vertical-align: -1px; padding: 0; }

/* ---------- modales (contenido) ---------- */
.modal h3 { margin: 0 0 8px; font-size: 18px; }
.modal .h3-range { font-weight: 400; color: var(--ink-soft); }
.modal img { max-width: 100%; border-radius: 6px; margin: 0 0 10px; display: block; }
.modal p { margin: 0 0 8px; font-size: 14px; }
.modal-note { color: var(--ink-soft); font-size: 13px; }
.modal-note .src-tag { opacity: .55; font-size: 11px; }
.intro .red { color: var(--shu); }
.modal-btn { display: inline-block; margin-top: 4px; border: 1px solid var(--line); background: var(--paper-2); color: var(--ink); border-radius: 6px; padding: 6px 14px; font: 600 13px "Segoe UI", system-ui, sans-serif; text-decoration: none; }

/* ---------- modal de línea (banner, frecuencia, ride, estaciones, frase) ---------- */
.line-banner { background: var(--lc); color: #fff; border-radius: 10px; padding: 14px 12px; text-align: center; margin-bottom: 12px; }
.line-banner .jp { font-size: 26px; font-weight: 700; line-height: 1.2; }
.badge-row { margin-top: 8px; }
.badge { display: inline-block; background: #fff; color: var(--lc); border-radius: 50%; min-width: 30px; height: 30px; line-height: 30px; font-weight: 800; font-size: 15px; padding: 0 3px; }
.modal .freq { margin: -4px 0 12px; text-align: center; color: var(--ink-soft); font-size: 13px; }
.modal .freq.has-src { margin-bottom: 2px; }
.freq-src { text-align: center; margin: 0 0 12px; }
.freq-src a { color: var(--ink-soft); opacity: .7; font-size: 11px; }
.ride { display: flex; justify-content: space-between; gap: 8px; background: var(--paper-2); border-radius: 8px; padding: 8px 12px; margin: 0 0 12px; font-size: 13px; }
.ride .arrow { align-self: center; color: var(--ink-soft); }
.ride .arr { text-align: right; }
.ride .stn { color: var(--ink-soft); }
.modal .platform { margin: 0 0 8px; }
.platform .sign { font-size: 17px; }
.modal .reverse { margin: 0 0 10px; }
.stations { border-left: 3px solid var(--lc); padding-left: 10px; margin: 0 0 12px; }
.station { padding: 3px 0; }
.station .romaji { color: var(--ink-soft); font-size: 12px; }
.station-code { display: inline-block; min-width: 26px; border-radius: 9px; background: var(--lc); color: #fff; font-size: 10px; font-weight: 800; text-align: center; line-height: 15px; height: 15px; margin-right: 3px; vertical-align: -2px; padding: 0 2px; }
.phrase { background: var(--paper-2); border-radius: 10px; padding: 10px 12px; margin: 0 0 12px; }
.phrase .jp { font-size: 19px; line-height: 1.6; }
.phrase .romaji { color: var(--ink-soft); font-size: 13px; margin-top: 4px; }
.phrase .gloss { font-size: 12px; margin-top: 4px; }

/* ---------- overlay del modal (dialog nativo) ---------- */
dialog.overlay { border: none; background: var(--card); color: var(--ink); border-top: 5px solid var(--shu); border-radius: 8px; width: min(520px, calc(100vw - 32px)); max-height: 85vh; overflow-y: auto; box-shadow: 0 12px 50px rgba(0,0,0,.35); padding: 22px 24px; }
dialog.overlay::backdrop { background: rgba(0,0,0,.45); }
.overlay-close { position: absolute; top: 8px; right: 12px; border: none; background: transparent; font-size: 24px; line-height: 1; color: var(--ink-soft); cursor: pointer; }
"""

SCRIPT = """(function () {
  'use strict';
  var overlay = document.getElementById('overlay');
  var body = document.getElementById('overlay-body');
  var store = document.getElementById('modal-store').content;
  var currentRow = '';   // fila desde la que se abrió el modal visible

  // el modal es compartible: el hash guarda tarjeta + fila (#m-clave@fila)
  function setHash(h) {
    history.replaceState(null, '', h ? '#' + h : location.pathname + location.search);
  }
  function openModal(id, rowId) {
    var src = store.getElementById(id);
    if (!src) return;
    body.innerHTML = src.outerHTML;
    if (rowId) currentRow = rowId;
    setHash(id + (currentRow ? '@' + currentRow : ''));
    if (!overlay.open) overlay.showModal();   // Escape y focus los maneja el <dialog>
  }
  overlay.addEventListener('close', function () {   // cubre ×, backdrop y Escape
    body.innerHTML = '';
    currentRow = '';
    setHash('');
  });

  document.addEventListener('click', function (e) {
    var link = e.target.closest('.modal-link');
    if (link) {
      var href = link.getAttribute('href') || '';
      if (href.indexOf('#m-') === 0) {
        e.preventDefault();
        var row = link.closest('li[id]');   // dentro del dialog no hay fila: conserva la actual
        openModal('m-' + href.slice(3), row ? row.id : '');
        return;
      }
    }
    if (e.target === overlay || e.target.closest('.overlay-close')) overlay.close();
  });

  // llegada con #m-clave[@fila]: scroll a la fila (con flash) y abrir la tarjeta
  function applyHash() {
    var m = /^#(m-[^@]+)(?:@(.+))?$/.exec(location.hash);
    if (!m) return;
    var row = m[2] ? document.getElementById(m[2]) : null;
    if (!row) {
      var firstLink = document.querySelector('.steps a[href="#' + m[1] + '"]');
      row = firstLink && firstLink.closest('li[id]');
    }
    if (row) {
      row.scrollIntoView({ block: 'center' });
      row.classList.add('flash');
      setTimeout(function () { row.classList.remove('flash'); }, 2000);
    }
    openModal(m[1], row ? row.id : '');
  }
  applyHash();
  window.addEventListener('hashchange', applyHash);   // también al navegar solo el hash

  // fotos rotas: ocultarlas (reemplaza los onerror inline del pipeline viejo)
  document.addEventListener('error', function (e) {
    if (e.target.tagName === 'IMG' && e.target.closest('.modal')) {
      e.target.style.display = 'none';
    }
  }, true);

  // barra de días: resaltar el día visible
  var nav = document.querySelector('.day-nav');
  if (nav && 'IntersectionObserver' in window) {
    var links = {};
    nav.querySelectorAll('a[href^="#d-"]').forEach(function (a) {
      links[a.getAttribute('href').slice(1)] = a;
    });
    var days = Array.prototype.slice.call(document.querySelectorAll('section.day'));
    var visible = {};
    var observer = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) { visible[en.target.id] = en.isIntersecting; });
      var current = null;
      days.forEach(function (d) { if (!current && visible[d.id]) current = d.id; });
      if (!current) return;    // arriba del día 1: conservar el resaltado previo
      days.forEach(function (d) {
        if (links[d.id]) links[d.id].classList.toggle('on', d.id === current);
      });
      if (current && links[current].scrollIntoView) {
        links[current].scrollIntoView({ block: 'nearest', inline: 'nearest' });
      }
    }, { rootMargin: '-50px 0px -55% 0px' });
    days.forEach(function (d) { observer.observe(d); });
  }

  // carruseles (.options angostas, barra de días): arrastre lateral con mouse;
  // el touch ya scrollea nativo. Un arrastre real suprime el click que suelta.
  var drag = null, dragged = false;
  document.addEventListener('pointerdown', function (e) {
    if (e.pointerType !== 'mouse' || e.button !== 0) return;
    var el = e.target.closest('.options, .day-nav');
    if (!el || el.scrollWidth <= el.clientWidth + 4) return;
    drag = { el: el, x: e.clientX, left: el.scrollLeft };
    dragged = false;
  });
  document.addEventListener('pointermove', function (e) {
    if (!drag) return;
    var dx = e.clientX - drag.x;
    if (Math.abs(dx) > 5) dragged = true;
    if (dragged) {
      drag.el.scrollLeft = drag.left - dx;
      e.preventDefault();
    }
  });
  document.addEventListener('pointerup', function () { drag = null; });
  document.addEventListener('click', function (e) {
    if (dragged) { e.preventDefault(); e.stopPropagation(); dragged = false; }
  }, true);
})();"""

INTRO = """Física de 10 personas, ya sumada en cada hora: <b>+15 min de reagrupe en cada movimiento</b> (alguien siempre está en el baño), <b>ninguna comida sentada dura menos de 1 h</b> (con 10 son 1 h 15 reales), y cada conmutación viene con su línea, estación y transbordo — nivel Keep de Juan, y un poco más. Días de ~12 horas <b>con holgura a propósito</b>: si un lugar les gusta, se quedan — los bloques de tarde son los que se sacrifican, nunca el ancla de la mañana. Las horas en <b class="red">rojo</b> son las únicas fijas (vuelos, aperturas, reservas, el tour); todo lo demás se estira o se cae sin culpa. Kioto madruga a las 6:00 porque ahí el silencio se compra con sueño; Tokio abre tarde y ahí se descansa. Regla de los 10: mañana juntos en el ancla, tarde en subgrupos, cena juntos si sale natural. <b>Comidas:</b> las opciones son de donde ESTÁN a esa hora; las recomendaciones grandes (★) solo aparecen en noches libres, cuando sí pueden moverse a ellas; cada columna trae 3 opciones clickeables (toca cualquier lugar para ver qué es, quién lo recomienda y su Google Maps) y el orden de precio es fijo — Take barato, Ai medio, Shu caro: juntas son el rango del momento; los barrios 🏮 son la opción de llegar y escoger ahí, y los huecos libres de mediodía sirven para peregrinar a un lugar específico. <b>Desayunos:</b> 🏨 = incluido en el hotel · ☕ = comprarlo cerca · 🏪 = konbini precomprado la noche anterior (los madrugones no perdonan el buffet)."""

refs = RefLog()
days_html = "\n\n".join(render_day(d, refs, i + 1) for i, d in enumerate(DAYS))
modals_html = "\n".join(render_modal(k) for k in refs.order)


def nav_link(day, num):
    label = str(day.get("titulo", "")).split("·")[0].strip() or f"día {num}"
    return f'<a href="#d{num}">{html.escape(label)}</a>'


nav_html = "".join(nav_link(d, i + 1) for i, d in enumerate(DAYS))

page = f"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="description" content="Itinerario día por día del viaje familiar a Japón — 4 al 18 de octubre de 2026: Osaka, Kioto y Tokio, hora por hora.">
<meta name="theme-color" content="#b23a2a">
<title>Japón 2026 · itinerario</title>
<link rel="icon" href="data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22><text y=%22.9em%22 font-size=%2290%22>⛩️</text></svg>">
<link rel="stylesheet" href="itinerario.css">
</head>
<body>
<div class="wrap">
<nav class="day-nav" aria-label="Días">{nav_html}</nav>
<section>
  <h2>El marco, día por día — hora por hora</h2>
  <p class="intro">{INTRO}</p>

{days_html}
</section>
<template id="modal-store">
{modals_html}
</template>
<dialog class="overlay" id="overlay"><button class="overlay-close" type="button" aria-label="Cerrar">×</button><div id="overlay-body"></div></dialog>
<script src="itinerario.js"></script>
</div>
</body>
</html>
"""

with open(OUT, "w", encoding="utf-8") as f:
    f.write(page)
with open(OUT_CSS, "w", encoding="utf-8") as f:
    f.write(CSS.lstrip())
with open(OUT_JS, "w", encoding="utf-8") as f:
    f.write(SCRIPT + "\n")
print(f"itinerario.html · {len(DAYS)} días · {len(refs.order)} modales · {len(page) // 1024} KB"
      f" · itinerario.css {len(CSS) // 1024} KB · itinerario.js {len(SCRIPT) // 1024} KB")
if FIXED_TITLES:
    print(f"títulos normalizados (asteriscos sueltos del pipeline viejo): {len(FIXED_TITLES)}")
    for t in FIXED_TITLES:
        print("  ·", t[:80])

# el HTML debe ser proyección 1:1 del YAML — comprobarlo en cada build
import subprocess
r = subprocess.run([sys.executable, os.path.join(SD, "verify_roundtrip.py")],
                   capture_output=True, text=True, encoding="utf-8")
print(r.stdout.strip() or r.stderr.strip())
