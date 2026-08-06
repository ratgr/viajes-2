# -*- coding: utf-8 -*-
"""verify_roundtrip.py — comprueba que itinerario.html es una proyección 1:1
de viaje.yaml: parsea el HTML generado, reconstruye días/pasos (invirtiendo el
markdown: <b>↔**, <i>↔*, <br>↔\\n, a.modal-link↔@[alt](clave)) y los compara
contra el YAML campo por campo.

Alcance: días (titulo/note/ancla/date) y pasos (location/transit/mode/time/
fixed/duration/title/note/solo_seleccion/hidden-summary/options anidadas).
Fuera de alcance (solo-mapa o derivado): coords/color de transits, y los
bloques data-derived de los modales (horario, frase, SUBIR/BAJAR, icono).
"""
import os
import re
import sys
from html.parser import HTMLParser

import yaml

from common import resolve_trip, trip_paths

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
VOID = {"br", "img", "meta", "link", "input", "hr"}


class Node:
    def __init__(self, tag, attrs):
        self.tag = tag
        self.attrs = dict(attrs)
        self.children = []

    def cls(self):
        return (self.attrs.get("class") or "").split()


class TreeBuilder(HTMLParser):
    def __init__(self):
        super().__init__()
        self.root = Node("root", [])
        self.stack = [self.root]

    def handle_starttag(self, tag, attrs):
        n = Node(tag, attrs)
        self.stack[-1].children.append(n)
        if tag not in VOID:
            self.stack.append(n)

    def handle_startendtag(self, tag, attrs):
        self.stack[-1].children.append(Node(tag, attrs))

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i].tag == tag:
                del self.stack[i:]
                return

    def handle_data(self, data):
        if data:
            self.stack[-1].children.append(data)


def nodes(children, tag=None, klass=None):
    for c in children:
        if isinstance(c, Node) and (tag is None or c.tag == tag) and (klass is None or klass in c.cls()):
            yield c


def first(children, tag=None, klass=None):
    return next(nodes(children, tag, klass), None)


def text_of(node):
    out = []
    for c in node.children:
        out.append(c if isinstance(c, str) else text_of(c))
    return "".join(out)


def text_plain(node):
    """texto sin lo derivado ni separadores presentacionales (.sep)."""
    out = []
    for c in node.children:
        if isinstance(c, str):
            out.append(c)
        elif "data-derived" in c.attrs or "sep" in c.cls():
            continue
        else:
            out.append(text_plain(c))
    return "".join(out)


def to_md(children):
    """HTML renderizado → texto fuente (markdown + @[refs]); salta lo derivado."""
    out = []
    for c in children:
        if isinstance(c, str):
            out.append(c)
        elif "data-derived" in c.attrs:
            continue
        elif c.tag == "br":
            out.append("\n")
        elif c.tag == "i" and "line-chip" in c.cls():
            continue
        elif c.tag == "a" and "modal-link" in c.cls():
            key = (c.attrs.get("href") or "")[3:]     # '#m-xxx' → 'xxx'
            out.append(f"@[{to_md(c.children)}]({key})")
        elif c.tag == "b":
            out.append("**" + to_md(c.children) + "**")
        elif c.tag == "i":
            out.append("*" + to_md(c.children) + "*")
        else:
            out.append(to_md(c.children))
    return "".join(out)


# ---------------------------------------------------------------- HTML → pasos
def parse_step(li):
    d = {}
    if "data-location" in li.attrs:
        d["location"] = li.attrs["data-location"]
    if "data-transit" in li.attrs:
        d["transit"] = li.attrs["data-transit"]
    if "data-mode" in li.attrs:
        d["mode"] = li.attrs["data-mode"]
    if "data-solo-seleccion" in li.attrs:
        d["solo_seleccion"] = True
    if "hidden-summary" in li.cls():
        d["hidden-summary"] = True
    t = first(li.children, "time")
    if t is not None:
        tt = text_plain(t).strip()      # sin la hora-fin derivada
        if tt:
            d["time"] = tt
        if "fixed" in t.cls():
            d["fixed"] = True
    body = first(li.children, "div", "body")
    inner = body.children if body else []
    wrap = first(inner, "span", "transit")
    if wrap is not None:
        inner = wrap.children + [c for c in inner if c is not wrap]
    for c in nodes(inner):
        if "data-derived" in c.attrs:      # duración inferida etc.: no es dato
            continue
        if c.tag == "b" and "title" in c.cls():
            d["title"] = to_md(c.children).strip()
        elif c.tag == "span" and "duration" in c.cls():
            d["duration"] = text_plain(c).strip()
        elif c.tag == "span" and "note" in c.cls():
            d["note"] = re.sub(r"^\s*-\s", "", to_md(c.children)).strip()
        elif c.tag == "ul" and "options" in c.cls():
            d["options"] = [parse_opt(o) for o in nodes(c.children, "li")]
    return d


def parse_opt(li):
    sub = first(li.children, "ul", "steps")
    b = first(li.children, "b")
    title = to_md(b.children).strip() if b else ""
    if sub is not None:
        return {"title": title, "steps": [parse_step(x) for x in nodes(sub.children, "li")]}
    opts, last = [], None
    for c in nodes(li.children):
        if c.tag == "a" and "modal-link" in c.cls():
            last = {"location": (c.attrs.get("href") or "")[3:]}
            opts.append(last)
        elif c.tag == "span" and "precio" in c.cls() and last is not None:
            last["precio"] = text_of(c).strip()
    return {"title": title, "options": opts}


def parse_days(html_text):
    tb = TreeBuilder()
    tb.feed(html_text)

    def walk(n, out):
        for c in n.children:
            if isinstance(c, Node):
                if c.tag == "section" and "day" in c.cls():
                    out.append(c)
                walk(c, out)

    sections, days = [], []
    walk(tb.root, sections)
    for s in sections:
        head = first(s.children, "header")
        h3 = first(head.children, "h3")
        note = first(head.children, "span", "note")
        ancla = first(head.children, "span", "ancla")
        steps_ul = first(s.children, "ul", "steps")
        days.append({
            "titulo": text_of(h3).strip() if h3 else "",
            "note": text_of(note).strip() if note else "",
            "ancla": re.sub(r"^Ancla:\s*", "", text_of(ancla).strip()) if ancla else "",
            "date": s.attrs.get("data-fecha", ""),
            "steps": [parse_step(li) for li in nodes(steps_ul.children, "li")],
        })
    return days


# ---------------------------------------------------------------- YAML → pasos
SKIP_DUR = (None, 0, "0")


def norm_step(s):
    d = {}
    if s.get("location"):
        d["location"] = str(s["location"])
    if s.get("transit"):
        d["transit"] = str(s["transit"])
    if s.get("mode"):
        d["mode"] = str(s["mode"])
    if s.get("solo_seleccion"):
        d["solo_seleccion"] = True
    if s.get("hidden-summary"):
        d["hidden-summary"] = True
    if s.get("time") not in (None, ""):
        d["time"] = str(s["time"])
    if s.get("fixed"):
        d["fixed"] = True
    if s.get("duration") not in SKIP_DUR:
        d["duration"] = str(s["duration"]).strip()
    if s.get("title"):
        d["title"] = str(s["title"]).replace("*", "").strip()
    if s.get("note"):
        d["note"] = str(s["note"]).strip()
    if s.get("options"):
        d["options"] = [norm_opt(o) for o in s["options"] if isinstance(o, dict)]
    return d


def norm_opt(o):
    title = str(o.get("title", "")).replace("*", "").strip()
    if "steps" in o:
        return {"title": title, "steps": [norm_step(x) for x in o["steps"] if isinstance(x, dict)]}
    opts = []
    for x in o.get("options", []):
        e = {"location": str(x.get("location") or "")}
        if x.get("precio"):
            e["precio"] = str(x["precio"]).strip()
        opts.append(e)
    return {"title": title, "options": opts}


def norm_day(day):
    date = day.get("date")
    return {
        "titulo": str(day.get("titulo", "")).strip(),
        "note": str(day.get("note", "")).strip(),
        "ancla": str(day.get("ancla", "")).strip(),
        "date": date.isoformat() if hasattr(date, "isoformat") else str(date),
        "steps": [norm_step(s) for s in day.get("steps", []) if isinstance(s, dict)],
    }


# ---------------------------------------------------------------- comparación
def diff(a, b, path, out):
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b)):
            diff(a.get(k), b.get(k), f"{path}.{k}", out)
    elif isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            out.append(f"{path}: {len(a)} vs {len(b)} elementos")
        for i, (x, y) in enumerate(zip(a, b)):
            diff(x, y, f"{path}[{i}]", out)
    elif a != b:
        out.append(f"{path}: {a!r} != {b!r}")


def main():
    trip = resolve_trip(sys.argv)
    page = sys.argv[2] if len(sys.argv) > 2 else "itinerario.html"
    src_dir, pages_dir, _ = trip_paths(trip)
    Y = yaml.safe_load(open(os.path.join(src_dir, "viaje.yaml"), encoding="utf-8"))
    html_days = parse_days(open(os.path.join(pages_dir, page), encoding="utf-8").read())
    yaml_days = [norm_day(d) for d in Y.get("days", [])]
    problems = []
    if len(html_days) != len(yaml_days):
        problems.append(f"días: {len(html_days)} en HTML vs {len(yaml_days)} en YAML")
    for i, (h, y) in enumerate(zip(html_days, yaml_days)):
        diff(y, h, f"d{i + 1}", problems)
    total = sum(len(d["steps"]) for d in yaml_days)
    if problems:
        print(f"round-trip: {len(problems)} diferencias ({total} pasos):")
        for p in problems[:40]:
            print("  ·", p)
        if len(problems) > 40:
            print(f"  … y {len(problems) - 40} más")
        return 1
    print(f"round-trip OK: {len(yaml_days)} días · {total} pasos — HTML ≡ YAML")
    return 0


if __name__ == "__main__":
    sys.exit(main())
