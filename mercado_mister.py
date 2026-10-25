#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MERCADO: jugadores libres (los que pone el juego) y los que venden otros managers.

Pide la página del mercado, separa a los libres (data-owner = 0) de los que vende un manager humano
y guarda mercado.json. Además guarda cada día el valor de los libres en mercado_historial.json para
calcular cuánto crece su valor al día (la página solo da una flecha verde/roja, sin cantidad).

Usa las mismas credenciales que mister_extractor.py. El mercado se renueva a las 05:00 (hora de Madrid);
conviene ejecutarlo a partir de las 06:00 porque tarda un rato en actualizarse.

Uso:  python mercado_mister.py            (pide el mercado y guarda mercado.json)
      python mercado_mister.py archivo.html   (prueba el lector con una respuesta guardada, sin conectarse)
"""

import json
import os
import re
import sys
from datetime import datetime, timezone

from bs4 import BeautifulSoup

CARPETA = os.path.dirname(os.path.abspath(__file__))
ARCHIVO = os.path.join(CARPETA, "mercado.json")
HISTORIAL = os.path.join(CARPETA, "mercado_historial.json")
DIAS_HISTORIAL = 30
URL_MERCADO = "https://mister.mundodeportivo.com/market"
POSICIONES = {1: "PT", 2: "DF", 3: "MC", 4: "DL"}


def _num(txt):
    m = re.search(r"-?\d+", str(txt or "").replace(".", ""))
    return int(m.group(0)) if m else None


def _dec(txt):
    try:
        return float(str(txt).strip().replace(",", "."))
    except ValueError:
        return None


def parsear(html):
    """Devuelve la lista de jugadores del mercado (libres y de managers) a partir del HTML."""
    sopa = BeautifulSoup(html, "html.parser")
    jugadores = []
    for li in sopa.select("li[data-price][data-owner]"):
        enlace = li.select_one("a.player[href*='players/']")
        if not enlace:
            continue
        mid = re.search(r"players/(\d+)(?:/([^/?#]+))?", enlace.get("href", ""))
        if not mid:
            continue
        nombre_el = li.select_one(".name")
        nombre = re.sub(r"\s+", " ", nombre_el.get_text(" ", strip=True)) if nombre_el else ""
        equipo = li.select_one(".icons img.team-logo")
        mt = re.search(r"teams/(\d+)", equipo.get("src", "")) if equipo else None
        rival = li.select_one(".rival img.team-logo")
        mr = re.search(r"teams/(\d+)", rival.get("src", "")) if rival else None
        foto = li.select_one(".player-avatar img")
        avatar = li.select_one(".player-avatar")
        estados = [c[3:] for c in (avatar.get("class", []) if avatar else []) if c.startswith("st-")]
        if nombre_el is not None and nombre_el.select_one("svg use[href*='injury']") and "injury" not in estados:
            estados.append("injury")
        racha = []
        for s in li.select(".streak span"):
            t = s.get_text(strip=True)
            racha.append(int(t) if re.fullmatch(r"-?\d+", t) else None)
        flecha = li.select_one(".value-arrow")
        sentido = 0
        if flecha:
            cl = flecha.get("class", [])
            sentido = 1 if "green" in cl else -1 if "red" in cl else 0
        vendedor_el = li.select_one(".header .date")
        vendedor = re.sub(r"\s+", " ", vendedor_el.get_text(" ", strip=True)).rstrip(",").strip() if vendedor_el else ""
        owner = str(li.get("data-owner", "0"))
        pos = int(li.get("data-position") or 0)
        pts = li.select_one(".icons .points")
        avg = li.select_one(".avg")
        jugadores.append({
            "id": mid.group(1),
            "slug": mid.group(2) or "",
            "name": nombre,
            "pos": POSICIONES.get(pos, "?"),
            "teamId": int(mt.group(1)) if mt else None,
            "rivalId": int(mr.group(1)) if mr else None,
            "price": _num(li.get("data-price")),
            "free": owner == "0",
            "seller": "Libre" if owner == "0" else vendedor,
            "ends": _num(li.get("data-ends")),
            "points": _num(pts.get_text()) if pts else None,
            "avg": _dec(avg.get_text()) if avg else None,
            "streak": racha,
            "arrow": sentido,
            "status": estados,
            "photo": foto.get("src", "") if foto else "",
        })
    return jugadores


def guardar_historial(libres, hoy):
    try:
        with open(HISTORIAL, encoding="utf-8") as f:
            h = json.load(f)
    except (OSError, ValueError):
        h = {}
    h[hoy] = {j["id"]: j["price"] for j in libres if j["price"]}
    for d in sorted(h)[:-DIAS_HISTORIAL]:
        del h[d]
    with open(HISTORIAL, "w", encoding="utf-8") as f:
        json.dump(h, f, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return h


def main():
    if len(sys.argv) > 1:
        with open(sys.argv[1], encoding="utf-8") as f:
            html = f.read()
        ahora = datetime.now(timezone.utc)
    else:
        import mister_extractor as m
        import requests
        sesion = requests.Session()
        cab = dict(m.HEADERS)
        cab["referer"] = m.URL_BASE + "/team"
        resp = sesion.post(URL_MERCADO, headers=cab, timeout=30)
        if resp.status_code != 200 or "player-list" not in resp.text:
            print(f"[!] No se pudo leer el mercado (HTTP {resp.status_code}). Suele significar que la cookie o el x-auth han caducado.")
            with open(os.path.join(CARPETA, "mercado_debug.html"), "w", encoding="utf-8") as f:
                f.write(resp.text)
            sys.exit(1)
        html = resp.text
        ahora = datetime.now(timezone.utc)

    todos = parsear(html)
    if not todos:
        print("[!] La página no contiene jugadores del mercado: nada que guardar.")
        sys.exit(1)
    libres = [j for j in todos if j["free"]]
    hoy = hora_madrid_str(ahora)
    hist = guardar_historial(libres, hoy)
    salida = {
        "updated": hoy,
        "updatedAt": ahora.isoformat(timespec="seconds"),
        "ends": max((j["ends"] or 0) for j in todos) or None,
        "total": len(todos),
        "libres": libres,
        "historial": hist,
    }
    with open(ARCHIVO, "w", encoding="utf-8") as f:
        json.dump(salida, f, ensure_ascii=False, separators=(",", ":"))
    print(f"Mercado: {len(todos)} jugadores, {len(libres)} libres (los {len(todos) - len(libres)} restantes los venden otros managers y se ignoran).")
    for j in libres:
        print(f"   {j['pos']} {j['name']:<22} {j['price']:>10,} €".replace(",", "."))


def hora_madrid_str(ahora):
    try:
        from zoneinfo import ZoneInfo
        return ahora.astimezone(ZoneInfo("Europe/Madrid")).strftime("%Y-%m-%d")
    except Exception:
        return ahora.strftime("%Y-%m-%d")


if __name__ == "__main__":
    codigo = 0
    try:
        main()
    except SystemExit as e:
        codigo = e.code if isinstance(e.code, int) else 1
    except Exception:
        import traceback
        traceback.print_exc()
        codigo = 1
    if not os.environ.get("GITHUB_ACTIONS"):
        try:
            input("\nPresiona ENTER para cerrar la ventana...")
        except (EOFError, RuntimeError, OSError):
            import time as _t
            _t.sleep(60)
    sys.exit(codigo)
