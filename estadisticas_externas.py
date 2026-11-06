#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ESTADÍSTICAS EXTERNAS DE LALIGA (para el modelo de puntos)

Mister puntúa con SofaScore: la nota de cada jugador en el partido, más los goles según la posición. Para
predecir esa nota hace falta saber lo que hace cada jugador en el campo y cómo se espera que vaya el partido.
Este script reúne, sin credenciales y con pausa entre peticiones (y solo si el robots.txt de cada web lo permite):

  · SofaScore: por partido, la nota y las estadísticas de cada jugador (minutos, xG, xA, tiros, pases clave,
    entradas, despejes, paradas...) y las cuotas de los partidos que faltan.
  · Understat: xG y xA de cada jugador y de cada equipo, partido a partido.
  · football-data.co.uk: resultados y cuotas de cierre (Pinnacle / Bet365 / media) de toda la temporada y de los
    próximos partidos.

Cada fuente es independiente: si una falla, las demás se guardan igual. Lo ya descargado se guarda en externo/
y solo se piden los partidos nuevos.

Uso:  python estadisticas_externas.py            (todo)
      python estadisticas_externas.py sofascore  (solo una fuente: sofascore, understat o cuotas)
"""
import csv
import io
import json
import os
import re
import sys
import time
import urllib.robotparser
from datetime import datetime, timezone

import requests

CARPETA = os.path.dirname(os.path.abspath(__file__))
EXT = os.path.join(CARPETA, "externo")
UA_BOT = "GolometroBot"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
PAUSA = 1.5
TEMPORADA_UNDERSTAT = "2026"          # Understat nombra la temporada 2026/27 como 2026
TEMPORADA_FD = "2627"                 # football-data.co.uk: 2026/27

sesion = requests.Session()
sesion.headers.update({"User-Agent": UA, "Accept-Language": "es-ES,es;q=0.9,en;q=0.8"})
_robots = {}
estado = {}


def log(*a):
    print(*a, flush=True)


def permitido(url):
    """Respeta el robots.txt de cada web (si no se puede leer, se asume permitido, como hacen los navegadores)."""
    m = re.match(r"(https?://[^/]+)", url)
    base = m.group(1)
    if base not in _robots:
        rp = urllib.robotparser.RobotFileParser()
        try:
            r = sesion.get(base + "/robots.txt", timeout=20)
            if r.status_code == 200:
                rp.parse(r.text.splitlines())
            else:
                rp.parse([])
        except requests.RequestException:
            rp.parse([])
        _robots[base] = rp
    return _robots[base].can_fetch(UA_BOT, url)


def pedir(url, json_=True, cab=None, intentos=2):
    if not permitido(url):
        log(f"  robots.txt no permite {url}: se omite")
        return None
    for i in range(intentos):
        try:
            r = sesion.get(url, timeout=30, headers=cab or {})
            time.sleep(PAUSA)
            if r.status_code == 200:
                return r.json() if json_ else r.text
            log(f"  HTTP {r.status_code} en {url}")
            if r.status_code in (403, 404, 429):
                return None
        except (requests.RequestException, ValueError) as e:
            log(f"  error en {url}: {type(e).__name__}")
            time.sleep(PAUSA * 2)
    return None


def cargar(nombre, defecto):
    try:
        with open(os.path.join(EXT, nombre), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return defecto


def guardar(nombre, datos):
    os.makedirs(EXT, exist_ok=True)
    with open(os.path.join(EXT, nombre), "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, separators=(",", ":"))


# ------------------------------------------------------------------ SofaScore
SOFA = "https://api.sofascore.com/api/v1"
SOFA_TORNEO = 8      # LaLiga
SOFA_CAMPOS = ["rating", "minutesPlayed", "goals", "goalAssist", "expectedGoals", "expectedAssists", "totalShots",
               "onTargetScoringAttempt", "keyPass", "bigChanceCreated", "bigChanceMissed", "totalPass", "accuratePass",
               "touches", "totalTackle", "interceptionWon", "totalClearance", "outfielderBlock", "duelWon", "duelLost",
               "wasFouled", "fouls", "dispossessed", "possessionLostCtrl", "saves", "goalsPrevented", "punches",
               "penaltyWon", "penaltyConceded", "penaltyMiss", "penaltySave", "errorLeadToAGoal", "ownGoals",
               "yellowCard", "redCard", "totalContest", "wonContest", "totalCross", "accurateCross", "aerialWon"]


def sofascore():
    cache = cargar("sofascore.json", {"temporada": None, "partidos": {}, "proximos": {}})
    t = pedir(f"{SOFA}/unique-tournament/{SOFA_TORNEO}/seasons")
    if not t or not t.get("seasons"):
        estado["sofascore"] = "sin acceso"
        return
    temp = t["seasons"][0]
    sid = temp["id"]
    if cache.get("temporada") != sid:
        cache = {"temporada": sid, "nombre": temp.get("name"), "partidos": {}, "proximos": {}}
    rondas = pedir(f"{SOFA}/unique-tournament/{SOFA_TORNEO}/season/{sid}/rounds") or {}
    actual = (rondas.get("currentRound") or {}).get("round") or 1
    nuevos, proximos = 0, {}
    for rnd in range(1, actual + 2):
        ev = pedir(f"{SOFA}/unique-tournament/{SOFA_TORNEO}/season/{sid}/events/round/{rnd}")
        for e in (ev or {}).get("events", []):
            eid = str(e["id"])
            fin = (e.get("status") or {}).get("type") == "finished"
            info = {"ronda": rnd, "ts": e.get("startTimestamp"), "local": e["homeTeam"]["name"], "visitante": e["awayTeam"]["name"],
                    "localId": e["homeTeam"]["id"], "visitanteId": e["awayTeam"]["id"]}
            if fin and eid not in cache["partidos"]:
                lu = pedir(f"{SOFA}/event/{eid}/lineups")
                if not lu:
                    continue
                jug = []
                for lado in ("home", "away"):
                    for p in (lu.get(lado) or {}).get("players", []):
                        s = p.get("statistics") or {}
                        if not s:
                            continue
                        fila = {"id": p["player"]["id"], "n": p["player"].get("name"), "lado": lado[0],
                                "pos": p.get("position") or p["player"].get("position"), "sup": bool(p.get("substitute"))}
                        fila.update({k: s[k] for k in SOFA_CAMPOS if k in s})
                        jug.append(fila)
                info.update({"gl": (e.get("homeScore") or {}).get("current"), "gv": (e.get("awayScore") or {}).get("current"),
                             "jugadores": jug})
                cache["partidos"][eid] = info
                nuevos += 1
            elif not fin and (e.get("status") or {}).get("type") == "notstarted":
                od = pedir(f"{SOFA}/event/{eid}/odds/1/all")
                info["cuotas"] = resumen_cuotas_sofa(od)
                proximos[eid] = info
    cache["proximos"] = proximos
    cache["actualizado"] = ahora()
    guardar("sofascore.json", cache)
    estado["sofascore"] = f"ok: {len(cache['partidos'])} partidos con notas ({nuevos} nuevos), {len(proximos)} próximos"


def fraccion(x):
    try:
        a, b = str(x).split("/")
        return 1 + float(a) / float(b)
    except (ValueError, ZeroDivisionError):
        return None


def resumen_cuotas_sofa(od):
    """1X2, más/menos 2,5 goles y ambos marcan, en cuota decimal."""
    out = {}
    for m in (od or {}).get("markets", []):
        nombre = (m.get("marketName") or "").lower()
        ch = {c.get("name"): fraccion(c.get("fractionalValue")) for c in m.get("choices", [])}
        if nombre == "full time":
            out["1x2"] = [ch.get("1"), ch.get("X"), ch.get("2")]
        elif nombre == "match goals" and str(m.get("choiceGroup")) == "2.5":
            out["ou25"] = [ch.get("Over"), ch.get("Under")]
        elif nombre == "both teams to score":
            out["btts"] = [ch.get("Yes"), ch.get("No")]
    return out


# ------------------------------------------------------------------ Understat
US = "https://understat.com"


def understat():
    cache = cargar("understat.json", {"temporada": TEMPORADA_UNDERSTAT, "partidos": {}, "jugadores": []})
    cab = {"X-Requested-With": "XMLHttpRequest", "Referer": f"{US}/league/La_liga/{TEMPORADA_UNDERSTAT}"}
    liga = pedir(f"{US}/getLeagueData/La_liga/{TEMPORADA_UNDERSTAT}", cab=cab)
    if not liga:   # versión antigua: los datos van dentro del HTML
        html = pedir(f"{US}/league/La_liga/{TEMPORADA_UNDERSTAT}", json_=False)
        liga = {}
        for k in ("datesData", "playersData", "teamsData"):
            m = re.search(k + r"\s*=\s*JSON\.parse\('(.*?)'\)", html or "")
            if m:
                liga[k.replace("Data", "")] = json.loads(m.group(1).encode().decode("unicode_escape"))
    fechas = liga.get("dates") or []
    if not fechas:
        estado["understat"] = "sin acceso"
        return
    cache["jugadores"] = liga.get("players") or cache.get("jugadores", [])
    nuevos = 0
    for d in fechas:
        mid = str(d.get("id"))
        if not d.get("isResult") or mid in cache["partidos"]:
            continue
        md = pedir(f"{US}/getMatchData/{mid}", cab={**cab, "Referer": f"{US}/match/{mid}"})
        if not md:
            continue
        ros = md.get("rosters") or {}
        jug = []
        for lado in ("h", "a"):
            for r in (ros.get(lado) or {}).values():
                jug.append({k: r.get(k) for k in ("player_id", "player", "position", "time", "goals", "own_goals", "shots", "xG",
                                                  "assists", "key_passes", "xA", "xGChain", "xGBuildup", "yellow_card", "red_card")} | {"lado": lado})
        cache["partidos"][mid] = {"fecha": d.get("datetime"), "local": d["h"]["title"], "visitante": d["a"]["title"],
                                  "gl": d["goals"]["h"], "gv": d["goals"]["a"], "xgl": d["xG"]["h"], "xgv": d["xG"]["a"], "jugadores": jug}
        nuevos += 1
    cache["actualizado"] = ahora()
    guardar("understat.json", cache)
    estado["understat"] = f"ok: {len(cache['partidos'])} partidos ({nuevos} nuevos), {len(cache['jugadores'])} jugadores"


# ------------------------------------------------------------------ football-data.co.uk (cuotas)
FD = "https://www.football-data.co.uk"
FD_COLS = ["Date", "Time", "HomeTeam", "AwayTeam", "FTHG", "FTAG", "HS", "AS", "HST", "AST", "HC", "AC",
           "B365H", "B365D", "B365A", "PSH", "PSD", "PSA", "AvgH", "AvgD", "AvgA", "B365>2.5", "B365<2.5", "P>2.5", "P<2.5",
           "Avg>2.5", "Avg<2.5", "AHh", "AvgAHH", "AvgAHA", "PSCH", "PSCD", "PSCA", "B365CH", "B365CD", "B365CA",
           "AvgCH", "AvgCD", "AvgCA", "PC>2.5", "PC<2.5", "AvgC>2.5", "AvgC<2.5"]


def filas_csv(txt, div=None):
    if not txt:
        return []
    txt = txt.lstrip("﻿")
    out = []
    for f in csv.DictReader(io.StringIO(txt)):
        if div and f.get("Div") != div:
            continue
        out.append({k: f.get(k) for k in FD_COLS if f.get(k) not in (None, "")})
    return out


def cuotas():
    jugados = filas_csv(pedir(f"{FD}/mmz4281/{TEMPORADA_FD}/SP1.csv", json_=False))
    proximos = filas_csv(pedir(f"{FD}/fixtures.csv", json_=False), div="SP1")
    if not jugados and not proximos:
        estado["cuotas"] = "sin acceso"
        return
    guardar("cuotas.json", {"actualizado": ahora(), "jugados": jugados, "proximos": proximos})
    estado["cuotas"] = f"ok: {len(jugados)} partidos jugados y {len(proximos)} próximos con cuotas"


def ahora():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def main():
    fuentes = {"sofascore": sofascore, "understat": understat, "cuotas": cuotas}
    pedidas = [a for a in sys.argv[1:] if a in fuentes] or list(fuentes)
    for nombre in pedidas:
        log(f"== {nombre}")
        try:
            fuentes[nombre]()
        except Exception as e:      # una fuente rota no tumba las demás
            estado[nombre] = f"error: {type(e).__name__}: {e}"[:200]
        log(f"   {estado.get(nombre)}")
    previo = cargar("estado.json", {})
    previo.update({k: {"estado": v, "fecha": ahora()} for k, v in estado.items()})
    guardar("estado.json", previo)
    return 0 if any(str(v).startswith("ok") for v in estado.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
