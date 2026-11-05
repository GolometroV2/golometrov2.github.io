#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SEGUIMIENTO DE PLANTILLAS Y ECONOMÍA

Genera equipos.json con:
  - las plantillas actuales de cada manager (valor, cambio diario, cláusula...)
  - el historial de valores de cada jugador y de cada plantilla
  - los fichajes y ventas detectados entre ejecuciones

Se ejecuta con frecuencia (cada ~15 minutos desde GitHub Actions). Solo reescribe
equipos.json si algo ha cambiado, así que solo hay commit cuando un manager compra
o vende, o cuando cambian los valores.
Usa las mismas credenciales que mister_extractor.py.
"""

import json
import os
import re
import sys
from datetime import datetime, timezone

import requests

import mister_extractor as m

ARCHIVO = os.path.join(m.CARPETA_SCRIPT, "equipos.json")
MAX_HISTORIAL = 60        # entradas guardadas por jugador / plantilla
MAX_MOVIMIENTOS = 100
ARCHIVO_PUJAS = os.path.join(m.CARPETA_SCRIPT, "pujas.json")
CLAUSULA_MINIMA = 1000000
CARPETA_FOTOS = os.path.join(m.CARPETA_SCRIPT, "fotos")
_fallos_foto = {"n": 0}
POS = {1: "PT", 2: "DF", 3: "MC", 4: "DL"}


def cargar_previo():
    if os.path.exists(ARCHIVO):
        try:
            with open(ARCHIVO, "r", encoding="utf-8") as f:
                return json.load(f)
        except (ValueError, OSError):
            pass
    return {}


def entero(x):
    try:
        return int(round(float(x)))
    except (TypeError, ValueError):
        return 0


def actualizar_historial(hist, clave, valor, anterior, fecha):
    """Guarda [fecha, valor, valorAnterior] solo si ha cambiado respecto a la última entrada."""
    h = hist.setdefault(str(clave), [])
    if h and h[-1][1] == valor and h[-1][2] == anterior:
        return
    if h and h[-1][0] == fecha:
        h[-1] = [fecha, valor, anterior]
    else:
        h.append([fecha, valor, anterior])
    del h[:-MAX_HISTORIAL]


def descargar_foto(url, subcarpeta, ident):
    """Guarda la imagen en fotos/<subcarpeta>/ y devuelve la ruta relativa (o la URL original si falla)."""
    if not url or not str(url).startswith("http") or ident is None:
        return None
    version = re.search(r"version=(\d+)", url)
    nombre = f"{ident}_{version.group(1)}.png" if version else f"{ident}.png"
    ruta = os.path.join(CARPETA_FOTOS, subcarpeta, nombre)
    relativa = f"fotos/{subcarpeta}/{nombre}"
    if os.path.exists(ruta) and os.path.getsize(ruta) > 0:
        return relativa
    if _fallos_foto["n"] >= 3:      # si el servidor de imágenes falla, no se insiste en cada jugador
        return url
    try:
        r = requests.get(url, timeout=15, headers={"user-agent": m.HEADERS["user-agent"],
                                                   "referer": "https://mister.mundodeportivo.com/"})
        if r.status_code == 200 and r.content and r.headers.get("content-type", "").startswith("image/"):
            os.makedirs(os.path.dirname(ruta), exist_ok=True)
            with open(ruta, "wb") as f:
                f.write(r.content)
            return relativa
        print(f"   [!] No se pudo descargar la imagen (status {r.status_code}): {url}")
    except Exception as e:
        print(f"   [!] Error descargando {url}: {e}")
    _fallos_foto["n"] += 1
    return url


def descargar_plantillas(session):
    resp = session.post(m.URL_STANDINGS, params={"gw": m.GW_SEMILLA}, headers=m.HEADERS, timeout=20)
    if resp.status_code != 200:
        raise RuntimeError(f"Clasificación: status {resp.status_code}")
    listas = m.extraer_listas(resp.text)
    if not listas:
        raise RuntimeError("No se encontró la clasificación en la respuesta")

    managers = []
    for f in listas[0]:
        data = m.post_ajax(
            session, "/ajax/sw/users",
            {"post": "users", "id": f["id"], "slug": f["slug"], "qs": f"gw={m.GW_SEMILLA}", "comments": "0"},
            m.GW_SEMILLA,
        )
        if not data:
            # Si falta un manager parecería que ha vendido a todos sus jugadores: se aborta
            raise RuntimeError(f"No se pudo leer la plantilla de {f['name']}")

        jugadores = []
        for p in data.get("team_now") or []:
            clausula = (p.get("clause") or {}).get("value")
            jugadores.append({
                "id": str(p["id"]),
                "name": p.get("name"),
                "pos": POS.get(entero(p.get("position")), "?"),
                "teamId": p.get("id_team"),
                "value": entero(p.get("value")),
                "prev": entero(p.get("prev_value")),
                "points": p.get("points"),
                "avg": p.get("avg"),
                "clause": entero(clausula) if clausula else None,
                "acquired": p.get("created"),
                "origin": p.get("transfer_origin"),
                "short": p.get("short"),
                "status": p.get("status"),
                "streak": p.get("streak"),
                "photo": descargar_foto(p.get("photoUrl"), "jugadores", p.get("id")),
                "teamLogo": descargar_foto(p.get("teamLogoUrl"), "escudos", p.get("id_team")),
            })
        valor = data.get("value") or {}
        managers.append({
            "id": f["id"],
            "name": f["name"],
            "avatar": "".join(w[0].upper() for w in f["name"].split()[:2]) or "MF",
            "avatarUrl": m.descargar_avatar(f.get("avatarUrl") or ""),
            "hue": f.get("hue"),
            "squadValue": entero(valor.get("value")),
            "squadPrev": entero(valor.get("prev_value")),
            "players": jugadores,
        })
    return managers


def detectar_movimientos(previo, managers, ahora):
    antes = {p["id"]: mg["id"] for mg in previo.get("managers", []) for p in mg["players"]}
    despues = {p["id"]: mg["id"] for mg in managers for p in mg["players"]}
    info = {p["id"]: p for mg in managers + previo.get("managers", []) for p in mg["players"]}
    nuevos = []
    if not antes:        # primera ejecución: no hay con qué comparar
        return nuevos
    for pid in set(antes) | set(despues):
        a, b = antes.get(pid), despues.get(pid)
        if a != b:
            nuevos.append({"date": ahora, "playerId": pid, "name": info[pid]["name"],
                           "from": a, "to": b, "value": info[pid]["value"]})
    return nuevos


def registrar_pujas(movimientos, managers):
    """pujas.json: lo que se pagó en cada compra, para calibrar la puja ideal de la web.
    Mister pone la cláusula en 1,5 veces el precio pagado (comprobado con todas las cláusulas pagadas en la liga),
    así que precio = cláusula / 1,5. Con la cláusula mínima (1.000.000 €) solo se sabe que se pagó 666.667 € o menos."""
    compras = [mv for mv in movimientos if mv.get("to")]
    if not compras:
        return
    try:
        with open(ARCHIVO_PUJAS, encoding="utf-8") as f:
            datos = json.load(f)
    except (OSError, ValueError):
        datos = {"compras": []}
    try:
        with open(os.path.join(m.CARPETA_SCRIPT, "mercado_historial.json"), encoding="utf-8") as f:
            hist = json.load(f)
    except (OSError, ValueError):
        hist = {}
    jug = {(mg["id"], str(p["id"])): p for mg in managers for p in mg["players"]}
    for mv in compras:
        pid = str(mv["playerId"])
        p = jug.get((mv["to"], pid))
        cl = (p or {}).get("clause")
        if not cl:
            continue
        tipo = "clausula" if p.get("origin") == "clause" else ("mercado" if not mv.get("from") else "traspaso")
        dias = [d for d in sorted(hist) if d < mv["ts"][:10] and pid in hist[d]]
        datos.setdefault("compras", []).insert(0, {
            "ts": mv["ts"], "playerId": pid, "name": mv["name"], "from": mv.get("from"), "to": mv["to"], "tipo": tipo,
            "valor": mv["value"], "listado": hist[dias[-1]][pid] if tipo == "mercado" and dias else None,
            "precio": round(cl / 1.5) if cl > CLAUSULA_MINIMA else None, "clausulaMinima": cl <= CLAUSULA_MINIMA})
        print(f"   Puja: {mv['name']} ({tipo}) por {round(cl / 1.5) if cl > CLAUSULA_MINIMA else '≤ 666.667'} €")
    datos["updatedAt"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with open(ARCHIVO_PUJAS, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=0)


def indice_fotos():
    """fotos/indice.json: {idJugador: ruta de su foto más reciente}. La página lo usa para poner cara a los capitanes de
    jornadas pasadas aunque ese jugador ya no esté en ninguna plantilla."""
    carpeta = os.path.join(CARPETA_FOTOS, "jugadores")
    if not os.path.isdir(carpeta):
        return
    ind = {}
    for nombre in sorted(os.listdir(carpeta)):
        if nombre.endswith(".png") and os.path.getsize(os.path.join(carpeta, nombre)) > 0:
            ind[nombre.split("_")[0].split(".")[0]] = f"fotos/jugadores/{nombre}"
    ruta = os.path.join(CARPETA_FOTOS, "indice.json")
    try:
        with open(ruta, encoding="utf-8") as f:
            if json.load(f) == ind:
                return
    except (OSError, ValueError):
        pass
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(ind, f, ensure_ascii=False, separators=(",", ":"))


def main():
    session = requests.Session()
    previo = cargar_previo()
    try:
        managers = descargar_plantillas(session)
    except (RuntimeError, m.ErrorSesion) as e:
        print(f"[!] {e}. No se modifica equipos.json.")
        sys.exit(1)

    ahora = m.hora_madrid()
    fecha, fecha_hora = ahora.strftime("%Y-%m-%d"), ahora.strftime("%d/%m %H:%M")

    history = previo.get("history", {})
    for mg in managers:
        for p in mg["players"]:
            actualizar_historial(history, p["id"], p["value"], p["prev"], fecha)
    squad_history = previo.get("squadHistory", {})
    for mg in managers:
        actualizar_historial(squad_history, mg["id"], mg["squadValue"], mg["squadPrev"], fecha)

    ahora_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    movimientos = detectar_movimientos(previo, managers, fecha_hora)
    for mv in movimientos:
        mv["ts"] = ahora_utc
        print(f"   Movimiento: {mv['name']} | {mv['from']} -> {mv['to']}")
    transfers = (movimientos + previo.get("transfers", []))[:MAX_MOVIMIENTOS]
    try:
        registrar_pujas(movimientos, managers)
    except Exception as e:          # nunca debe impedir guardar las plantillas
        print(f"[!] No se pudo registrar el precio de las compras: {e}")

    salida = {
        "updated": ahora.strftime("%d/%m/%Y %H:%M"),
        "updatedAt": ahora_utc,
        "managers": managers,
        "history": history,
        "squadHistory": squad_history,
        "transfers": transfers,
    }

    indice_fotos()
    sin_hora = lambda d: {k: v for k, v in d.items() if k not in ("updated", "updatedAt")}
    if sin_hora(salida) == sin_hora(previo):
        print("Sin cambios: no se escribe equipos.json.")
        return

    with open(ARCHIVO, "w", encoding="utf-8") as f:
        json.dump(salida, f, ensure_ascii=False, separators=(",", ":"))
    print(f"equipos.json actualizado ({len(managers)} managers, {len(movimientos)} movimientos nuevos).")


if __name__ == "__main__":
    main()

