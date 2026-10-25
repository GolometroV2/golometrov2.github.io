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
    # efecto de la portería a cero en porteros y defensas (se mide con los partidos jugados)
    return out


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
