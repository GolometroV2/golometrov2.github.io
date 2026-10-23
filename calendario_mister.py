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
from datetime import datetime, timezone

import requests

import mister_extractor as m

ARCHIVO = os.path.join(m.CARPETA_SCRIPT, "calendario.json")
JORNADAS_FUTURAS = 3   # cuántas jornadas por jugar se guardan (la próxima y las siguientes)


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
    return m.post_ajax(session, "/ajax/sw/gameweek", {"post": "gameweek", "id": gw_id}, gw_id)


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
    except (RuntimeError, m.ErrorSesion) as e:
        print(f"[!] {e}. No se modifica calendario.json.")
        sys.exit(1)

    ahora = m.hora_madrid()
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


if __name__ == "__main__":
    main()
