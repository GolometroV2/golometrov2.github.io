#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AUTOAJUSTE DEL RECOMENDADOR DE CAPITÁN

Cada vez que se ejecuta:
  1. Reconstruye, jornada a jornada, lo que el recomendador habría predicho usando SOLO datos anteriores
     a esa jornada (sin hacer trampa) y lo compara con los puntos reales de cada jugador.
  2. Recalibra los parámetros del modelo (sensibilidad al ataque/portería, localía, peso del rival, forma...)
     buscando los que menos se equivocan. El ajuste está limitado: con pocos datos se queda cerca de los
     valores por defecto y solo cambia si la mejora es clara.
  3. Extrae patrones de vuestra liga (efecto del resultado, de jugar en casa, rivales que más conceden...).
  4. Guarda todo en parametros_capitan.json, que la página lee para usar los parámetros nuevos y mostrar el
     panel "Aprendizaje".

No necesita credenciales de Mister: solo lee mister_fantasy_data.json, calendario.json y, si existe, equipos.json.
"""
import collections
import json
import math
import os
import statistics as st
import sys
from datetime import datetime, timezone

CARPETA = os.path.dirname(os.path.abspath(__file__))
F_DATOS = os.path.join(CARPETA, "mister_fantasy_data.json")
F_CAL = os.path.join(CARPETA, "calendario.json")
F_EQ = os.path.join(CARPETA, "equipos.json")
F_SALIDA = os.path.join(CARPETA, "parametros_capitan.json")

POS = ["PT", "DF", "MC", "DL"]
ATAQUE = {"PT": 0, "DF": 0.25, "MC": 0.7, "DL": 1}
PORTERIA = {"PT": 0.5, "DF": 0.8, "MC": 0.2, "DL": 0}
LIMITE_F = (0.55, 1.6)
GW_MIN_EVAL = 4          # primera jornada que se evalúa (antes no hay historial)
FILAS_MIN = 80           # con menos actuaciones evaluables no se toca nada
N0 = 300                 # cuanto mayor, más se parece el ajuste a los valores por defecto

# Mismos valores por defecto que CAP en golometro.html
DEFECTO = {"SENS_ATAQUE": 0.6, "SENS_CS": 0.2, "HOME_EXTRA": 0.04, "W_RIVAL": 0.75,
           "K_POS": 4, "K_JUGADOR": 4, "FORMA_ALPHA": 0.85, "F_SUPLENTE": 0.59}
REJILLAS = {"SENS_ATAQUE": [0.2, 0.4, 0.6, 0.8, 1.0], "SENS_CS": [0.0, 0.1, 0.2, 0.35, 0.5],
            "HOME_EXTRA": [0.0, 0.02, 0.04, 0.06, 0.08], "W_RIVAL": [0.0, 0.25, 0.5, 0.75, 1.0],
            "K_POS": [2, 4, 8], "K_JUGADOR": [2, 4, 6, 10], "FORMA_ALPHA": [0.6, 0.85, 1.0]}


def cargar(ruta, defecto=None):
    try:
        with open(ruta, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return defecto


def media(x):
    return sum(x) / len(x) if x else 0.0


def desv(x):
    if len(x) < 2:
        return 0.0
    m = media(x)
    return math.sqrt(sum((v - m) ** 2 for v in x) / len(x))


def corr(a, b):
    if len(a) < 3:
        return 0.0
    ma, mb = media(a), media(b)
    sa = math.sqrt(sum((x - ma) ** 2 for x in a))
    sb = math.sqrt(sum((y - mb) ** 2 for y in b))
    return sum((x - ma) * (y - mb) for x, y in zip(a, b)) / (sa * sb) if sa * sb else 0.0


# ---------------------------------------------------------------------------------------------
# Datos
# ---------------------------------------------------------------------------------------------
def construir_datos(D, C, E):
    equipo_de = {}
    for gid, eqs in (C.get("lineups") or {}).items():           # onces probables de la próxima jornada
        for tid, e in eqs.items():
            for pid in e["players"]:
                equipo_de[str(pid)] = int(tid)
    for mg in (E or {}).get("managers", []):                      # plantillas actuales
        for p in mg.get("players", []):
            if p.get("teamId") is not None:
                equipo_de[str(p["id"])] = int(p["teamId"])

    por_gw = collections.defaultdict(list)
    for g in C.get("games", []):
        por_gw[g["gw"]].append(g)

    def partido(gw, t):
        for g in por_gw[gw]:
            if g["home"] == t:
                return g, True, g["away"]
            if g["away"] == t:
                return g, False, g["home"]
        return None, None, None

    obs, vistos = [], set()
    for j in sorted(D["matchdays"], key=lambda x: int(x[1:])):
        gw = int(j[1:])
        for uid, u in D["matchdays"][j].items():
            for p in u.get("players", []):
                clave = (gw, p["id"])
                if clave in vistos:
                    continue
                vistos.add(clave)
                base = p["basePoints"] if p.get("captain") and p.get("basePoints") is not None else p.get("points")
                t = p.get("teamId") or equipo_de.get(str(p["id"]))
                g, casa, rival = partido(gw, t) if t else (None, None, None)
                obs.append({"gw": gw, "pid": str(p["id"]), "name": p.get("name"), "pos": p.get("pos"),
                            "pts": base if isinstance(base, (int, float)) else None,
                            "played": bool(p.get("played")), "minutes": p.get("minutes") or 0,
                            "team": t, "rival": rival, "casa": casa, "game": g,
                            "captain": bool(p.get("captain")), "uid": uid})
    nombres = {}
    for g in C.get("games", []):
        nombres[g["home"]] = g.get("homeName")
        nombres[g["away"]] = g.get("awayName")
    return obs, por_gw, nombres


class Modelo:
    """Predice los puntos de un jugador si juega, usando solo información anterior a su jornada."""

    def __init__(self, obs, C):
        self.jug = [o for o in obs if o["played"] and o["pts"] is not None]
        self.juegos = [g for g in C.get("games", []) if g.get("gh") is not None]
        self.hist = collections.defaultdict(list)
        for o in self.jug:
            self.hist[o["pid"]].append(o)
        self._eq = {}
        self._pos = {}

    def equipos(self, gw):
        if gw in self._eq:
            return self._eq[gw]
        jg = [g for g in self.juegos if g["gw"] < gw]
        T = collections.defaultdict(lambda: [0, 0, 0])
        sh = sa = 0
        for g in jg:
            for t, gf, ga in ((g["home"], g["gh"], g["ga"]), (g["away"], g["ga"], g["gh"])):
                T[t][0] += gf
                T[t][1] += ga
                T[t][2] += 1
            sh += g["gh"]
            sa += g["ga"]
        N = max(len(jg), 1)
        lg = (sh + sa) / (2 * N) or 1.3
        hf, af = (sh / N) / lg or 1.1, (sa / N) / lg or 0.9

        def f(t):
            x = T[t]
            return ((x[0] + 4 * lg) / (x[2] + 4)) / lg, ((x[1] + 4 * lg) / (x[2] + 4)) / lg

        def xg(a, b, casa):
            return lg * f(a)[0] * f(b)[1] * (hf if casa else af)

        p0 = []
        for g in [g for g in self.juegos if g["gw"] == gw]:
            p0 += [math.exp(-xg(g["home"], g["away"], True)), math.exp(-xg(g["away"], g["home"], False))]
        p0lg = media(p0) or math.exp(-lg)
        self._eq[gw] = (lg, xg, p0lg)
        return self._eq[gw]

    def mupos(self, gw, pos):
        k = (gw, pos)
        if k not in self._pos:
            x = [o["pts"] for o in self.jug if o["gw"] < gw and o["pos"] == pos]
            self._pos[k] = media(x) if len(x) >= 5 else {"PT": 4.8, "DF": 3.8, "MC": 4.3, "DL": 5.0}[pos]
        return self._pos[k]

    def prediccion(self, o, P, con_contexto=True):
        gw, pos = o["gw"], o["pos"]
        mu0 = self.mupos(gw, pos)
        h = [x for x in self.hist[o["pid"]] if x["gw"] < gw]
        racha = h[-5:]
        if racha:
            w = [P["FORMA_ALPHA"] ** (len(racha) - 1 - i) for i in range(len(racha))]
            forma = sum(wi * x["pts"] for wi, x in zip(w, racha)) / sum(w)
            crudo = 0.5 * forma + 0.5 * media([x["pts"] for x in h])
            n = min(len(h), 12)
            mu = (n * crudo + P["K_JUGADOR"] * mu0) / (n + P["K_JUGADOR"])
        else:
            mu = mu0
        if not con_contexto or not (o["team"] and o["game"]):
            return mu
        lg, xg, p0lg = self.equipos(gw)
        xa = xg(o["team"], o["rival"], o["casa"])
        xb = xg(o["rival"], o["team"], not o["casa"])
        fxg = (1 + (P["HOME_EXTRA"] if o["casa"] else -P["HOME_EXTRA"]) + ATAQUE[pos] * P["SENS_ATAQUE"] * (xa / lg - 1)
               + PORTERIA[pos] * P["SENS_CS"] * (math.exp(-xb) / p0lg - 1))
        x = [q["pts"] for q in self.jug if q["gw"] < gw and q["pos"] == pos and q["rival"] == o["rival"]]
        fpts = ((sum(x) + P["K_POS"] * mu0) / (len(x) + P["K_POS"])) / mu0
        f = min(max(max(fxg, 0.3) * (1 + P["W_RIVAL"] * (fpts - 1)), LIMITE_F[0]), LIMITE_F[1])
        return mu * f


def rmse(modelo, filas, P, ctx=True):
    return math.sqrt(media([(modelo.prediccion(o, P, ctx) - o["pts"]) ** 2 for o in filas]))


def ajustar(modelo, filas):
    """Búsqueda coordenada a coordenada en rejillas pequeñas; después se encoge hacia los valores por defecto."""
    base = rmse(modelo, filas, DEFECTO)
    P = dict(DEFECTO)
    mejor = base
    for _ in range(2):
        for k, rej in REJILLAS.items():
            for v in rej:
                Q = dict(P)
                Q[k] = v
                r = rmse(modelo, filas, Q)
                if r < mejor - 1e-9:
                    mejor, P = r, Q
    lam = len(filas) / (len(filas) + N0)
    final = {}
    for k in REJILLAS:
        v = DEFECTO[k] + lam * (P[k] - DEFECTO[k])
        final[k] = round(v) if k.startswith("K_") else round(v, 3)
    r_final = rmse(modelo, filas, {**DEFECTO, **final})
    if r_final > base * 0.995:       # mejora menor del 0,5 %: no merece la pena tocar nada
        return dict(DEFECTO), base, base, False
    return {**DEFECTO, **final}, base, r_final, True


# ---------------------------------------------------------------------------------------------
# Patrones
# ---------------------------------------------------------------------------------------------
def patrones(obs, nombres, jug):
    res = {"posiciones": {}, "resultado": {}, "local": {}, "rivales": {}, "minutos": {}}
    for pos in POS:
        x = [o["pts"] for o in jug if o["pos"] == pos]
        if len(x) < 5:
            continue
        m, s = media(x), desv(x)
        res["posiciones"][pos] = {"n": len(x), "media": round(m, 2), "sd": round(s, 2),
                                  "asimetria": round(sum((v - m) ** 3 for v in x) / len(x) / s ** 3, 2) if s else 0,
                                  "pAlto": round(sum(v >= 9 for v in x) / len(x), 3),
                                  "pBajo": round(sum(v <= 1 for v in x) / len(x), 3),
                                  "pNeg": round(sum(v < 0 for v in x) / len(x), 3)}
        r = {"W": [], "D": [], "L": []}
        ca, fu, cs, nocs = [], [], [], []
        for o in jug:
            if o["pos"] != pos or not o["game"]:
                continue
            g = o["game"]
            gf, ga = (g["gh"], g["ga"]) if o["casa"] else (g["ga"], g["gh"])
            if gf is None:
                continue
            r["W" if gf > ga else "L" if gf < ga else "D"].append(o["pts"])
            (ca if o["casa"] else fu).append(o["pts"])
            (cs if ga == 0 else nocs).append(o["pts"])
        res["resultado"][pos] = {k: {"n": len(v), "media": round(media(v), 2)} for k, v in r.items()}
        res["resultado"][pos]["porteriaACero"] = {"n": len(cs), "media": round(media(cs), 2)}
        res["resultado"][pos]["encaja"] = {"n": len(nocs), "media": round(media(nocs), 2)}
        res["local"][pos] = {"casa": {"n": len(ca), "media": round(media(ca), 2)}, "fuera": {"n": len(fu), "media": round(media(fu), 2)}}
        # rivales que más y menos conceden a esta posición
        por_riv = collections.defaultdict(list)
        for o in jug:
            if o["pos"] == pos and o["rival"]:
                por_riv[o["rival"]].append(o["pts"])
        tabla = [(t, len(v), media(v)) for t, v in por_riv.items() if len(v) >= 4]
        tabla.sort(key=lambda z: -z[2])
        fmt = lambda z: {"equipo": nombres.get(z[0], str(z[0])), "n": z[1], "media": round(z[2], 2), "vsLiga": round(z[2] / m - 1, 3)}
        res["rivales"][pos] = {"conceden": [fmt(z) for z in tabla[:3] if z[2] > m],
                               "concedenPoco": [fmt(z) for z in tabla[::-1][:3] if z[2] < m]}
    mins = [(o["minutes"], o["pts"]) for o in jug]
    cortos = [p for mi, p in mins if mi < 60]
    largos = [p for mi, p in mins if mi >= 60]
    res["minutos"] = {"menos60": {"n": len(cortos), "media": round(media(cortos), 2)}, "mas60": {"n": len(largos), "media": round(media(largos), 2)}}
    return res


def validacion_fuera_de_muestra(modelo, filas):
    """Para cada jornada, ajusta con las anteriores y prueba en ella: error real del ajuste (sin hacer trampa)."""
    e_aj, e_def, n = [], [], 0
    for gw in sorted({o["gw"] for o in filas}):
        entrena = [o for o in filas if o["gw"] < gw]
        prueba = [o for o in filas if o["gw"] == gw]
        if len(entrena) < FILAS_MIN or not prueba:
            continue
        P, _, _, cambio = ajustar(modelo, entrena)
        e_aj += [(modelo.prediccion(o, P) - o["pts"]) ** 2 for o in prueba]
        e_def += [(modelo.prediccion(o, DEFECTO) - o["pts"]) ** 2 for o in prueba]
        n += len(prueba)
    if not n:
        return None
    return {"n": n, "rmseAjustado": round(math.sqrt(media(e_aj)), 3), "rmseDefecto": round(math.sqrt(media(e_def)), 3)}


def evaluar_jornadas(modelo, P, obs):
    """Por jornada: error del modelo frente a la media de la posición, y qué capitán habría elegido el modelo."""
    salida = []
    for gw in sorted({o["gw"] for o in obs if o["gw"] >= GW_MIN_EVAL}):
        filas = [o for o in modelo.jug if o["gw"] == gw and o["team"] and o["game"]]
        if len(filas) < 8:
            continue
        e_mod = math.sqrt(media([(modelo.prediccion(o, P) - o["pts"]) ** 2 for o in filas]))
        e_pos = math.sqrt(media([(modelo.mupos(gw, o["pos"]) - o["pts"]) ** 2 for o in filas]))
        pm, ph, pa, nlin = [], [], [], 0
        lineas = collections.defaultdict(list)
        for o in obs:
            if o["gw"] == gw:
                lineas[o["uid"]].append(o)
        for uid, L in lineas.items():
            cand = [o for o in L if o["team"] and o["game"]]
            hum = [o for o in L if o["captain"] and o["team"]]
            if len(cand) < 6 or not hum:
                continue
            real = lambda o: o["pts"] if (o["played"] and o["pts"] is not None) else 0
            top = max(cand, key=lambda o: modelo.prediccion(o, P))
            pm.append(real(top)); ph.append(real(hum[0])); pa.append(media([real(o) for o in cand])); nlin += 1
        salida.append({"gw": gw, "n": len(filas), "rmseModelo": round(e_mod, 2), "rmsePosicion": round(e_pos, 2),
                       "lineas": nlin, "capModelo": round(media(pm), 2) if pm else None,
                       "capHumano": round(media(ph), 2) if ph else None, "capAzar": round(media(pa), 2) if pa else None})
    return salida


def main():
    D, C = cargar(F_DATOS), cargar(F_CAL)
    if not D or not C or not C.get("games"):
        print("[!] Faltan mister_fantasy_data.json o calendario.json: no se hace nada.")
        sys.exit(0)
    E = cargar(F_EQ, {})
    obs, por_gw, nombres = construir_datos(D, C, E)
    modelo = Modelo(obs, C)
    jug = modelo.jug
    total, con_equipo = len(jug), sum(1 for o in jug if o["team"] and o["game"])
    filas = [o for o in jug if o["gw"] >= GW_MIN_EVAL and o["team"] and o["game"]]
    print(f"Actuaciones: {total} | con equipo conocido: {con_equipo} | evaluables (J{GW_MIN_EVAL}+): {len(filas)}")

    if len(filas) < FILAS_MIN:
        params, r0, r1, cambio = dict(DEFECTO), None, None, False
        aviso = f"Solo {len(filas)} actuaciones evaluables (se necesitan {FILAS_MIN}): se usan los parámetros por defecto."
    else:
        params, r0, r1, cambio = ajustar(modelo, filas)
        aviso = None if cambio else "Los parámetros por defecto ya son los mejores que se pueden justificar con los datos actuales."
        fuera = validacion_fuera_de_muestra(modelo, filas)
        if cambio and (not fuera or fuera["rmseAjustado"] > fuera["rmseDefecto"] * 0.998):
            # El ajuste solo mejora "mirando las respuestas": con jornadas que no ha visto no gana nada. Se descarta.
            params, cambio = dict(DEFECTO), False
            aviso = "El ajuste automático no mejora al probarlo en jornadas que no había visto: se mantienen los parámetros por defecto."
            P_descartado = True

    # suplentes: cuántos puntos hace quien juega menos de 60 minutos frente a la media
    cortos = [o["pts"] for o in jug if o["minutes"] < 60]
    if len(cortos) >= 40:
        lam = len(cortos) / (len(cortos) + 120)
        params["F_SUPLENTE"] = round(DEFECTO["F_SUPLENTE"] + lam * (media(cortos) / media([o["pts"] for o in jug]) - DEFECTO["F_SUPLENTE"]), 3)

    P = {**DEFECTO, **params}
    metricas = {"fueraDeMuestra": fuera if len(filas) >= FILAS_MIN else None}
    if filas:
        pos_base = math.sqrt(media([(modelo.mupos(o["gw"], o["pos"]) - o["pts"]) ** 2 for o in filas]))
        sin_ctx = rmse(modelo, filas, P, ctx=False)
        con_ctx = rmse(modelo, filas, P, ctx=True)
        corr_f = corr([modelo.prediccion(o, P, False) for o in filas], [o["pts"] for o in filas])
        corr_c = corr([modelo.prediccion(o, P, True) for o in filas], [o["pts"] for o in filas])
        metricas.update({"filas": len(filas), "rmsePosicion": round(pos_base, 3), "rmseForma": round(sin_ctx, 3), "rmseCompleto": round(con_ctx, 3),
                    "corrForma": round(corr_f, 3), "corrCompleto": round(corr_c, 3),
                    "rmseDefecto": round(r0, 3) if r0 else None, "rmseAjustado": round(r1, 3) if r1 else None})
        print(f"RMSE: posición {pos_base:.3f} | forma {sin_ctx:.3f} | forma+contexto {con_ctx:.3f} (corr {corr_f:.2f} -> {corr_c:.2f})")

    salida = {
        "updatedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "muestra": {"actuaciones": total, "conEquipo": con_equipo, "jornadas": sorted({o["gw"] for o in obs})[-1] if obs else 0},
        "aviso": aviso,
        "params": {k: v for k, v in P.items()},
        "metricas": metricas,
        "patrones": patrones(obs, nombres, jug),
        "jornadas": evaluar_jornadas(modelo, P, obs) if filas else [],
    }
    previo = cargar(F_SALIDA, {})
    sin_hora = lambda d: {k: v for k, v in d.items() if k != "updatedAt"}
    if sin_hora(salida) == sin_hora(previo):
        print("Sin cambios en el autoajuste.")
        return
    with open(F_SALIDA, "w", encoding="utf-8") as f:
        json.dump(salida, f, ensure_ascii=False, separators=(",", ":"))
    cambios = {k: (DEFECTO[k], P[k]) for k in P if k in DEFECTO and P[k] != DEFECTO[k]}
    print("parametros_capitan.json actualizado.", ("Parámetros cambiados: " + str(cambios)) if cambios else "Parámetros sin cambios.")


if __name__ == "__main__":
    main()
