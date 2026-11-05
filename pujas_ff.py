#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PUJA MÁXIMA RENTABLE DE FUTBOL FANTASY (para los libres del mercado de hoy)

Futbol Fantasy publica en la ficha de cada jugador, eligiendo «Mister Fantasy», la «puja máxima rentable»:
lo máximo que se puede pagar sin perder dinero con lo que se espera que suba (según su tendencia de precio
y su titularidad). Este script la lee solo para los libres del mercado del día (una petición a la lista del
mercado de Mister en Futbol Fantasy y una por jugador, con pausa) y guarda pujas_ff.json:

  {"updatedAt": ..., "jugadores": {idMister: {"ff": idFF, "valor": valor según FF, "puja": puja máxima rentable o 0}}}

«puja» = 0 significa «sin rentabilidad» (FF cree que va a bajar). La web usa la puja en porcentaje sobre el
valor de FF, para no depender de que FF haya actualizado ya el precio del día.

Uso:  python pujas_ff.py
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
SALIDA = os.path.join(CARPETA, "pujas_ff.json")


def norm(s):
    s = unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def cargar(nombre, defecto):
    try:
        with open(os.path.join(CARPETA, nombre), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return defecto


def descargar(url, sesion, minimo=2000):
    for i in range(3):
        try:
            r = sesion.get(url, timeout=60)
            if r.status_code == 200 and len(r.text) > minimo:
                return r.text
            print(f"  aviso: {url} -> HTTP {r.status_code}, {len(r.text)} bytes")
        except requests.RequestException as e:
            print(f"  aviso: {url} -> {e}")
        time.sleep(5 * (i + 1))
    return None


def jugadores_ff(html):
    """Filas de la lista del mercado de Mister en FF: id, nombre y valor."""
    filas = []
    for m in re.finditer(r'data-id="(\d+)"\s+data-nombre="([^"]*)"[^>]*?data-valor="(\d+)"', html, re.S):
        filas.append({"id": m.group(1), "n": norm(m.group(2)), "v": int(m.group(3))})
    return filas


def emparejar(nombre, valor, filas):
    """El jugador de FF con el mismo nombre; si hay dudas, el de nombre más parecido con un valor casi igual."""
    k = norm(nombre)
    exactos = [f for f in filas if f["n"] == k]
    if len(exactos) == 1:
        return exactos[0]
    mejor, nota = None, 0
    for f in exactos or filas:
        pal = f["n"].split()
        if len(k.split()) > 1 and len(pal) > 1 and pal[0][0] != k[0]:
            continue        # la inicial del nombre tiene que coincidir (evita confundir a dos «Padilla»)
        sim = SequenceMatcher(None, k, f["n"]).ratio()
        cerca = valor and abs(f["v"] - valor) <= max(0.03 * valor, 20000)
        apellido = k.split()[-1] in f["n"].split() if k else False
        puntos = sim + (0.3 if cerca else 0) + (0.3 if apellido else 0)
        if puntos > nota:
            mejor, nota = f, puntos
    return mejor if mejor and nota >= 1.05 else None


def main():
    mercado = cargar("mercado.json", {})
    libres = mercado.get("libres") or []
    if not libres:
        print("No hay libres en mercado.json: nada que hacer.")
        return 0
    completos = {str(p["id"]): p.get("name") for p in (cargar("jugadores.json", {}).get("jugadores") or [])}
    s = requests.Session()
    s.headers["User-Agent"] = UA
    s.headers["Accept-Language"] = "es-ES,es;q=0.9"
    lista = descargar(BASE + "/analytics/mister/mercado", s, minimo=20000)
    if not lista:
        print("No se pudo leer la lista del mercado de Futbol Fantasy.")
        return 1
    filas = jugadores_ff(lista)
    print(f"Futbol Fantasy: {len(filas)} jugadores en su lista de Mister")
    salida = {}
    for p in libres:
        pid = str(p["id"])
        f = emparejar(completos.get(pid) or p.get("name"), p.get("price"), filas)
        if not f:
            print(f"  sin emparejar: {p.get('name')}")
            continue
        time.sleep(PAUSA)
        html = descargar(f"{BASE}/analytics/mister/mercado/detalle/{f['id']}?perfil=1", s)
        if not html:
            continue
        pujas = re.findall(r"parsePujaIdeal\((\d+)", html)
        if not pujas:
            continue
        puja = int(pujas[-1])
        salida[pid] = {"ff": f["id"], "valor": f["v"], "puja": puja if puja >= f["v"] else 0}
        txt = f"{puja:,}".replace(",", ".") if puja >= f["v"] else "sin rentabilidad"
        print(f"  {p.get('name')}: valor FF {f['v']:,} · puja máxima rentable {txt}".replace(",", "."))
    if not salida:
        print("No se leyó ninguna puja: no se modifica pujas_ff.json.")
        return 1
    with open(SALIDA, "w", encoding="utf-8") as fh:
        json.dump({"updatedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "jugadores": salida},
                  fh, ensure_ascii=False, indent=0)
    print(f"Guardado pujas_ff.json con {len(salida)} jugadores")
    return 0


if __name__ == "__main__":
    sys.exit(main())
