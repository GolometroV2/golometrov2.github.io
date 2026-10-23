#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CALENDARIO Y ALINEACIONES PROBABLES (para el recomendador de capitán)

Genera calendario.json con:
  - la lista de jornadas (id, número, estado, fechas)
  - los partidos de cada jornada (local, visitante, goles, fecha)
  - las alineaciones probables de los partidos aún sin jugar

Las jornadas ya terminadas se piden una sola vez; las próximas se vuelven a pedir en cada
ejecución porque las alineaciones probables cambian. Solo reescribe el archivo si algo cambió.
Usa las mismas credenciales que mister_extractor.py.
"""

import json
import os
import sys
import time
from datetime import datetime, timezone

import requests

import mister_extractor as m

ARCHIVO = os.path.join(m.CARPETA_SCRIPT, "calendario.json")
JORNADAS_FUTURAS = 3   # cuántas jornadas por jugar se guardan (la próxima y las siguientes)


def hora_madrid():
    """Hora de Madrid. Usa la de mister_extractor si existe (versión nueva); si no, calcula la suya."""
    if hasattr(m, "hora_madrid"):
        return m.hora_madrid()
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("Europe/Madrid"))
    except Exception:
        return datetime.now()


def cargar_previo():
    try:
        with open(ARCHIVO, "r", encoding="utf-8") as f:
            return json.load(f)
    except (ValueError, OSError):
        return {}


def numero(x):
    try:
        return int(x)
    except (TypeError, ValueError):
        return None


def pedir_jornada(session, gw_id):
    """Pide una jornada y, si falla, explica por qué (código HTTP y principio de la respuesta)."""
    headers = {k: v for k, v in m.HEADERS.items() if k != "partial-request"}
    headers["content-type"] = "application/x-www-form-urlencoded; charset=UTF-8"
    headers["referer"] = f"{m.URL_BASE}/feed"
    try:
        resp = session.post(m.URL_BASE + "/ajax/sw/gameweek", data={"post": "gameweek", "id": gw_id},
                            headers=headers, timeout=20)
    except Exception as e:
        print(f"   [!] Error de red pidiendo la jornada {gw_id}: {e}")
        return None
    try:
        contenido = resp.json()
    except ValueError:
        print(f"   [!] Jornada {gw_id}: HTTP {resp.status_code} y la respuesta no es JSON.")
        print(f"       Empieza por: {resp.text[:200]!r}")
        print("       Suele significar que la cookie o el x-auth han caducado: renuévalos en credenciales.env.")
        return None
    if resp.status_code != 200 or contenido.get("status") != "ok":
        print(f"   [!] Jornada {gw_id}: HTTP {resp.status_code}, respuesta: {str(contenido)[:200]}")
        return None
    time.sleep(m.PAUSA_ENTRE_PETICIONES)
    return contenido.get("data")


def partidos_de(data, gw_id, gw_num):
    out = []
    for g in data.get("games") or []:
        out.append({
            "id": g.get("id"),
            "gwId": gw_id,
            "gw": gw_num,
            "home": g.get("id_home"),
            "away": g.get("id_away"),
            "homeName": g.get("home"),
            "awayName": g.get("away"),
            "gh": numero(g.get("goals_home")),
            "ga": numero(g.get("goals_away")),
            "status": g.get("status"),
            "ts": (g.get("date") or {}).get("ts"),
        })
    return out


def alineaciones_de(data):
    """{idPartido: {idEquipo: {"players": [ids], "confirmed": 0/1}}} con los 11 probables."""
    res = {}
    for id_partido, prev in (data.get("preview") or {}).items():
        equipos = {}
        for id_equipo, lista in ((prev or {}).get("players") or {}).items():
            equipos[str(id_equipo)] = {
                "players": [str(p["id"]) for p in lista],
                "confirmed": 1 if any(p.get("confirmed") for p in lista) else 0,
            }
        if equipos:
            res[str(id_partido)] = equipos
    return res


def main():
    print(f"Se guardará en: {ARCHIVO}")
    session = requests.Session()
    previo = cargar_previo()
    try:
        semilla = pedir_jornada(session, m.GW_SEMILLA)
        if not semilla or not semilla.get("gameweeks"):
            raise RuntimeError("No se pudo leer la lista de jornadas")
        jornadas = [
            {"id": g["id"], "gw": g["gameweek"], "status": g.get("status"),
             "first": g.get("firstMatchDate"), "last": g.get("lastMatchDate")}
            for g in semilla["gameweeks"]
        ]

        partidos_previos = {}
        for g in previo.get("games", []):
            partidos_previos.setdefault(g["gwId"], []).append(g)

        partidos, alineaciones = [], {}
        por_jugar = 0
        for j in jornadas:
            terminada = j["status"] == "finished"
            if terminada:
                previos = partidos_previos.get(j["id"])
                if previos and all(g.get("gh") is not None for g in previos):
                    partidos.extend(previos)   # ya la teníamos completa
                    continue
            else:
                if por_jugar >= JORNADAS_FUTURAS:
                    continue
                por_jugar += 1
            data = semilla if j["id"] == m.GW_SEMILLA else pedir_jornada(session, j["id"])
            if not data:
                raise RuntimeError(f"No se pudo leer la jornada {j['gw']}")
            partidos.extend(partidos_de(data, j["id"], j["gw"]))
            if not terminada:
                alineaciones.update(alineaciones_de(data))
    except (RuntimeError, m.ErrorSesion, KeyError) as e:
        print(f"[!] {e!r}. No se modifica calendario.json.")
        sys.exit(1)

    ahora = hora_madrid()
    salida = {
        "updated": ahora.strftime("%d/%m/%Y %H:%M"),
        "updatedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "gameweeks": jornadas,
        "games": partidos,
        "lineups": alineaciones,
    }
    sin_hora = lambda d: {k: v for k, v in d.items() if k not in ("updated", "updatedAt")}
    if sin_hora(salida) == sin_hora(previo):
        print("Calendario sin cambios.")
        return
    with open(ARCHIVO, "w", encoding="utf-8") as f:
        json.dump(salida, f, ensure_ascii=False, separators=(",", ":"))
    print(f"calendario.json actualizado ({len(partidos)} partidos).")


LOG = os.path.join(m.CARPETA_SCRIPT, "calendario_log.txt")


class _Doble:
    """Copia todo lo que se imprime a un archivo, para poder leerlo aunque la ventana se cierre."""
    def __init__(self, original, archivo):
        self.original, self.archivo = original, archivo

    def write(self, texto):
        self.original.write(texto)
        self.archivo.write(texto)
        self.archivo.flush()

    def flush(self):
        self.original.flush()


def esperar():
    """En local mantiene la ventana abierta; en GitHub Actions no espera."""
    if os.environ.get("GITHUB_ACTIONS"):
        return
    try:
        input("\nPresiona ENTER para cerrar la ventana...")
    except (EOFError, RuntimeError, OSError):
        import time as _t
        _t.sleep(120)   # si no hay consola interactiva, deja 2 minutos para leer


if __name__ == "__main__":
    local = not os.environ.get("GITHUB_ACTIONS")
    if local:
        sys.stdout = _Doble(sys.stdout, open(LOG, "w", encoding="utf-8"))
    codigo = 0
    try:
        main()
    except SystemExit as e:
        codigo = e.code if isinstance(e.code, int) else 1
    except Exception:
        import traceback
        traceback.print_exc()
        codigo = 1
    if local:
        print(f"\n(Este mensaje también está guardado en {LOG})")
    esperar()
    sys.exit(codigo)
