#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MODELO DE LA LIGA ENTERA (v2)

Aprende de TODOS los jugadores (jugadores_historial.json), no solo de los que alineáis, y calcula dos cosas
que usan el recomendador de capitán y el de mercado:

  1) Probabilidad de jugar: regresión logística con las últimas jornadas del jugador (¿jugó los últimos partidos?,
     ¿cuántos?, racha de titularidades...), su valor (los titulares valen más) y su posición.
  2) Puntos esperados si juega, antes de mirar su forma: una recta por posición según su valor
     (un jugador de 15 M rinde más que uno de 1 M).

También mide, mirando solo datos anteriores a cada jornada, cuánto mejoran frente a las fórmulas anteriores.
No necesita librerías externas.
"""

import collections
import json
import math
import os

POS = ["PT", "DF", "MC", "DL"]
NOMBRES = ["r_all", "r2", "r1", "n", "pts_medios", "log_valor", "racha", "DF", "MC", "DL"]
GW_MIN = 6          # primera jornada que se usa para aprender (antes casi no hay historial)


def media(x):
    return sum(x) / len(x) if x else 0.0


def caracteristicas(streak, valor, pos):
    """streak: puntos de las últimas jornadas (None = no jugó). Es lo MISMO que calcula la página con la lista de Mister."""
    s = list(streak or [])[-5:]
    n = len(s)
    jugo = [x for x in s if x is not None]
    r_all = len(jugo) / n if n else 0.7
    ult2 = s[-2:]
    r2 = sum(1 for x in ult2 if x is not None) / len(ult2) if ult2 else 0.7
    r1 = (1.0 if s[-1] is not None else 0.0) if s else 0.7
    racha = 0
    for x in reversed(s):
        if x is None:
            break
        racha += 1
    return [r_all, r2, r1, n / 5, media(jugo) if jugo else 3.5, math.log10(max(valor or 1e5, 1e5)),
            racha / 5, 1.0 if pos == "DF" else 0.0, 1.0 if pos == "MC" else 0.0, 1.0 if pos == "DL" else 0.0]


def sigmoide(z):
    return 1 / (1 + math.exp(-max(-30, min(30, z))))


def resolver(A, b):
    """Resuelve A x = b (Gauss con pivote parcial)."""
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


def logistica(X, y, lam=1.0, iteraciones=25):
    """Regresión logística con penalización L2 (IRLS). El primer peso es la constante."""
    k = len(X[0]) + 1
    w = [0.0] * k
    for _ in range(iteraciones):
        H = [[0.0] * k for _ in range(k)]
        g = [0.0] * k
        for xi, yi in zip(X, y):
            v = [1.0] + xi
            p = sigmoide(sum(a * b for a, b in zip(w, v)))
            s = p * (1 - p) + 1e-9
            for i in range(k):
                g[i] += (p - yi) * v[i]
                vi = v[i] * s
                for j in range(i, k):
                    H[i][j] += vi * v[j]
        for i in range(k):
            for j in range(i):
                H[i][j] = H[j][i]
            if i > 0:
                H[i][i] += lam
                g[i] += lam * w[i]
        paso = resolver(H, g)
        w = [a - b for a, b in zip(w, paso)]
        if max(abs(b) for b in paso) < 1e-6:
            break
    return w


def probabilidad(w, car):
    return sigmoide(w[0] + sum(a * b for a, b in zip(w[1:], car)))


def recta(x, y, lam=0.0):
    """y = a x + b por mínimos cuadrados."""
    n = len(x)
    if n < 20:
        return None
    mx, my = media(x), media(y)
    sxx = sum((a - mx) ** 2 for a in x) + lam
    if sxx <= 0:
        return None
    a = sum((u - mx) * (v - my) for u, v in zip(x, y)) / sxx
    return [a, my - a * mx]


def construir(H, J, D=None):
    """Observaciones (jugador, jornada): pos, valor, puntos (None = no jugó) y puntos de las 5 jornadas anteriores."""
    jug = {p["id"]: p for p in (J or {}).get("jugadores", [])}
    pts = collections.defaultdict(dict)
    for pid, v in (H or {}).get("puntos", {}).items():
        for g, x in v.items():
            pts[pid][int(g)] = x
    if D:      # jornadas antiguas de los jugadores que vosotros alineasteis
        for j, us in (D.get("matchdays") or {}).items():
            gw = int(j[1:])
            for u in us.values():
                for p in u.get("players", []):
                    pid = str(p["id"])
                    b = p["basePoints"] if p.get("captain") and p.get("basePoints") is not None else p.get("points")
                    if gw in pts[pid]:
                        continue
                    if p.get("played") and isinstance(b, (int, float)):
                        pts[pid][gw] = b
                    elif p.get("played") is False:
                        pts[pid][gw] = None
    ultima = (J or {}).get("ultimaJornada")      # la jornada en curso aún no está cerrada: sus datos son parciales
    filas = []
    for pid, h in pts.items():
        p = jug.get(pid)
        if not p:
            continue
        for gw, x in h.items():
            if ultima is not None and gw > ultima:
                continue
            previas = [h[g] for g in range(gw - 5, gw) if g in h]
            filas.append({"pid": pid, "gw": gw, "pos": p["pos"], "valor": p["value"], "pts": x, "ant": previas})
    return filas


def ajustar(H, J, D=None):
    filas = [f for f in construir(H, J, D) if f["ant"]]
    gws = sorted({f["gw"] for f in filas if f["gw"] >= GW_MIN})
    out = {"muestra": len(filas), "jornadas": gws}
    if len(filas) < 300 or len(gws) < 2:
        out["aviso"] = "Todavía hay pocos datos de la liga entera para este modelo."
        return out

    def X_y(rows):
        return [caracteristicas(f["ant"], f["valor"], f["pos"]) for f in rows], [0.0 if f["pts"] is None else 1.0 for f in rows]

    # ---- validación hacia delante: cada jornada se predice con lo aprendido en las anteriores ----
    b_log, b_cur, b_tasa, b_cte = [], [], [], []
    e_val, e_pos, e_base = [], [], []
    for g in [x for x in gws if x >= GW_MIN + 1]:
        tr = [f for f in filas if f["gw"] < g]
        te = [f for f in filas if f["gw"] == g]
        if len(tr) < 300 or not te:
            continue
        X, y = X_y(tr)
        w = logistica(X, y)
        Xt, yt = X_y(te)
        cte = media(y)
        for xi, yi in zip(Xt, yt):
            b_log.append((probabilidad(w, xi) - yi) ** 2)
            b_cur.append((min(1, max(0, 0.1 + 0.8 * (0.4 * xi[1] + 0.6 * xi[0]))) - yi) ** 2)
            b_tasa.append((min(0.98, max(0.02, xi[0])) - yi) ** 2)
            b_cte.append((cte - yi) ** 2)
        # puntos al jugar: recta por valor frente a media de la posición
        for pos in POS:
            jt = [f for f in tr if f["pos"] == pos and f["pts"] is not None]
            r = recta([math.log10(max(f["valor"] or 1e5, 1e5)) for f in jt], [f["pts"] for f in jt])
            m = media([f["pts"] for f in jt])
            for f in te:
                if f["pos"] != pos or f["pts"] is None:
                    continue
                pred = r[0] * math.log10(max(f["valor"] or 1e5, 1e5)) + r[1] if r else m
                e_val.append((pred - f["pts"]) ** 2)
                e_pos.append((m - f["pts"]) ** 2)
    if b_log:
        out["validacion"] = {
            "brierLogistica": round(media(b_log), 4), "brierFormulaAnterior": round(media(b_cur), 4),
            "brierTasaPropia": round(media(b_tasa), 4), "brierConstante": round(media(b_cte), 4),
            "rmsePriorValor": round(math.sqrt(media(e_val)), 3), "rmseMediaPosicion": round(math.sqrt(media(e_pos)), 3),
            "n": len(b_log)}

    # ---- ajuste final con todo lo disponible ----
    X, y = X_y(filas)
    w = logistica(X, y)
    out["juega"] = {"nombres": NOMBRES, "pesos": [round(a, 4) for a in w]}
    prior = {}
    for pos in POS:
        jt = [f for f in filas if f["pos"] == pos and f["pts"] is not None]
        r = recta([math.log10(max(f["valor"] or 1e5, 1e5)) for f in jt], [f["pts"] for f in jt])
        prior[pos] = [round(r[0], 4), round(r[1], 4)] if r else None
    out["priorValor"] = prior
    out["valorDin"] = valor_dinamica(J, H)
    try:
        out["factores"] = factores(H, J, D, cargar(os.path.join(os.path.dirname(os.path.abspath(__file__)), "calendario.json")))
    except Exception as e:      # el análisis de factores nunca debe romper el modelo
        out["factores"] = None
        print(f"[!] Análisis de factores no disponible: {e}")
    try:
        out["partido"] = modelo_partido(H, J, cargar(os.path.join(os.path.dirname(os.path.abspath(__file__)), "calendario.json")))
    except Exception as e:      # tampoco el modelo de partido
        out["partido"] = None
        print(f"[!] Modelo de partido no disponible: {e}")
    return out


# ---------------------------------------------------------------------------------------------
# Cómo cambia el valor de un jugador cada día
# ---------------------------------------------------------------------------------------------
V_NOMBRES = ["const", "media", "pts_ultima", "jugo_ultima", "log_valor", "lesion", "con_dueno", "pts_medios_5", "cambio_ayer"]
V_CORTE = 1_000_000      # por debajo de 1 M el valor se mueve al azar (±12 % al día) y no se puede predecir
V_CLIP = 0.10


def car_valor(p):
    s = [x for x in (p.get("streak") or [])][-5:]
    jug = [x for x in s if isinstance(x, (int, float))]
    ult = s[-1] if s and isinstance(s[-1], (int, float)) else None
    return [1.0, p.get("avg") or 0.0, float(ult or 0), 1.0 if ult is not None else 0.0,
            math.log10(max(p.get("value") or 1e5, 1e5)) - 6, 1.0 if p.get("status") == "injury" else 0.0,
            1.0 if p.get("owner") else 0.0, media(jug) if jug else 0.0]


def ridge(X, y, lam=10.0):
    k = len(X[0])
    mu = [0.0] + [media([r[j] for r in X]) for j in range(1, k)]
    sd = [1.0] + [(media([(r[j] - mu[j]) ** 2 for r in X]) ** 0.5) or 1.0 for j in range(1, k)]
    Z = [[(r[j] - mu[j]) / sd[j] if j else 1.0 for j in range(k)] for r in X]
    A = [[sum(z[i] * z[j] for z in Z) + (lam if i == j and i else 0.0) for j in range(k)] for i in range(k)]
    b = [sum(z[i] * t for z, t in zip(Z, y)) for i in range(k)]
    w = resolver(A, b)
    return w, mu, sd


def valor_dinamica(J, H):
    """Cambio diario del valor (%) en función de la media, la última jornada, el valor, si está lesionado, si tiene dueño
    y, sobre todo, de cuánto cambió el día anterior: en Mister el valor tiene mucha inercia (medido el 05/11: el cambio de
    hoy se parece un 95 % al de ayer y la inercia se va perdiendo un 6 % por día)."""
    from datetime import date
    jug = (J or {}).get("jugadores", [])
    por_id = {p["id"]: p for p in jug}
    hv = (H or {}).get("valor", {})
    filas, pares = [], {k: [] for k in range(1, 5)}
    for pid, serie in hv.items():
        p = por_id.get(pid)
        if not p:
            continue
        ds = sorted(serie)
        cambios = {}
        for a, b in zip(ds[:-1], ds[1:]):
            try:
                dt = (date.fromisoformat(b) - date.fromisoformat(a)).days
            except ValueError:
                continue
            if dt == 1 and serie[a]:
                cambios[b] = max(-V_CLIP, min(V_CLIP, serie[b] / serie[a] - 1))
        for b, y in cambios.items():
            ayer = (date.fromisoformat(b) - __import__("datetime").timedelta(days=1)).isoformat()
            if ayer in cambios:
                filas.append((car_valor(p) + [cambios[ayer]], y, serie[b]))
            if serie[b] >= V_CORTE:     # inercia a varios días (para prever hasta el partido)
                for k in pares:
                    d2 = (date.fromisoformat(b) + __import__("datetime").timedelta(days=k)).isoformat()
                    if d2 in cambios:
                        pares[k].append((y, cambios[d2]))
    # pendiente del cambio k días después frente al de hoy -> factor de inercia por día (phi)
    pend = {}
    for k, v in pares.items():
        if len(v) >= 50:
            mx, my = media([a for a, _ in v]), media([b for _, b in v])
            den = sum((a - mx) ** 2 for a, _ in v)
            if den > 0:
                pend[k] = sum((a - mx) * (b - my) for a, b in v) / den
    phis = [pend[k] ** (1 / k) for k in pend if pend[k] > 0]
    alto = [f for f in filas if f[2] >= V_CORTE]
    bajo = [f for f in filas if f[2] < V_CORTE]
    out = {"n": len(filas), "corte": V_CORTE, "bajo": round(media([f[1] for f in bajo]), 4) if bajo else 0.0}
    if len(alto) < 60:
        out["aviso"] = "Pocos datos para modelar el valor."
        return out
    # validación cruzada en 5 grupos (sin hacer trampa)
    idx = list(range(len(alto)))
    import random
    random.Random(7).shuffle(idx)
    pred = [0.0] * len(alto)
    for k in range(5):
        test = set(idx[k::5])
        tr = [alto[i] for i in idx if i not in test]
        w, mu, sd = ridge([f[0] for f in tr], [f[1] for f in tr])
        for i in test:
            z = [alto[i][0][j] if j == 0 else (alto[i][0][j] - mu[j]) / sd[j] for j in range(len(w))]
            z[0] = 1.0
            pred[i] = sum(a * b for a, b in zip(w, z))
    y = [f[1] for f in alto]
    my = media(y)
    sst = sum((v - my) ** 2 for v in y)
    sse = sum((v - p) ** 2 for v, p in zip(y, pred))
    out["r2"] = round(1 - sse / sst, 3) if sst else None
    w, mu, sd = ridge([f[0] for f in alto], y)
    out["nombres"] = V_NOMBRES
    out["pesos"] = [round(a, 5) for a in w]
    out["medias"] = [round(a, 5) for a in mu]
    out["desv"] = [round(a, 5) for a in sd]
    out["nAlto"] = len(alto)
    if phis:
        out["phi"] = round(max(0.5, min(0.99, media(phis))), 3)
        out["inercia"] = {str(k): round(v, 3) for k, v in pend.items()}
    return out



# ---------------------------------------------------------------------------------------------
# Qué decide los puntos (análisis de factores) y cómo se mueven juntos los jugadores de un mismo partido
# ---------------------------------------------------------------------------------------------
def _ols(X, y):
    """Mínimos cuadrados con constante: devuelve (pesos, R²)."""
    k = len(X[0]) + 1
    Z = [[1.0] + r for r in X]
    A = [[sum(z[i] * z[j] for z in Z) for j in range(k)] for i in range(k)]
    b = [sum(z[i] * t for z, t in zip(Z, y)) for i in range(k)]
    w = resolver(A, b)
    my = media(y)
    pred = [sum(a * c for a, c in zip(w, z)) for z in Z]
    sst = sum((v - my) ** 2 for v in y)
    sse = sum((v - q) ** 2 for v, q in zip(y, pred))
    return w, (1 - sse / sst) if sst else 0.0


def _corr(a, b):
    ma, mb = media(a), media(b)
    sa = sum((x - ma) ** 2 for x in a) ** 0.5
    sb = sum((x - mb) ** 2 for x in b) ** 0.5
    return sum((x - ma) * (y - mb) for x, y in zip(a, b)) / (sa * sb) if sa and sb else 0.0


def factores(H, J, D, C):
    """Mide, solo con datos anteriores a cada jornada, cuánto explica cada factor de los puntos de un jugador que juega:
       · su nivel (media de la temporada encogida hacia lo que se espera por su valor),
       · el partido (goles a favor y en contra: después del partido, cuánto explicaría saberlos; antes, cuánto se pueden prever),
       · los goles del propio jugador (puntos por gol y parte de sus puntos que vienen de goles, con vuestros onces).
       Devuelve también la «correlación de partido» por posición que usa la simulación de la jornada: cuántos puntos sube o
       baja un jugador por cada gol de su equipo o del rival por encima de lo esperado."""
    jug = {p["id"]: p for p in (J or {}).get("jugadores", [])}
    ult = (J or {}).get("ultimaJornada") or 99
    games = (C or {}).get("games") or []
    porgw = collections.defaultdict(list)
    for g in games:
        porgw[g["gw"]].append(g)
    pts = collections.defaultdict(dict)
    for pid, v in (H or {}).get("puntos", {}).items():
        for g, x in v.items():
            pts[pid][int(g)] = x
    num = lambda x: isinstance(x, (int, float))
    filas = []
    for pid, h in pts.items():
        p = jug.get(pid)
        if not p:
            continue
        for gw, x in h.items():
            if not num(x) or gw > ult:
                continue
            g = next((q for q in porgw[gw] if p["teamId"] in (q["home"], q["away"]) and num(q.get("gh"))), None)
            if not g:
                continue
            casa = g["home"] == p["teamId"]
            filas.append({"pid": pid, "gw": gw, "pos": p["pos"], "team": p["teamId"], "riv": g["away"] if casa else g["home"],
                          "casa": casa, "pts": x, "valor": p["value"] or 1e5, "gf": g["gh"] if casa else g["ga"], "gc": g["ga"] if casa else g["gh"]})
    gws = sorted({f["gw"] for f in filas})
    prueba = [g for g in gws if g >= (gws[0] + 2 if gws else 99)]
    if len(filas) < 600 or len(prueba) < 2:
        return None

    def media_antes(pid, g):
        p = jug[pid]
        tot, avg = float(p.get("points") or 0), float(p.get("avg") or 0)
        n = round(tot / avg) if avg > 0 else 0
        for gw, x in pts[pid].items():
            if gw >= g and gw <= ult and num(x):
                tot -= x
                n -= 1
        return (tot / n if n > 0 else None), max(n, 0)

    res = collections.defaultdict(list)      # pos -> [(residuo, gf - λf, gc - λc)]
    niv_p, niv_y, lam_p, lam_y = [], [], [], []
    for g in prueba:
        tr = [f for f in filas if f["gw"] < g]
        pri = {}
        for pos in POS:
            jt = [f for f in tr if f["pos"] == pos]
            pri[pos] = recta([math.log10(max(f["valor"], 1e5)) for f in jt], [f["pts"] for f in jt])
        gs = [q for q in games if q["gw"] < g and num(q.get("gh"))]
        lg = media([q["gh"] + q["ga"] for q in gs]) / 2 if gs else 1.3
        gf_, ga_ = collections.defaultdict(list), collections.defaultdict(list)
        for q in gs:
            gf_[q["home"]].append(q["gh"]); ga_[q["home"]].append(q["ga"]); gf_[q["away"]].append(q["ga"]); ga_[q["away"]].append(q["gh"])
        att = lambda t: (sum(gf_[t]) + 4 * lg) / (len(gf_[t]) + 4) / lg
        dfn = lambda t: (sum(ga_[t]) + 4 * lg) / (len(ga_[t]) + 4) / lg
        for f in (x for x in filas if x["gw"] == g):
            r = pri[f["pos"]]
            prior = r[0] * math.log10(max(f["valor"], 1e5)) + r[1] if r else 4.0
            avg, n = media_antes(f["pid"], g)
            mu = prior if avg is None else (n * avg + 20 * prior) / (n + 20)
            lf = lg * att(f["team"]) * dfn(f["riv"]) * (1.1 if f["casa"] else 0.9)
            lc = lg * att(f["riv"]) * dfn(f["team"]) * (0.9 if f["casa"] else 1.1)
            niv_p.append(mu); niv_y.append(f["pts"]); lam_p.append(lf); lam_y.append(f["gf"])
            res[f["pos"]].append((f["pts"] - mu, f["gf"] - lf, f["gc"] - lc))
    corr = {}
    for pos in POS:
        L = res[pos]
        if len(L) < 60:
            continue
        w, r2 = _ols([[a[1], a[2]] for a in L], [a[0] for a in L])
        corr[pos] = {"gf": round(w[1], 3), "gc": round(w[2], 3), "r2": round(max(0.0, r2), 3), "n": len(L)}
    # goles del propio jugador (vuestros onces: Mister da goles y asistencias de cada actuación)
    goles = {}
    obs = []
    for j, us in ((D or {}).get("matchdays") or {}).items():
        for u in us.values():
            for p in u.get("players", []):
                b = p["basePoints"] if p.get("captain") and p.get("basePoints") is not None else p.get("points")
                if p.get("played") and num(b):
                    obs.append((p.get("pos"), b, p.get("goals") or 0, p.get("assists") or 0))
    for pos in POS:
        L = [o for o in obs if o[0] == pos]
        if len(L) < 40:
            continue
        w, r2 = _ols([[o[2], o[3]] for o in L], [o[1] for o in L])
        mp = media([o[1] for o in L])
        gpp = media([o[2] for o in L])
        goles[pos] = {"ptsGol": round(w[1], 2), "ptsAsist": round(w[2], 2), "golesPartido": round(gpp, 3),
                      "parteGoles": round(max(0.0, w[1] * gpp) / mp, 3) if mp > 0 else None, "r2": round(max(0.0, r2), 3), "n": len(L)}
    return {"n": len(niv_y), "jornadas": prueba, "nivelCorr": round(_corr(niv_p, niv_y), 3),
            "golesPrevistosCorr": round(_corr(lam_p, lam_y), 3), "correlacion": corr, "goles": goles}

# ---------------------------------------------------------------------------------------------
# Modelo de partido: cómo puntúa cada posición según los goles que marca y encaja su equipo
# ---------------------------------------------------------------------------------------------
GOLES_MAX = 4      # 0, 1, 2, 3 y «4 o más»
TRAMOS = {"0-1": (0, 1), "2": (2, 2), "3+": (3, 99)}
N_CUANTILES = 24


def modelo_partido(H, J, C, lam=8.0):
    """Con TODOS los jugadores de LaLiga que juegan, mide para cada posición:
         · efecto de los goles encajados por su equipo (0, 1, 2, 3, 4+) y de los marcados, en puntos por encima de su nivel
           (su media encogida hacia lo que se espera por su valor, calculada solo con jornadas anteriores),
         · cómo se reparten los puntos alrededor de eso (24 cuantiles del residuo), aparte cuando su equipo encaja 3 o más.
       La web lo combina con los goles esperados del partido (Poisson) para dar la media y el riesgo de cada jugador:
       un defensa que juega contra el Madrid tiene muchas más papeletas de encajar 3 y de acabar en negativo."""
    jug = {p["id"]: p for p in (J or {}).get("jugadores", [])}
    ult = (J or {}).get("ultimaJornada") or 99
    porgw = collections.defaultdict(list)
    for g in (C or {}).get("games") or []:
        if isinstance(g.get("gh"), (int, float)) and isinstance(g.get("ga"), (int, float)):
            porgw[g["gw"]].append(g)
    num = lambda x: isinstance(x, (int, float))
    pts = collections.defaultdict(dict)
    for pid, v in (H or {}).get("puntos", {}).items():
        for g, x in v.items():
            pts[pid][int(g)] = x
    filas = []
    for pid, h in pts.items():
        p = jug.get(pid)
        if not p:
            continue
        for gw, x in h.items():
            if not num(x) or gw > ult:
                continue
            g = next((q for q in porgw[gw] if p["teamId"] in (q["home"], q["away"])), None)
            if g:
                casa = g["home"] == p["teamId"]
                filas.append({"pid": pid, "gw": gw, "pos": p["pos"], "pts": x, "valor": p["value"] or 1e5,
                              "gf": g["gh"] if casa else g["ga"], "gc": g["ga"] if casa else g["gh"]})
    if len(filas) < 600:
        return None

    def media_antes(pid, g):
        p = jug[pid]
        tot, avg = float(p.get("points") or 0), float(p.get("avg") or 0)
        n = round(tot / avg) if avg > 0 else 0
        for gw, x in pts[pid].items():
            if gw >= g and gw <= ult and num(x):
                tot -= x
                n -= 1
        return (tot / n if n > 0 else None), max(n, 0)

    # nivel de cada jugador ANTES de cada jornada (como lo vería la web)
    for g in sorted({f["gw"] for f in filas}):
        tr = [f for f in filas if f["gw"] < g] or [f for f in filas if f["gw"] == g]
        pri = {pos: recta([math.log10(max(f["valor"], 1e5)) for f in tr if f["pos"] == pos], [f["pts"] for f in tr if f["pos"] == pos]) for pos in POS}
        for f in (x for x in filas if x["gw"] == g):
            r = pri[f["pos"]]
            prior = r[0] * math.log10(max(f["valor"], 1e5)) + r[1] if r else 4.0
            avg, n = media_antes(f["pid"], g)
            f["mu"] = prior if avg is None else (n * avg + 20 * prior) / (n + 20)

    out = {}
    for pos in POS:
        L = [f for f in filas if f["pos"] == pos]
        if len(L) < 100:
            continue
        cat = lambda x: min(int(x), GOLES_MAX)
        X = [[1.0] + [1.0 if cat(f["gc"]) == k else 0.0 for k in range(1, GOLES_MAX + 1)]
             + [1.0 if cat(f["gf"]) == j else 0.0 for j in range(1, GOLES_MAX + 1)] for f in L]
        y = [f["pts"] - f["mu"] for f in L]
        n = len(X[0])
        A = [[sum(r[i] * r[j] for r in X) + (lam if i == j and i > 0 else 0.0) for j in range(n)] for i in range(n)]
        b = [sum(r[i] * t for r, t in zip(X, y)) for i in range(n)]
        w = resolver(A, b)
        efc = [0.0] + w[1:GOLES_MAX + 1]
        eff = [0.0] + w[GOLES_MAX + 1:]
        res = [(t - (w[0] + efc[cat(f["gc"])] + eff[cat(f["gf"])]), f["gc"]) for f, t in zip(L, y)]
        cuant = lambda r: [round(r[min(len(r) - 1, int((i + 0.5) / N_CUANTILES * len(r)))], 2) for i in range(N_CUANTILES)]
        todos = sorted(r for r, _ in res)
        q = {}
        for nombre, (lo, hi) in TRAMOS.items():
            r = sorted(x for x, k in res if lo <= k <= hi)
            q[nombre] = cuant(r if len(r) >= 60 else todos)
        out[pos] = {"encajados": [round(x, 2) for x in efc], "marcados": [round(x, 2) for x in eff], "residuo": q, "n": len(L)}
    return out or None


def cargar(ruta, defecto=None):
    try:
        with open(ruta, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return defecto


if __name__ == "__main__":
    c = os.path.dirname(os.path.abspath(__file__))
    r = ajustar(cargar(os.path.join(c, "jugadores_historial.json")), cargar(os.path.join(c, "jugadores.json")),
                cargar(os.path.join(c, "mister_fantasy_data.json")))
    print(json.dumps(r, indent=1, ensure_ascii=False))
