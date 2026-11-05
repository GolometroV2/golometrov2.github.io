#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ALINEACIONES PROBABLES DE FUTBOL FANTASY

Lee las alineaciones probables de futbolfantasy.com (su robots.txt permite el acceso) y guarda
alineaciones.json con la probabilidad de ser titular de cada jugador de Mister en su proximo partido.
Se usa un unico acceso a la lista de partidos y uno por partido, con pausa entre peticiones.

  alineaciones.json            -> probabilidades actuales: jugadores[idMister][jornada] = {p, conf, les, ff}
  alineaciones_historial.json  -> ultima probabilidad antes de cada partido (para calibrar el modelo)

Uso:  python alineaciones_ff.py            (descarga de internet)
      python alineaciones_ff.py --prueba   (solo lista lo que haria, sin escribir)
"""
import json
import os
import re
import sys
import time
import unicodedata
from datetime import datetime, timezone
from difflib import SequenceMatcher

import requests

CARPETA = os.path.dirname(os.path.abspath(__file__))
BASE = "https://www.futbolfantasy.com"
UA = "Mozilla/5.0 (compatible; GolometroBot/1.0; liga privada de uso personal)"
PAUSA = 2.0
JORNADAS_ADELANTE = 2          # jornada en curso (o siguiente) y la que viene
P_TITULAR_CONFIRMADO = 0.97    # alineacion ya confirmada: titular
P_SUPLENTE_CONFIRMADO = 0.15   # alineacion confirmada: en el banquillo (puede entrar)

ALIAS_EQUIPOS = {              # nombre de FF -> palabras que identifican al equipo en Mister
    "athletic": "athletic", "real-sociedad": "real sociedad", "deportivo": "deportivo", "osasuna": "osasuna",
    "elche": "elche", "valencia": "valencia", "barcelona": "barcelona", "alaves": "alaves", "getafe": "getafe",
    "sevilla": "sevilla", "levante": "levante", "atletico": "atletico", "rayo": "rayo", "celta": "celta",
    "betis": "betis", "rayo-vallecano": "rayo", "malaga": "malaga", "racing": "racing", "real-madrid": "real madrid",
    "villarreal": "villarreal", "espanyol": "espanyol",
}


def norm(s):
    s = unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"\([^)]*\)", " ", s)
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def cargar(nombre, defecto):
    try:
        with open(os.path.join(CARPETA, nombre), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return defecto


def descargar(url, sesion):
    for i in range(3):
        try:
            r = sesion.get(url, timeout=40)
            if r.status_code == 200 and len(r.text) > 20000:
                return r.text
            print(f"  aviso: {url} -> HTTP {r.status_code}, {len(r.text)} bytes")
        except requests.RequestException as e:
            print(f"  aviso: {url} -> {e}")
        time.sleep(5 * (i + 1))
    return None


def equipos_mister(cal):
    """{idEquipo: nombre normalizado}"""
    eq = {}
    for g in cal.get("games", []):
        eq[g["home"]] = norm(g.get("homeName"))
        eq[g["away"]] = norm(g.get("awayName"))
    return eq


def equipo_de_ff(slug, eq):
    clave = ALIAS_EQUIPOS.get(slug, slug.replace("-", " "))
    cand = [i for i, n in eq.items() if clave in n or n in clave]
    if len(cand) > 1:                                  # p. ej. «real madrid» frente a «madrid»
        cand = [i for i in cand if eq[i] == clave] or cand[:1]
    return cand[0] if cand else None


def partir_slug(resto, slugs):
    """'real-sociedad-rayo' -> ('real-sociedad', 'rayo') usando los equipos conocidos."""
    p = resto.split("-")
    for k in range(1, len(p)):
        a, b = "-".join(p[:k]), "-".join(p[k:])
        if a in slugs and b in slugs:
            return a, b
    return None


def leer_partido(html):
    """Devuelve la lista de jugadores del partido con su probabilidad de ser titular."""
    jug = []
    marcas = list(re.finditer(r'<div class="jugador_(\d+)[^"]*"[^>]*data-onceFF="(titular|suplente)"', html))
    for k, m in enumerate(marcas):
        fin = marcas[k + 1].start() if k + 1 < len(marcas) else m.start() + 12000
        seg = html[m.start():min(fin, m.start() + 12000)]
        pb = re.search(r'data-probabilidad="([^"]*)"', seg)
        hr = re.search(r'/jugadores/([^"/]+)/', seg)
        nom = re.search(r'class="truncate-name[^"]*">([^<]+)<', seg)
        les = re.search(r'data-lesion="(-?\d+)"', seg)
        if not pb or not hr:
            continue
        raw = pb.group(1).strip()
        if raw.endswith("%"):
            try:
                p, conf = float(raw[:-1]) / 100.0, False
            except ValueError:
                continue
        else:                                           # alineacion confirmada: «Titular» / «Suplente»
            p, conf = (P_TITULAR_CONFIRMADO if raw.lower().startswith("titular") else P_SUPLENTE_CONFIRMADO), True
        jug.append({"ffId": m.group(1), "slug": hr.group(1), "corto": (nom.group(1).strip() if nom else ""),
                    "p": round(p, 3), "conf": conf, "les": int(les.group(1)) if les else -1,
                    "once": m.group(2)})
    return jug


def puntuar(j, nombre_norm):
    """Parecido entre un jugador de FF y un nombre de Mister (0 a 1)."""
    slug = re.sub(r"-\d+$", "", j["slug"]).replace("-", " ")
    cort = norm(j["corto"])
    mt = nombre_norm.split()
    s = SequenceMatcher(None, slug, nombre_norm).ratio()
    if cort and cort in nombre_norm:
        s = max(s, 0.85 + 0.1 * min(len(cort), 10) / 10)
    st = [t for t in slug.split() if len(t) > 2]
    if st and all(any(x == t or (len(t) > 3 and (x.startswith(t) or t.startswith(x))) for x in mt) for t in st):
        s = max(s, 0.95)
    # nombre corto de Mister (p. ej. «Pedri», «Koke», «Isco») contenido en el de FF
    mt3 = [x for x in mt if len(x) > 2]
    if mt3 and len(mt3) <= 2 and all(x in slug.split() for x in mt3):
        s = max(s, 0.9)
    # solo el apellido (ultima palabra) coincide
    if mt and slug.split() and slug.split()[-1] == mt[-1]:
        s = max(s, 0.8)
    return s


def emparejar(jugs_ff, candidatos):
    """candidatos: lista de jugadores de Mister. Devuelve ({idMister: jugadorFF}, [sin pareja])."""
    res, sin = {}, []
    usados = set()
    puntos = []
    for j in jugs_ff:
        for c in candidatos:
            puntos.append((puntuar(j, c["_n"]), j["ffId"], c["id"]))
    puntos.sort(reverse=True)
    por_ff = {j["ffId"]: j for j in jugs_ff}
    hecho = set()
    for s, f, c in puntos:
        if s < 0.72 or f in hecho or c in usados:
            continue
        res[c] = por_ff[f]
        hecho.add(f)
        usados.add(c)
    for j in jugs_ff:
        if j["ffId"] not in hecho:
            sin.append({"ff": j["slug"], "nombre": j["corto"], "p": j["p"]})
    return res, sin


# ---------- Analítica Fantasy (analiticafantasy.com; su robots.txt permite las páginas, no su /api/) ----------
AF_BASE = "https://www.analiticafantasy.com"
ALIAS_AF = {"atletico-madrid": "atletico", "deportivo-la-coruna": "deportivo", "racing-santander": "racing", "rayo-vallecano": "rayo",
            "real-betis": "betis", "celta-vigo": "celta", "athletic-club": "athletic"}


def leer_af(html):
    """Jugadores de un partido de Analítica Fantasy con su probabilidad de ser titular («chance»)."""
    trozos = re.findall(r'self\.__next_f\.push\(\[1,"(.*?)"\]\)</script>', html, re.S)
    datos = ""
    for c in trozos:
        try:
            datos += json.loads('"' + c + '"')
        except ValueError:
            pass
    vistos, jug = set(), []
    patron = r'"playerId":(\d+),"grid":(?:\d+|null),"chance":(\d+|null),.{0,400}?"esTitular":(true|false),"name":"([^"]*)","slug":"([^"]*)"'
    for m in re.finditer(patron, datos):
        pid, ch, tit, nom, slug = m.groups()
        if pid in vistos or ch == "null":
            continue
        vistos.add(pid)
        bloque = datos[m.end():m.end() + 700]
        sanc = '"isSanctioned":true' in bloque[:bloque.find('"predictedFantasyPoints"')] if '"predictedFantasyPoints"' in bloque else False
        p = 0.0 if sanc else int(ch) / 100.0
        jug.append({"ffId": "af" + pid, "slug": slug, "corto": nom, "p": round(p, 3), "tit": tit == "true"})
    return jug


def leer_analitica(s, pend, eq, por_equipo):
    """{idMister: {jornada: probabilidad}} con las alineaciones probables de Analítica Fantasy."""
    lista = descargar(f"{AF_BASE}/la-liga/alineaciones-probables", s)
    if not lista:
        print("No se pudo leer la lista de Analítica Fantasy.")
        return {}, 0
    partidos = dict(re.findall(r'href="/partido/(\d+)-([a-z0-9-]+)"', lista))
    claves = set(ALIAS_AF) | set(ALIAS_EQUIPOS)
    res, leidos = {}, 0
    for pid, resto in partidos.items():
        par = partir_slug(resto, claves)
        if not par:
            print(f"  AVISO Analítica: no reconozco los equipos de {resto}")
            continue
        a, b = (ALIAS_AF.get(x, x) for x in par)
        ha, hb = equipo_de_ff(a, eq), equipo_de_ff(b, eq)
        g = next((g for g in sorted(pend, key=lambda x: x.get("ts") or 0) if g["home"] == ha and g["away"] == hb), None)
        if not g:
            continue
        time.sleep(PAUSA)
        html = descargar(f"{AF_BASE}/partido/{pid}-{resto}", s)
        if not html:
            continue
        lst = leer_af(html)
        cands = por_equipo.get(g["home"], []) + por_equipo.get(g["away"], [])
        emp, _ = emparejar(lst, cands)
        for idm, j in emp.items():
            res.setdefault(idm, {})[str(g["gw"])] = {"p": j["p"], "tit": j["tit"]}
        leidos += 1
        print(f"  Analítica {resto} (J{g['gw']}): {len(lst)} jugadores, {len(emp)} emparejados")
    return res, leidos


def main():
    prueba = "--prueba" in sys.argv
    cal = cargar("calendario.json", {})
    jug = cargar("jugadores.json", {}).get("jugadores", [])
    if not cal.get("games") or not jug:
        print("Faltan calendario.json o jugadores.json")
        sys.exit(1)
    ahora = time.time()
    # jornadas que nos interesan: las abiertas (con partidos por jugar), las primeras N
    abiertas = sorted({g["gw"] for g in cal["games"] if g.get("status") != "played" and (g.get("ts") or 0) > ahora - 3 * 3600})
    objetivo = set(abiertas[:JORNADAS_ADELANTE])
    pend = [g for g in cal["games"] if g["gw"] in objetivo and g.get("status") != "played"]
    print(f"Jornadas {sorted(objetivo)} · partidos pendientes: {len(pend)}")
    eq = equipos_mister(cal)
    por_equipo = {}
    for p in jug:
        p["_n"] = norm(p["name"])
        por_equipo.setdefault(p["teamId"], []).append(p)

    s = requests.Session()
    s.headers["User-Agent"] = UA
    s.headers["Accept-Language"] = "es-ES,es;q=0.9"
    lista = descargar(f"{BASE}/laliga/posibles-alineaciones", s)
    if not lista:
        print("No se pudo leer la lista de partidos de Futbol Fantasy.")
        sys.exit(1)
    slugs = set(re.findall(r'/laliga/equipos/([a-z0-9-]+)', lista))
    slugs |= set(ALIAS_EQUIPOS)          # en las URLs de partidos algunos equipos van abreviados (p. ej. «rayo» y no «rayo-vallecano»)
    partidos = {}
    for pid, resto in re.findall(r'/partidos/(\d+)-([a-z0-9-]+)"', lista):
        par = partir_slug(resto, slugs)
        if par:
            partidos.setdefault(pid, par)
    print(f"Partidos en FF: {len(partidos)} · equipos: {len(slugs)}")

    # partido de FF -> partido de Mister
    asign = []
    for pid, (a, b) in partidos.items():
        ha, hb = equipo_de_ff(a, eq), equipo_de_ff(b, eq)
        if ha is None or hb is None:
            print(f"  AVISO sin equipo en Mister: {a} / {b}")
            continue
        g = next((g for g in sorted(pend, key=lambda x: x.get("ts") or 0) if g["home"] == ha and g["away"] == hb), None)
        if g:
            asign.append((pid, a, b, g))
    print(f"Partidos que se van a leer: {len(asign)}")
    if prueba:
        for pid, a, b, g in asign:
            print("  ", pid, a, b, "-> jornada", g["gw"])
        return

    out_j, sin_par, info = {}, [], []
    previo = cargar("alineaciones.json", {})
    for pid, a, b, g in asign:
        time.sleep(PAUSA)
        html = descargar(f"{BASE}/partidos/{pid}-{a}-{b}", s)
        if not html:
            continue
        lst = leer_partido(html)
        cands = por_equipo.get(g["home"], []) + por_equipo.get(g["away"], [])
        par, sin = emparejar(lst, cands)
        for idm, j in par.items():
            out_j.setdefault(idm, {})[str(g["gw"])] = {"p": j["p"], "conf": j["conf"], "les": j["les"], "ff": j["slug"], "once": j["once"]}
        sin_par += [dict(x, partido=f"{a}-{b}") for x in sin]
        info.append({"ff": pid, "local": a, "visitante": b, "jornada": g["gw"], "jugadores": len(lst), "emparejados": len(par),
                     "confirmada": any(j["conf"] for j in lst)})
        print(f"  {a}-{b} (J{g['gw']}): {len(lst)} jugadores en FF, {len(par)} emparejados con Mister")

    # mezcla con Analítica Fantasy: media de las dos webs cuando ambas tienen al jugador
    try:
        af, n_af = leer_analitica(s, pend, eq, por_equipo)
    except Exception as e:
        af, n_af = {}, 0
        print(f"[!] Analítica Fantasy no disponible: {e}")
    for idm, porgw in af.items():
        for gw, d in porgw.items():
            e = out_j.setdefault(idm, {}).get(gw)
            if e is None:
                out_j[idm][gw] = {"p": d["p"], "pff": None, "paf": d["p"], "conf": False, "les": -1, "ff": None, "once": "titular" if d["tit"] else "suplente"}
            else:
                e["pff"] = e["p"]
                e["paf"] = d["p"]
                if not e["conf"]:                       # alineación confirmada en FF: manda la confirmación
                    e["p"] = round((e["pff"] + d["p"]) / 2, 3)
    for porgw in out_j.values():
        for e in porgw.values():
            e.setdefault("pff", e["p"] if e.get("ff") else None)
            e.setdefault("paf", None)
    print(f"Analítica Fantasy: {n_af} partidos leídos")

    if not out_j:
        print("No se ha podido leer ninguna alineacion: no se escribe nada.")
        sys.exit(1)
    ahora_iso = datetime.now(timezone.utc).isoformat(timespec="seconds")
    res = {"updatedAt": ahora_iso, "fuente": "futbolfantasy.com + analiticafantasy.com", "partidos": info, "jugadores": out_j, "sinEmparejar": sin_par[:80]}
    # solo reescribe si cambia algo (para no llenar el historial de commits)
    if {k: previo.get(k) for k in ("partidos", "jugadores")} != {k: res[k] for k in ("partidos", "jugadores")}:
        with open(os.path.join(CARPETA, "alineaciones.json"), "w", encoding="utf-8") as f:
            json.dump(res, f, ensure_ascii=False, separators=(",", ":"))
        print("alineaciones.json actualizado.")
    else:
        print("Sin cambios.")

    # historial: ultima probabilidad conocida ANTES del partido (para calibrar despues con lo que paso de verdad)
    hist = cargar("alineaciones_historial.json", {})
    equipo_de = {p["id"]: p["teamId"] for p in jug}
    for idm, porgw in out_j.items():
        for gw, d in porgw.items():
            game = next((x for x in pend if str(x["gw"]) == gw and equipo_de.get(idm) in (x["home"], x["away"])), None)
            if game and (game.get("ts") or 9e12) > ahora:
                hist.setdefault(gw, {})[idm] = [d["p"], int(d["conf"]), ahora_iso, d.get("pff"), d.get("paf")]
    with open(os.path.join(CARPETA, "alineaciones_historial.json"), "w", encoding="utf-8") as f:
        json.dump(hist, f, ensure_ascii=False, separators=(",", ":"))


if __name__ == "__main__":
    main()
