#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TODOS LOS JUGADORES DE LA LIGA (puntos, media, últimas 5 jornadas, valor, estado, próximo rival)

Pide a Mister la lista completa del buscador de jugadores (50 por página) y guarda:
  - jugadores.json            foto del día de cada jugador (valor, valor de ayer, forma, estado, próximo partido, dueño)
  - jugadores_historial.json  memoria acumulada: puntos de cada jugador en cada jornada y valor de cada día

La lista da las últimas 5 jornadas de cada jugador; como el script se ejecuta cada día, el historial va
creciendo y es la base de datos con la que el modelo aprende de los 500 jugadores y no solo de los que
vosotros alineáis. Usa las mismas credenciales que mister_extractor.py.

Uso:  python jugadores_mister.py                 (pide la lista a Mister)
      python jugadores_mister.py respuesta.json  (prueba con una respuesta guardada, sin conectarse)
"""

import json
import os
import sys
import time
from datetime import datetime, timezone

CARPETA = os.path.dirname(os.path.abspath(__file__))
F_JUG = os.path.join(CARPETA, "jugadores.json")
F_HIST = os.path.join(CARPETA, "jugadores_historial.json")
F_CAL = os.path.join(CARPETA, "calendario.json")
URL = "https://mister.mundodeportivo.com/ajax/sw/players"
POSICIONES = {1: "PT", 2: "DF", 3: "MC", 4: "DL"}
POR_PAGINA = 50
MAX_PAGINAS = 40
DIAS_VALOR = 45


def filtros(ancho):
    return {
        "post": "players", "filters[position]": 0, "filters[value_from]": 0,
        "filters[value_to]": 500000000 if ancho else 24800000,
        "filters[clause_from]": 0, "filters[clause_to]": 1000000000 if ancho else 52500000,
        "filters[team]": 0, "filters[injured]": 0, "filters[favs]": 0, "filters[owner]": 0,
        "filters[benched]": 0, "filters[stealable]": 0, "order": 1, "name": "", "parentElement": "#fg-content",
    }


def limpiar(p):
    """Un jugador de la respuesta -> diccionario compacto."""
    mi = p.get("match_info") or {}
    return {
        "id": str(p["id"]),
        "name": p.get("name"),
        "pos": POSICIONES.get(p.get("position"), "?"),
        "teamId": p.get("id_team"),
        "points": p.get("points"),
        "avg": p.get("avg"),
        "status": p.get("status"),
        "streak": p.get("streak") or [],
        "value": p.get("value"),
        "prev": p.get("prev_value"),
        "clause": p.get("clause"),
        "owner": str(p["id_uc"]) if p.get("id_uc") else None,
        "ownerName": p.get("uc_name"),
        "onMarket": bool(p.get("id_market")),
        "nextHome": mi.get("is_home"),
        "nextRival": mi.get("rival_team_id"),
    }


def pedir_todo():
    import requests
    import mister_extractor as m
    ses = requests.Session()
    cab = {k: v for k, v in m.HEADERS.items() if k != "partial-request"}
    cab["content-type"] = "application/x-www-form-urlencoded; charset=UTF-8"
    cab["referer"] = m.URL_BASE + "/search"
    for ancho in (True, False):
        todos, vistos = [], set()
        for pagina in range(MAX_PAGINAS):
            datos = filtros(ancho)
            datos["offset"] = pagina * POR_PAGINA
            try:
                r = ses.post(URL, data=datos, headers=cab, timeout=30)
                j = r.json()
            except Exception as e:
                print(f"   [!] Error en la página {pagina + 1}: {e}")
                break
            if r.status_code != 200 or j.get("status") != "ok":
                print(f"   [!] Respuesta no válida en la página {pagina + 1} (HTTP {r.status_code}).")
                break
            lote = (j.get("data") or {}).get("players") or []
            nuevos = [p for p in lote if str(p["id"]) not in vistos]
            for p in nuevos:
                vistos.add(str(p["id"]))
            todos += nuevos
            print(f"   página {pagina + 1}: {len(lote)} jugadores ({len(todos)} en total)")
            if len(lote) < POR_PAGINA or not nuevos:
                break
            time.sleep(0.4)
        if len(todos) >= 100:
            return todos
        print("   Pocos jugadores con los filtros amplios: se prueban los filtros originales.")
    return todos


def ultima_jornada_cerrada():
    try:
        with open(F_CAL, encoding="utf-8") as f:
            c = json.load(f)
        fin = [g["gw"] for g in c.get("gameweeks", []) if g.get("status") == "finished"]
        return max(fin) if fin else None
    except (OSError, ValueError):
        return None


def cargar(ruta, defecto):
    try:
        with open(ruta, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return defecto


def main():
    if len(sys.argv) > 1:
        with open(sys.argv[1], encoding="utf-8") as f:
            crudo = json.load(f)["data"]["players"]
        ahora = datetime.now(timezone.utc)
        local = True
    else:
        crudo = pedir_todo()
        ahora = datetime.now(timezone.utc)
        local = False
    if len(crudo) < (10 if len(sys.argv) > 1 else 100):
        print("[!] La lista de jugadores es demasiado corta: no se guarda nada.")
        sys.exit(1)

    jugadores = [limpiar(p) for p in crudo]
    gw = ultima_jornada_cerrada()
    try:
        from zoneinfo import ZoneInfo
        hoy = ahora.astimezone(ZoneInfo("Europe/Madrid")).strftime("%Y-%m-%d")
    except Exception:
        hoy = ahora.strftime("%Y-%m-%d")

    # --- memoria acumulada ---
    h = cargar(F_HIST, {"puntos": {}, "valor": {}})
    puntos, valor = h.setdefault("puntos", {}), h.setdefault("valor", {})
    nuevos = 0
    for j in jugadores:
        if gw is not None and j["streak"]:
            n = len(j["streak"])
            pj = puntos.setdefault(j["id"], {})
            for i, v in enumerate(j["streak"]):
                g = str(gw - (n - 1 - i))
                if int(g) < 1:
                    continue
                dato = v if isinstance(v, (int, float)) else None     # None = no jugó
                if g not in pj:
                    nuevos += 1
                pj[g] = dato
        if j["value"]:
            vj = valor.setdefault(j["id"], {})
            vj[hoy] = j["value"]
            for d in sorted(vj)[:-DIAS_VALOR]:
                del vj[d]
    h["actualizado"] = hoy
    h["ultimaJornada"] = gw

    salida = {"updated": hoy, "updatedAt": ahora.isoformat(timespec="seconds"), "ultimaJornada": gw,
              "total": len(jugadores), "jugadores": jugadores}
    if local:
        print(f"(prueba) {len(jugadores)} jugadores leídos; no se escribe nada.")
        print(f"   última jornada cerrada según el calendario: {gw}; puntos nuevos para el historial: {nuevos}")
        return
    with open(F_JUG, "w", encoding="utf-8") as f:
        json.dump(salida, f, ensure_ascii=False, separators=(",", ":"))
    with open(F_HIST, "w", encoding="utf-8") as f:
        json.dump(h, f, ensure_ascii=False, separators=(",", ":"))
    print(f"Jugadores: {len(jugadores)} guardados; {nuevos} puntos nuevos en el historial (jornada {gw}).")


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
    if not os.environ.get("GITHUB_ACTIONS") and len(sys.argv) == 1:
        try:
            input("\nPresiona ENTER para cerrar la ventana...")
        except (EOFError, RuntimeError, OSError):
            time.sleep(60)
    sys.exit(codigo)
