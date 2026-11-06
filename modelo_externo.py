#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MODELO CON ESTADÍSTICAS EXTERNAS (SofaScore, Understat y cuotas)

Convierte lo que descarga estadisticas_externas.py (carpeta externo/) en estadisticas.json, con los identificadores
de Mister, para que la página lo use en el capitán, el mercado y la predicción:

  partidos[idMister]  = goles esperados de cada equipo según las casas de apuestas (lh, la) y su probabilidad de
                        portería a cero. Las cuotas resumen mucho más que los goles de 11 jornadas: lesiones, rotaciones,
                        nivel real de cada equipo...
  jugadores[idMister] = por partido jugado: minutos, goles, xG, asistencias, xA, tiros, pases clave y nota media de
                        SofaScore (la que usa Mister para puntuar), y su forma de los últimos 5.
  conversion          = cómo convierte Mister la nota de SofaScore en puntos en cada posición (se mide cruzando
                        las notas con los puntos de Mister de cada jugador y jornada).
  validacion          = si con xG y cuotas se predicen mejor los puntos que solo con la media (jornadas pasadas,
                        usando solo lo anterior a cada una). La página solo usa los ajustes por xG si mejoran.

Sin datos externos no hace nada (y la página sigue con su modelo propio).
"""
import glob
import json
import math
import os
import re
import unicodedata
from collections import defaultdict
from datetime import datetime, timezone

CARPETA = os.path.dirname(os.path.abspath(__file__))
EXT = os.path.join(CARPETA, "externo")
SALIDA = os.path.join(CARPETA, "estadisticas.json")

# nombres de equipo en SofaScore / Understat / football-data -> id de Mister
ALIAS = {
    1: ["athletic club", "athletic", "ath bilbao", "athletic bilbao"],
    2: ["atletico madrid", "atletico", "atl madrid", "ath madrid", "atletico de madrid"],
    3: ["barcelona", "fc barcelona"],
    4: ["real betis", "betis"],
    5: ["celta vigo", "celta", "rc celta"],
    6: ["deportivo la coruna", "deportivo", "dep a coruna", "deportivo da coruna", "la coruna", "rc deportivo"],
    8: ["espanyol", "rcd espanyol", "espanol"],
    9: ["getafe", "getafe cf"],
    12: ["levante", "levante ud"],
    13: ["malaga", "malaga cf"],
    14: ["rayo vallecano", "rayo"],
    15: ["real madrid"],
    16: ["real sociedad", "sociedad"],
    17: ["sevilla", "sevilla fc"],
    19: ["valencia", "valencia cf"],
    20: ["villarreal", "villarreal cf"],
    23: ["elche", "elche cf"],
    48: ["alaves", "deportivo alaves"],
    50: ["osasuna", "ca osasuna"],
    1490: ["racing santander", "racing de santander", "real racing club", "racing"],
}


def norm(s):
    s = unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


EQUIPO = {norm(a): t for t, l in ALIAS.items() for a in l}


def equipo(nombre):
    n = norm(nombre)
    if n in EQUIPO:
        return EQUIPO[n]
    for a, t in EQUIPO.items():
        if a and (a in n or n in a):
            return t
    return None


def cargar(ruta, defecto):
    try:
        with open(ruta, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return defecto


def num(x):
    try:
        v = float(x)
        return v if math.isfinite(v) else None
    except (TypeError, ValueError):
        return None


# ------------------------------------------------------------------ cuotas -> goles esperados
def pois(l, k):
    return math.exp(-l) * l ** k / math.factorial(k)


def probs(lh, la, n=10):
    ph = pd = pa = po = 0.0
    for i in range(n):
        for j in range(n):
            p = pois(lh, i) * pois(la, j)
            if i > j:
                ph += p
            elif i == j:
                pd += p
            else:
                pa += p
            if i + j > 2:
                po += p
    return ph, pd, pa, po


def lambdas(c1, cx, c2, over=None, under=None):
    """Goles esperados de local y visitante que mejor reproducen las cuotas (quitando el margen de la casa)."""
    if not (c1 and cx and c2):
        return None
    q = [1 / c1, 1 / cx, 1 / c2]
    s = sum(q)
    q = [x / s for x in q]
    po = None
    if over and under:
        o, u = 1 / over, 1 / under
        po = o / (o + u)
    mejor, err = None, 9
    for t10 in range(14, 46):            # total de goles 1,4 a 4,5
        tot = t10 / 10
        for d100 in range(-300, 301, 4):     # diferencia de goles
            d = d100 / 100
            lh, la = (tot + d) / 2, (tot - d) / 2
            if lh <= 0.05 or la <= 0.05:
                continue
            ph, pd, pa, pov = probs(lh, la)
            e = (ph - q[0]) ** 2 + (pd - q[1]) ** 2 + (pa - q[2]) ** 2 + (0.5 * (pov - po) ** 2 if po is not None else 0)
            if e < err:
                mejor, err = (lh, la), e
    return mejor


def cargar_sofa():
    """Lo descargado de SofaScore: un fichero por jornada en externo/sofascore/<temporada>/ (o el formato antiguo)."""
    act = cargar(os.path.join(EXT, "sofascore", "actual.json"), {})
    sid = act.get("temporada")
    if not sid:
        return cargar(os.path.join(EXT, "sofascore.json"), {})
    base = os.path.join(EXT, "sofascore", str(sid))
    partidos = {}
    for f in sorted(glob.glob(os.path.join(base, "ronda_*.json"))):
        partidos.update(cargar(f, {}))
    proximos = cargar(os.path.join(base, "proximos.json"), {}).get("partidos") or {}
    return {"temporada": sid, "partidos": partidos, "proximos": proximos}


def cuotas_por_partido(cal, sofa):
    """Para cada partido del calendario de Mister: goles esperados según las cuotas (SofaScore o football-data)."""
    out = {}
    juegos = cal.get("games") or []
    clave = {}
    for g in juegos:
        clave[(g["home"], g["away"])] = g
    for e in list((sofa.get("proximos") or {}).values()):
        c = e.get("cuotas") or {}
        x = c.get("1x2") or [None] * 3
        ou = c.get("ou25") or [None, None]
        lam = lambdas(*x, *ou)
        g = clave.get((equipo(e.get("local")), equipo(e.get("visitante"))))
        if lam and g:
            out[str(g["id"])] = {"lh": round(lam[0], 3), "la": round(lam[1], 3), "fuente": "SofaScore"}
    fd = cargar(os.path.join(EXT, "cuotas.json"), {})
    for f in (fd.get("proximos") or []) + (fd.get("jugados") or []):
        g = clave.get((equipo(f.get("HomeTeam")), equipo(f.get("AwayTeam"))))
        if not g or str(g["id"]) in out:
            continue
        # cierre de Pinnacle si lo hay; si no, la media del mercado
        trio = [num(f.get(k)) for k in ("PSCH", "PSCD", "PSCA")]
        if not all(trio):
            trio = [num(f.get(k)) for k in ("PSH", "PSD", "PSA")]
        if not all(trio):
            trio = [num(f.get(k)) for k in ("AvgH", "AvgD", "AvgA")]
        ou = [num(f.get("PC>2.5")) or num(f.get("P>2.5")) or num(f.get("Avg>2.5")), num(f.get("PC<2.5")) or num(f.get("P<2.5")) or num(f.get("Avg<2.5"))]
        lam = lambdas(*trio, *ou)
        if lam:
            out[str(g["id"])] = {"lh": round(lam[0], 3), "la": round(lam[1], 3), "fuente": "football-data"}
    for k, v in out.items():
        v["csh"] = round(math.exp(-v["la"]), 3)
        v["csa"] = round(math.exp(-v["lh"]), 3)
    return out


# ------------------------------------------------------------------ jugadores de SofaScore -> Mister
def emparejar_jugadores(sofa, J):
    """id de SofaScore -> id de Mister, por nombre y equipo."""
    mis = defaultdict(list)
    for p in J.get("jugadores", []):
        mis[int(p["teamId"])].append(p)
    out = {}
    for e in (sofa.get("partidos") or {}).values():
        for lado, nombre in (("h", e.get("local")), ("a", e.get("visitante"))):
            t = equipo(nombre)
            if t is None:
                continue
            for j in e.get("jugadores", []):
                if j.get("lado") != lado or j["id"] in out:
                    continue
                n = norm(j.get("n"))
                cand = [p for p in mis[t] if norm(p["name"]) == n]
                if not cand:
                    ap = n.split()[-1] if n else ""
                    cand = [p for p in mis[t] if ap and ap in norm(p["name"]).split()]
                    if len(cand) > 1:
                        ini = n[:1]
                        cand = [p for p in cand if norm(p["name"]).startswith(ini)] or cand
                if len(cand) == 1:
                    out[j["id"]] = cand[0]["id"]
    return out


def jugadores_sofa(sofa, mapa):
    """Resumen por jugador de Mister: partidos jugados con sus estadísticas, en orden de fecha."""
    filas = defaultdict(list)
    for e in sorted((sofa.get("partidos") or {}).values(), key=lambda x: x.get("ts") or 0):
        for j in e.get("jugadores", []):
            mid = mapa.get(j["id"])
            if not mid or not j.get("minutesPlayed"):
                continue
            filas[mid].append({"r": e.get("ronda"), "min": j.get("minutesPlayed"), "nota": num(j.get("rating")),
                               "g": j.get("goals") or 0, "xg": num(j.get("expectedGoals")) or 0.0, "a": j.get("goalAssist") or 0,
                               "xa": num(j.get("expectedAssists")) or 0.0, "tiros": j.get("totalShots") or 0, "pc": j.get("keyPass") or 0,
                               "tit": not j.get("sup")})
    out = {}
    for mid, L in filas.items():
        mins = sum(x["min"] for x in L)
        notas = [x["nota"] for x in L if x["nota"]]
        out[mid] = {"pj": len(L), "tit": sum(1 for x in L if x["tit"]), "min": mins,
                    "g": sum(x["g"] for x in L), "xg": round(sum(x["xg"] for x in L), 2), "a": sum(x["a"] for x in L),
                    "xa": round(sum(x["xa"] for x in L), 2), "tiros": sum(x["tiros"] for x in L), "pc": sum(x["pc"] for x in L),
                    "nota": round(sum(notas) / len(notas), 2) if notas else None,
                    "nota5": round(sum(notas[-5:]) / len(notas[-5:]), 2) if notas else None,
                    "rondas": [[x["r"], x["min"], x["nota"], x["g"], round(x["xg"], 2), x["a"], round(x["xa"], 2)] for x in L[-8:]]}
    return out, filas


def conversion(filas, H, J):
    """Puntos de Mister frente a la nota de SofaScore y los goles, por posición (recta por mínimos cuadrados)."""
    pos = {p["id"]: p["pos"] for p in J.get("jugadores", [])}
    pts = H.get("puntos", {})
    datos = defaultdict(list)
    for mid, L in filas.items():
        for x in L:
            v = (pts.get(mid) or {}).get(str(x["r"]))
            if isinstance(v, (int, float)) and x["nota"]:
                datos[pos.get(mid)].append((x["nota"], x["g"], x["a"], v))
    out = {}
    for p, L in datos.items():
        if not p or len(L) < 40:
            continue
        # pts = a + b·nota + c·goles + d·asist
        X = [[1, n, g, a] for n, g, a, _ in L]
        y = [v for *_, v in L]
        k = 4
        A = [[sum(r[i] * r[j] for r in X) for j in range(k)] for i in range(k)]
        b = [sum(r[i] * t for r, t in zip(X, y)) for i in range(k)]
        w = resolver(A, b)
        pred = [sum(a * c for a, c in zip(w, r)) for r in X]
        my = sum(y) / len(y)
        r2 = 1 - sum((u - q) ** 2 for u, q in zip(y, pred)) / max(sum((u - my) ** 2 for u in y), 1e-9)
        out[p] = {"cte": round(w[0], 2), "porNota": round(w[1], 2), "porGol": round(w[2], 2), "porAsist": round(w[3], 2), "r2": round(r2, 3), "n": len(L)}
    return out


def resolver(A, b):
    n = len(b)
    M = [fila[:] + [b[i]] for i, fila in enumerate(A)]
    for i in range(n):
        p = max(range(i, n), key=lambda r: abs(M[r][i]))
        M[i], M[p] = M[p], M[i]
        d = M[i][i] or 1e-12
        for j in range(i, n + 1):
            M[i][j] /= d
        for r in range(n):
            if r != i:
                f = M[r][i]
                for j in range(i, n + 1):
                    M[r][j] -= f * M[i][j]
    return [M[i][n] for i in range(n)]


def validar(filas, H, J, conv):
    """¿Predice mejor los puntos de la jornada siguiente la media + corrección por xG que la media sola?
       Para cada jugador y ronda r: media de puntos antes de r frente a esa media + (xG − goles + xA − asist) por partido
       × puntos por gol/asistencia de su posición, con distintos pesos."""
    pos = {p["id"]: p["pos"] for p in J.get("jugadores", [])}
    pts = H.get("puntos", {})
    res = {w: [] for w in (0.0, 0.25, 0.5, 0.75, 1.0)}
    for mid, L in filas.items():
        c = conv.get(pos.get(mid))
        if not c:
            continue
        for i in range(3, len(L)):
            y = (pts.get(mid) or {}).get(str(L[i]["r"]))
            if not isinstance(y, (int, float)):
                continue
            prev = [(pts.get(mid) or {}).get(str(x["r"])) for x in L[:i]]
            prev = [v for v in prev if isinstance(v, (int, float))]
            if len(prev) < 3:
                continue
            m = sum(prev) / len(prev)
            n = i
            dg = (sum(x["xg"] for x in L[:i]) - sum(x["g"] for x in L[:i])) / n
            da = (sum(x["xa"] for x in L[:i]) - sum(x["a"] for x in L[:i])) / n
            for w in res:
                res[w].append((m + w * (dg * c["porGol"] + da * c["porAsist"]) - y) ** 2)
    if not res[0.0]:
        return None
    rmse = {str(w): round(math.sqrt(sum(v) / len(v)), 4) for w, v in res.items()}
    mejor = min(res, key=lambda w: sum(res[w]))
    return {"n": len(res[0.0]), "rmsePorPeso": rmse, "pesoXg": mejor, "mejora": round(float(rmse["0.0"]) - float(rmse[str(mejor)]), 4)}


def main():
    cal = cargar(os.path.join(CARPETA, "calendario.json"), {})
    J = cargar(os.path.join(CARPETA, "jugadores.json"), {})
    H = cargar(os.path.join(CARPETA, "jugadores_historial.json"), {})
    sofa = cargar_sofa()
    partidos = cuotas_por_partido(cal, sofa)
    jug, conv, val = {}, {}, None
    if sofa.get("partidos") and J.get("jugadores"):
        mapa = emparejar_jugadores(sofa, J)
        jug, filas = jugadores_sofa(sofa, mapa)
        conv = conversion(filas, H, J)
        val = validar(filas, H, J, conv)
        print(f"SofaScore: {len(mapa)} jugadores emparejados con Mister, {len(jug)} con partidos; conversión nota->puntos: {conv}")
        if val:
            print(f"Validación xG: {val}")
    if not partidos and not jug:
        print("Sin estadísticas externas todavía: no se crea estadisticas.json")
        return 0
    out = {"updatedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "partidos": partidos, "jugadores": jug,
           "conversion": conv, "validacion": val}
    with open(SALIDA, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
    print(f"estadisticas.json: {len(partidos)} partidos con cuotas, {len(jug)} jugadores")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
