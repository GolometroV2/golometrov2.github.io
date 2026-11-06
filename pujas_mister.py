#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PUJAS DEL MERCADO (noticias de Mister)

En la pantalla de noticias de Mister, cada fichaje del mercado trae un desplegable con TODAS las pujas que se
hicieron por ese jugador (no solo la ganadora). Mister solo deja ver las de los últimos 30 días. Este script las
lee de la misma petición que usa la web al bajar por las noticias (POST /ajax/feed, 20 tarjetas por página) y
las guarda en pujas_mister.json para la pestaña Mercado.

Uso:
  python pujas_mister.py            -> lee las noticias de los últimos 30 días y actualiza pujas_mister.json
  python pujas_mister.py --muestra  -> además guarda feed_muestra.html: las primeras páginas SIN scripts ni
                                       atributos (solo clases y texto), para ver cómo está hecha la página.
Las credenciales salen de los secretos (MISTER_COOKIE y X_AUTH_TOKEN) a través de mister_extractor; nunca se
imprimen ni se guardan.
"""
import json
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone

from bs4 import BeautifulSoup

CARPETA = os.path.dirname(os.path.abspath(__file__))
SALIDA = os.path.join(CARPETA, "pujas_mister.json")
MUESTRA = os.path.join(CARPETA, "feed_muestra.html")
POR_PAGINA = 20
MAX_PAGINAS = 30
PAUSA = 1.5
DIAS = 31


def html_de(resp_text):
    """La respuesta puede ser HTML o un JSON con el HTML dentro: se devuelve el HTML."""
    t = resp_text.strip()
    if t.startswith("{") or t.startswith("["):
        try:
            j = json.loads(t)
        except ValueError:
            return t
        trozos = []

        def buscar(x):
            if isinstance(x, str) and "<" in x and ">" in x:
                trozos.append(x)
            elif isinstance(x, dict):
                for v in x.values():
                    buscar(v)
            elif isinstance(x, list):
                for v in x:
                    buscar(v)
        buscar(j)
        return "\n".join(trozos)
    return t


def limpiar(html):
    """Quita scripts, estilos, formularios y casi todos los atributos: queda la estructura con clases y texto."""
    s = BeautifulSoup(html, "html.parser")
    for t in s(["script", "style", "noscript", "iframe", "form", "input", "link", "meta"]):
        t.decompose()
    for t in s.find_all("svg"):
        t.replace_with(s.new_string("[icono]"))
    for t in s.find_all(True):
        guardar = {}
        for k, v in list(t.attrs.items()):
            val = " ".join(v) if isinstance(v, list) else str(v)
            if (k == "class" or k.startswith("data-") or k in ("title", "alt", "href")) and len(val) < 160 \
                    and not re.search(r"token|auth|session|cookie|key", k + val, re.I):
                guardar[k] = v
        t.attrs = guardar
    return str(s)


# ---------------------------------------------------------------- lectura de las tarjetas
NUM = re.compile(r"\d{1,3}(?:\.\d{3})+|\d{4,}")


def numero(txt):
    m = NUM.search(txt or "")
    return int(m.group(0).replace(".", "")) if m else None


def parsear(html, managers):
    """Lee las tarjetas «card-transfer» de las noticias. Cada fila de jugador da: jugador (id de Mister), de quién
    a quién pasa, precio, si fue por cláusula, la antigüedad que muestra la cabecera («5h», «6d») y, si el fichaje
    salió del mercado, el desplegable «Otras pujas» con el resto de pujas (manager y cantidad).
    managers: {nombre: id}. Devuelve una lista de fichajes."""
    s = BeautifulSoup(html, "html.parser")
    compras = []
    visto_dias = False
    for card in s.select(".card.card-transfer"):
        envol = card.find_parent(class_="card-wrapper")
        cab = envol.select_one(".head") if envol else None
        edad = None
        if cab:
            m = re.search(r"(\d+)\s*([mhdsM])\s*$", cab.get_text(" ", strip=True))
            if m:
                u = m.group(2)
                if u == "d":
                    visto_dias = True
                if u == "m" and visto_dias:
                    u = "M"     # «1m» después de tarjetas en días = hace un mes (si no, son minutos)
                edad = m.group(1) + u
        for li in card.select("ul.player-list > li"):
            titulo = li.select_one(".title")
            fila = li.select_one(".player-row")
            if not titulo or not fila:
                continue
            j = titulo.find("strong")
            ems = [e.get_text(" ", strip=True) for e in titulo.find_all("em")]
            enlace = fila.select_one("a.player")
            pid = re.search(r"/players/(\d+)", enlace.get("href", "")) if enlace else None
            precio = numero(fila.select_one(".price").get_text()) if fila.select_one(".price") else None
            if not j or len(ems) < 2 or not precio:
                continue
            de, a = ems[0], ems[-1]
            pujas = [{"manager": a, "id": managers.get(a), "cantidad": precio}]
            for o in li.select("ul.other-bids > li"):
                if "other-bids-title" in (o.get("class") or []):
                    continue
                quien = o.find("strong")
                q = numero(o.get_text(" ", strip=True).split("›")[-1])
                if quien and q:
                    n = quien.get_text(" ", strip=True)
                    pujas.append({"manager": n, "id": managers.get(n), "cantidad": q})
            tipo = "clausula" if "cláusula" in titulo.get_text(" ") or "cláusula" in li.get_text(" ") else \
                ("venta" if a == "Mister" else ("mercado" if de == "Mister" else "traspaso"))
            compras.append({"feed": card.get("id", "").replace("feed-", ""), "playerId": pid.group(1) if pid else None,
                            "jugador": j.get_text(" ", strip=True), "de": de, "a": a,
                            "aId": managers.get(a), "deId": managers.get(de),
                            "precio": precio, "tipo": tipo, "edad": edad, "pujas": pujas})
    return compras


def fecha_de(edad, ref):
    """«5h», «6d», «1m» (cabecera de la tarjeta) -> fecha aproximada (UTC) restando a la hora de lectura."""
    if not edad:
        return None
    n, u = int(edad[:-1]), edad[-1]
    d = {"m": timedelta(minutes=n), "h": timedelta(hours=n), "d": timedelta(days=n), "s": timedelta(weeks=n),
         "M": timedelta(days=30 * n)}.get(u)
    return (ref - d).strftime("%Y-%m-%dT%H:%M:%SZ") if d else None


def poner_fechas(compras, ref):
    """Fecha de cada fichaje: la exacta de pujas.json si es el mismo jugador y comprador; si no, la aproximada."""
    exactas = {}
    try:
        with open(os.path.join(CARPETA, "pujas.json"), encoding="utf-8") as f:
            for c in json.load(f).get("compras", []):
                exactas.setdefault((str(c.get("playerId")), str(c.get("to"))), []).append(c.get("ts"))
    except (OSError, ValueError):
        pass
    for c in compras:
        aprox = fecha_de(c.get("edad"), ref)
        cand = exactas.get((str(c.get("playerId")), str(c.get("aId"))), [])
        if aprox and cand:
            t0 = datetime.strptime(aprox, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
            mejor = min(cand, key=lambda t: abs((datetime.strptime(t, "%Y-%m-%dT%H:%M:%SZ").replace(
                tzinfo=timezone.utc) - t0).total_seconds()))
            if abs((datetime.strptime(mejor, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc) - t0).days) <= 2:
                c["ts"], c["exacta"] = mejor, True
                continue
        c["ts"] = aprox


def poner_valores(compras):
    """Valor de mercado del jugador cuando se pujó (para medir la sobrepuja): el «listado» de pujas.json si es la
    misma compra; si no, el último valor de jugadores_historial.json anterior al día del fichaje."""
    listado, hist = {}, {}
    try:
        with open(os.path.join(CARPETA, "pujas.json"), encoding="utf-8") as f:
            for c in json.load(f).get("compras", []):
                if c.get("listado"):
                    listado[(str(c.get("playerId")), str(c.get("to")), (c.get("ts") or "")[:10])] = c["listado"]
    except (OSError, ValueError):
        pass
    try:
        with open(os.path.join(CARPETA, "jugadores_historial.json"), encoding="utf-8") as f:
            hist = json.load(f).get("valor", {})
    except (OSError, ValueError):
        pass
    for c in compras:
        if c.get("valor") or c.get("tipo") != "mercado" or not c.get("ts"):
            continue
        dia = c["ts"][:10]
        v = listado.get((str(c.get("playerId")), str(c.get("aId")), dia)) if c.get("exacta") else None
        if not v:
            serie = hist.get(str(c.get("playerId"))) or {}
            antes = sorted(k for k in serie if k < dia)
            # solo si hay valor del día anterior o el de antes (más atrás el valor ya ha cambiado)
            if antes and (datetime.fromisoformat(dia) - datetime.fromisoformat(antes[-1])).days <= 2:
                v = serie[antes[-1]]
        if v:
            c["valor"] = v


def guardar(compras):
    try:
        with open(SALIDA, encoding="utf-8") as f:
            previo = json.load(f)
    except (OSError, ValueError):
        previo = {"compras": []}
    # se acumulan: Mister solo enseña 30 días, aquí se guardan todos. Clave: tarjeta + jugador.
    clave = lambda c: (str(c.get("feed")), str(c.get("playerId")))
    vistos = {clave(c) for c in previo.get("compras", [])}
    nuevas = [c for c in compras if clave(c) not in vistos]
    for c in compras:
        c.pop("edad", None)
    previo["compras"] = sorted(nuevas + previo.get("compras", []), key=lambda c: c.get("ts") or "", reverse=True)
    previo["updatedAt"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    previo["nota"] = ("Fichajes leídos de las noticias de Mister. pujas = todas las pujas del fichaje (la primera es "
                      "la ganadora). tipo: mercado (de Mister), clausula, traspaso (entre managers) o venta (a Mister).")
    with open(SALIDA, "w", encoding="utf-8") as f:
        json.dump(previo, f, ensure_ascii=False, indent=0)
    con = sum(1 for c in previo["compras"] if len(c.get("pujas", [])) > 1)
    print(f"pujas_mister.json: {len(nuevas)} nuevas, {len(previo['compras'])} en total ({con} con varias pujas)")


def cargar_managers():
    try:
        with open(os.path.join(CARPETA, "mister_fantasy_data.json"), encoding="utf-8") as f:
            return {x.get("name", ""): str(x.get("id")) for x in json.load(f).get("managers", [])}
    except (OSError, ValueError):
        return {}


def main():
    managers = cargar_managers()
    # Modo local: leer una página de noticias guardada desde el navegador (sin credenciales)
    if "--html" in sys.argv:
        i = sys.argv.index("--html")
        ruta = sys.argv[i + 1]
        ref = datetime.now(timezone.utc)
        if "--fecha" in sys.argv:
            ref = datetime.fromisoformat(sys.argv[sys.argv.index("--fecha") + 1].replace("Z", "+00:00"))
        with open(ruta, encoding="utf-8", errors="ignore") as f:
            compras = parsear(f.read(), managers)
        poner_fechas(compras, ref)
        poner_valores(compras)
        print(f"Fichajes leídos de {os.path.basename(ruta)}: {len(compras)}")
        guardar(compras)
        return 0
    muestra = "--muestra" in sys.argv
    import requests
    import mister_extractor as m
    s = requests.Session()
    cab = dict(m.HEADERS)
    cab["referer"] = m.URL_BASE + "/feed"
    cab["content-type"] = "application/x-www-form-urlencoded; charset=UTF-8"
    cab.pop("partial-request", None)
    paginas, tipos = [], []
    ahora = datetime.now(timezone.utc)
    for k in range(MAX_PAGINAS):
        datos = {"end": "false", "loading": "true", "offset": str(k * POR_PAGINA), "cardsPerPage": str(POR_PAGINA)}
        try:
            r = s.post(m.URL_BASE + "/ajax/feed", headers=cab, data=datos, timeout=30)
        except requests.RequestException as e:
            print(f"[!] Error de red en la página {k + 1}: {type(e).__name__}")
            break
        if r.status_code != 200:
            print(f"[!] HTTP {r.status_code} en la página {k + 1} (¿credenciales caducadas?)")
            break
        tipos.append(r.headers.get("content-type", "?"))
        h = html_de(r.text)
        if not h.strip() or "card" not in h:
            break
        paginas.append(h)
        # se para al pasar de 30 días («1M» o más de 31 «d» en la cabecera de las tarjetas)
        if any((c.get("edad") or "").endswith("M") or (c.get("edad") or "").endswith("d") and int(c["edad"][:-1]) > DIAS
               for c in parsear(h, managers)):
            break
        time.sleep(PAUSA)
    print(f"Noticias: {len(paginas)} páginas leídas (tipo de respuesta: {', '.join(sorted(set(tipos))) or '-'})")
    if not paginas:
        return 1
    if muestra:
        with open(MUESTRA, "w", encoding="utf-8") as f:
            f.write("<!-- Muestra de las noticias de Mister sin scripts ni atributos sensibles (pujas_mister.py --muestra) -->\n")
            f.write("\n<!-- ===== página ===== -->\n".join(limpiar(p) for p in paginas[:6]))
        print(f"Guardada la muestra en {os.path.basename(MUESTRA)}")
    compras = []
    for p in paginas:
        compras += parsear(p, managers)
    poner_fechas(compras, ahora)
    poner_valores(compras)
    print(f"Fichajes encontrados: {len(compras)}")
    guardar(compras)
    return 0


if __name__ == "__main__":
    sys.exit(main())
