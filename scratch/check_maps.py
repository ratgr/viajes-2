# -*- coding: utf-8 -*-
"""check_maps.py — verifica los links 'Abrir en Maps' de viaje.yaml vía el puente de la extensión.

Recorre cada place con maps+gps (primero los usados como location en days, luego el resto),
navega la pestaña QA (setTabUrl), espera, lee h1/title del panel de Google Maps y
guarda una línea JSON por place en maps_results.jsonl (en el dir de la cola).

Uso: python check_maps.py <queue-dir> <viaje.yaml> [max_places]
"""
import json, os, sys, time, unicodedata

QUEUE = sys.argv[1]
YAML_PATH = sys.argv[2]
MAX_PLACES = int(sys.argv[3]) if len(sys.argv) > 3 else 0

CMD = os.path.join(QUEUE, "bridge-commands.jsonl")
RES = os.path.join(QUEUE, "bridge-results.jsonl")
OUT = os.path.join(QUEUE, "maps_results.jsonl")
SEQ = os.path.join(QUEUE, "seq.txt")

sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def next_id():
    n = 1
    if os.path.exists(SEQ):
        try:
            n = int(open(SEQ).read().strip()) + 1
        except Exception:
            n = int(time.time()) % 100000
    open(SEQ, "w").write(str(n))
    return n


def rpc(method, params, timeout=45.0):
    n = next_id()
    offset = os.path.getsize(RES) if os.path.exists(RES) else 0
    with open(CMD, "a", encoding="utf-8") as f:
        f.write(json.dumps({"id": n, "method": method, "params": params, "timeout": timeout}) + "\n")
    deadline = time.time() + timeout + 10
    while time.time() < deadline:
        if os.path.exists(RES) and os.path.getsize(RES) > offset:
            with open(RES, encoding="utf-8") as f:
                f.seek(offset)
                lines = f.readlines()
            offset += sum(len(l.encode("utf-8")) for l in lines)
            for line in lines:
                try:
                    r = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if r.get("id") == n:
                    return r
        time.sleep(0.3)
    return {"id": n, "ok": False, "error": "timeout"}


def norm(s):
    if not s:
        return ""
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return s.lower().strip()


def main():
    import yaml
    d = yaml.safe_load(open(YAML_PATH, encoding="utf-8"))
    places = d["places"]

    day_locs = []
    for day in d["days"]:
        for st in day.get("steps", []):
            loc = st.get("location")
            if loc and loc not in day_locs:
                day_locs.append(loc)

    ordered = [k for k in day_locs if k in places]
    ordered += [k for k in places if k not in ordered]

    todo = [(k, places[k]) for k in ordered
            if isinstance(places[k], dict) and places[k].get("maps") and places[k].get("gps")]
    if MAX_PLACES:
        todo = todo[:MAX_PLACES]

    done = set()
    if os.path.exists(OUT):
        for line in open(OUT, encoding="utf-8"):
            try:
                done.add(json.loads(line)["key"])
            except Exception:
                pass

    print(f"{len(todo)} places to check, {len(done)} already done", flush=True)
    captcha_streak = 0

    for i, (key, p) in enumerate(todo):
        if key in done:
            continue
        url = p["maps"]
        rec = {"key": key, "name": p.get("name"), "gps": p.get("gps"), "is_day_loc": key in day_locs}
        r = rpc("setTabUrl", [url], 40)
        if not r.get("ok"):
            rec["status"] = "nav_error"
            rec["error"] = str(r.get("error"))[:200]
            with open(OUT, "a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            time.sleep(4)
            continue
        time.sleep(5.0)
        h1 = rpc("getText", ["h1"], 30)
        title = rpc("getText", ["title"], 20)
        h1v = h1.get("result") if h1.get("ok") else None
        tv = title.get("result") if title.get("ok") else None
        if isinstance(h1v, dict):
            h1v = h1v.get("text") or str(h1v)
        if isinstance(tv, dict):
            tv = tv.get("text") or str(tv)
        # si h1 vacío, reintenta una vez tras 4 s más (maps lento)
        if not h1v:
            time.sleep(4.0)
            h1 = rpc("getText", ["h1"], 30)
            h1v = h1.get("result") if h1.get("ok") else None
            if isinstance(h1v, dict):
                h1v = h1v.get("text") or str(h1v)
        rec["h1"] = h1v
        rec["title"] = tv
        panel = rpc("getText", ['[role="main"]'], 25)
        pv = panel.get("result") if panel.get("ok") else None
        if isinstance(pv, dict):
            pv = pv.get("text") or str(pv)
        rec["panel"] = (pv or "")[:400]

        low = (norm(h1v) + " " + norm(tv))
        if "sorry" in (tv or "").lower() or "unusual traffic" in low or "captcha" in low:
            captcha_streak += 1
            rec["status"] = "captcha"
        else:
            captcha_streak = 0
            nn = norm(rec.get("name") or "")
            if h1v and nn and (nn in norm(h1v) or norm(h1v) in nn):
                rec["status"] = "ok_exact"
            elif not h1v or "resultados" in norm(h1v) or "results" in norm(h1v):
                rec["status"] = "review"  # panel sin nombre claro -> revisar título
            else:
                rec["status"] = "review"
        with open(OUT, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        print(f"[{i+1}/{len(todo)}] {key}: {rec['status']} h1={h1v!r}", flush=True)
        if captcha_streak >= 3:
            print("CAPTCHA persistente — deteniendo muestreo", flush=True)
            break
        time.sleep(3.5)

    print("DONE", flush=True)


if __name__ == "__main__":
    main()
