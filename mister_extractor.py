#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MISTER FANTASY PRO STATS - EXTRACTOR AUTOMÁTICO

Las credenciales NO van en el código. Crea un archivo llamado credenciales.env
en la misma carpeta que este script (una línea por variable, sin comillas):

MISTER_COOKIE=authenticated=true; PHPSESSID=...; token=...; refresh-token=...
X_AUTH_TOKEN=...

También puedes definirlas como variables de entorno de Windows.
"""

import hashlib
import json
import os
import re
import sys
import time
from datetime import datetime
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

CARPETA_SCRIPT = os.path.dirname(os.path.abspath(__file__))
URL_STANDINGS = "https://mister.mundodeportivo.com/standings"

# gw de una jornada que sabemos que existe (la del cURL). Desde su respuesta se lee
# el selector J1, J2, J3... con los gw reales de cada jornada.
GW_SEMILLA = 4044

# Solo se usa si no se consigue leer el selector de jornadas de la respuesta.
JORNADAS_RESPALDO = {2: 4043, 3: 4044}

URL_BASE = "https://mister.mundodeportivo.com"

# Goles encajados de un manager en una jornada:
#   "portero" -> goles que encajó su portero titular que jugó
#   "defensa" -> suma de los goles encajados por portero y defensas titulares que jugaron
GOLES_ENCAJADOS_MODO = "portero"

PAUSA_ENTRE_PETICIONES = 0.25
ARCHIVO_CACHE = os.path.join(CARPETA_SCRIPT, "cache_mister.json")
VERSION_CACHE = 2  # súbela cuando cambie cómo se calculan los datos de jugadores
POSICIONES = {1: "PT", 2: "DF", 3: "MC", 4: "DL"}

COLORES_AVATAR = ["#10b981", "#3b82f6", "#f59e0b", "#ef4444", "#8b5cf6", "#ec4899", "#06b6d4", "#84cc16"]


# --------------------------------------------------------------------------
# Credenciales
# --------------------------------------------------------------------------
def cargar_credenciales():
    valores = {}
    ruta_env = os.path.join(CARPETA_SCRIPT, "credenciales.env")
    if os.path.exists(ruta_env):
        with open(ruta_env, "r", encoding="utf-8") as f:
            for linea in f:
                linea = linea.strip()
                if not linea or linea.startswith("#") or "=" not in linea:
                    continue
                clave, valor = linea.split("=", 1)
                valores[clave.strip()] = valor.strip().strip('"').strip("'")

    cookie = valores.get("MISTER_COOKIE") or os.environ.get("MISTER_COOKIE", "")
    x_auth = valores.get("X_AUTH_TOKEN") or os.environ.get("X_AUTH_TOKEN", "")

    if not cookie or not x_auth:
        print("[!] Faltan credenciales.")
        print("    Crea 'credenciales.env' junto al script con las líneas:")
        print("    MISTER_COOKIE=...")
        print("    X_AUTH_TOKEN=...")
        input("\nPresiona ENTER para cerrar la ventana...")
        sys.exit(1)

    return cookie, x_auth


MISTER_COOKIE, X_AUTH_TOKEN = cargar_credenciales()

HEADERS = {
    "accept": "*/*",
    "accept-language": "es-ES,es;q=0.9,en;q=0.8",
    "origin": "https://mister.mundodeportivo.com",
    "partial-request": "true",
    "referer": "https://mister.mundodeportivo.com/standings",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/153.0.0.0 Safari/537.36",
    "x-auth": X_AUTH_TOKEN,
    "x-requested-with": "XMLHttpRequest",
    "cookie": MISTER_COOKIE,
}


# --------------------------------------------------------------------------
# Parseo
# --------------------------------------------------------------------------
def limpiar_numero(texto):
    if texto is None:
        return 0
    m = re.search(r"-?\d+", str(texto).replace(".", ""))
    return int(m.group(0)) if m else 0


def extraer_fila(li):
    """Convierte un <li> de usuario en un diccionario. Devuelve None si no es una fila de usuario."""
    enlace = li.select_one("a[href*='users/']")
    nombre_el = li.select_one(".name")
    pts_el = li.select_one(".points")
    if not enlace or not nombre_el or not pts_el:
        return None

    m = re.search(r"users/(\d+)", enlace["href"])
    if not m:
        return None

    # El número es texto directo de .points; el <span>Pts</span> y el <div class="diff"> se ignoran
    texto_pts = "".join(pts_el.find_all(string=True, recursive=False))

    pos_el = li.select_one(".position")

    plantilla = 0     # nº de jugadores en plantilla (lista general: "16 jugadores")
    jugados = None    # jugadores que puntuaron (lista de jornada: "9 / 11 Jugadores")
    valor = 0
    played_el = li.select_one(".played")
    if played_el:
        t = played_el.get_text(" ", strip=True)
        m_j = re.search(r"(\d+)\s*/\s*(\d+)", t)
        if m_j:
            jugados = int(m_j.group(1))
        else:
            m_p = re.search(r"(\d+)\s*jugadores", t, re.I)
            plantilla = int(m_p.group(1)) if m_p else 0
        m_v = re.search(r"€\s*([\d\.]+)", t)
        valor = int(m_v.group(1).replace(".", "")) if m_v else 0

    m_slug = re.search(r"users/\d+/([^/?#\"']+)", enlace["href"])

    return {
        "id": m.group(1),
        "slug": m_slug.group(1) if m_slug else "",
        "name": nombre_el.get_text(strip=True),
        "position": limpiar_numero(pos_el.get_text(strip=True)) if pos_el else 0,
        "points": limpiar_numero(texto_pts),
        "squadSize": plantilla,
        "playersPlayed": jugados,
        "squadValue": valor,
    }


def extraer_listas(html):
    """
    Devuelve las listas de usuarios de la respuesta, en orden de aparición:
    la primera es la clasificación GENERAL y la segunda la de la JORNADA.
    """
    soup = BeautifulSoup(html, "html.parser")
    listas = []
    for ul in soup.find_all("ul"):
        filas = []
        for li in ul.find_all("li"):
            if li.find_parent("ul") is not ul:
                continue
            fila = extraer_fila(li)
            if fila:
                filas.append(fila)
        if filas:
            listas.append(filas)

    if len(listas) >= 2:
        return listas

    # Respaldo: todas las filas seguidas; la segunda lista empieza donde se repite un id
    todas = [extraer_fila(li) for li in soup.find_all("li")]
    todas = [f for f in todas if f]
    vistos = set()
    for idx, f in enumerate(todas):
        if f["id"] in vistos:
            return [todas[:idx], todas[idx:]]
        vistos.add(f["id"])
    return [todas] if todas else []


def leer_selector_jornadas(html, gw_actual):
    """Lee el selector J1, J2, J3... y devuelve {numero_jornada: gw}."""
    soup = BeautifulSoup(html, "html.parser")
    cont = soup.select_one(".gameweek-selector-inline")
    mapa = {}
    if not cont:
        return mapa
    for el in cont.find_all(True):
        m = re.fullmatch(r"J(\d+)", el.get_text(strip=True))
        if not m:
            continue
        n = int(m.group(1))
        if el.name == "a":
            mg = re.search(r"gw=(\d+)", el.get("href", ""))
            if mg:
                mapa[n] = int(mg.group(1))
        elif el.find("a") is None and el.find_parent("a") is None:
            mapa.setdefault(n, gw_actual)  # elemento sin enlace = jornada seleccionada
    return mapa



# --------------------------------------------------------------------------
# Alineaciones y detalle de jugadores (goles, tarjetas...)
# --------------------------------------------------------------------------
class ErrorSesion(Exception):
    pass


_fallos = {"n": 0}
EVENTOS_VISTOS = set()


def post_ajax(session, ruta, datos, gw):
    headers = {k: v for k, v in HEADERS.items() if k != "partial-request"}
    headers["content-type"] = "application/x-www-form-urlencoded; charset=UTF-8"
    headers["referer"] = f"{URL_BASE}/standings?gw={gw}"
    try:
        resp = session.post(URL_BASE + ruta, data=datos, headers=headers, timeout=20)
        contenido = resp.json()
        ok = resp.status_code == 200 and contenido.get("status") == "ok"
    except Exception as e:
        print(f"      [!] Error en {ruta}: {e}")
        ok, contenido = False, {}

    if not ok:
        _fallos["n"] += 1
        if _fallos["n"] >= 5:
            raise ErrorSesion("5 peticiones seguidas han fallado")
        return None

    _fallos["n"] = 0
    time.sleep(PAUSA_ENTRE_PETICIONES)
    return contenido.get("data")


def valores(x):
    return list(x.values()) if isinstance(x, dict) else list(x or [])


def contar_evento(eventos, patron, alternativa):
    """Suma los 'count' de los eventos cuya clave encaje con el patrón; si no hay, usa la alternativa."""
    total, hallado = 0, False
    for clave, ev in eventos.items():
        if re.search(patron, clave, re.I):
            hallado = True
            total += int((ev or {}).get("count", 0) or 0)
    return total if hallado else alternativa


def compactar_detalle(d):
    """Del JSON de player-gameweek se queda con lo necesario."""
    eventos = d.get("events") or {}
    if isinstance(eventos, list):
        eventos = {}
    EVENTOS_VISTOS.update(eventos.keys())

    def cargar(campo):
        try:
            return json.loads(d.get(campo) or "{}")
        except (ValueError, TypeError):
            return {}

    stats = cargar("stats")
    det = cargar("marca_stats_rating_detailed")

    def v(clave):
        return (det.get(clave) or {}).get("value") or 0

    # Se toma el MAYOR valor entre las distintas fuentes: 'events' de Mister, las
    # estadísticas del proveedor y el detalle de Marca. Así no se pierden goles si
    # alguna fuente solo cuenta uno por jugador.
    ev_goles = contar_evento(eventos, r"^goal$", 0)
    st_goles = int(stats.get("goals", 0) or 0)
    dt_goles = int(v("goals"))
    goles = max(ev_goles, st_goles, dt_goles)
    if len({ev_goles, st_goles, dt_goles}) > 1:
        print(
            f"      [?] {d.get('name')} (gw {d.get('id_gameweek')}): goles distintos según la fuente "
            f"-> events={ev_goles}, stats={st_goles}, marca={dt_goles}. Se usa {goles}."
        )

    asist = max(contar_evento(eventos, r"assist", 0), int(stats.get("goalAssist", 0) or 0), int(v("goalAssist")))
    amarillas = max(contar_evento(eventos, r"^(?!.*double).*yellow", 0), int(v("yellowCard")))
    rojas = max(contar_evento(eventos, r"red|roja|double", 0), int(v("redCard") + v("doubleYellowCard")))

    # Goles encajados por el equipo del jugador en ese partido
    encajados = None
    try:
        eq, local, visit = d["match_team_id"], d["id_home"], d["id_away"]
        if eq == local:
            encajados = int(d["goals_away"])
        elif eq == visit:
            encajados = int(d["goals_home"])
    except (KeyError, TypeError, ValueError):
        pass
    if encajados is None:
        encajados = int(v("goalsAgainst"))

    return {
        "goals": int(goles),
        "assists": int(asist),
        "yellowCards": int(amarillas),
        "redCards": int(rojas),
        "ownGoals": int(stats.get("ownGoals", 0) or 0),
        "minutes": int(stats.get("minutesPlayed", 0) or 0),
        "goalsConceded": int(encajados),
    }


def cargar_cache():
    if os.path.exists(ARCHIVO_CACHE):
        try:
            with open(ARCHIVO_CACHE, "r", encoding="utf-8") as f:
                cache = json.load(f)
            if cache.get("_v") == VERSION_CACHE:
                return cache
            print("   Caché antigua descartada; se volverán a descargar los datos de jugadores.")
        except (ValueError, OSError):
            pass
    return {"_v": VERSION_CACHE}


def guardar_cache(cache):
    with open(ARCHIVO_CACHE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False)


def extra_manager(session, uid, slug, gw, cache):
    """Alineación de un manager en una jornada + goles, tarjetas y goles encajados."""
    clave_m = f"m:{uid}:{gw}"
    if clave_m in cache:
        return cache[clave_m]

    data = post_ajax(
        session, "/ajax/sw/users",
        {"post": "users", "id": uid, "slug": slug, "qs": f"gw={gw}", "comments": "0"}, gw,
    )
    if not data:
        return None

    cerrada = any(
        g.get("id") == gw and g.get("internalStatus") == "closed"
        for g in valores(data.get("gameWeeks"))
    )

    jugadores = []
    puntos_alineacion = 0
    for slots in valores((data.get("lineup") or {}).get("positions")):
        for p in valores(slots):
            pos_num = int(p.get("position", 0) or 0)
            pts = p.get("points")
            pts_num = pts if isinstance(pts, (int, float)) else None
            jugo = p.get("played") == 1
            if pts_num is not None:
                puntos_alineacion += pts_num

            extra = {"goals": 0, "assists": 0, "yellowCards": 0, "redCards": 0,
                     "ownGoals": 0, "minutes": 0, "goalsConceded": 0}
            if jugo:
                clave_p = f"p:{gw}:{p['id']}"
                if clave_p in cache:
                    extra = cache[clave_p]
                else:
                    det = post_ajax(
                        session, "/ajax/player-gameweek",
                        {"id_manager": uid, "id_gameweek": gw, "id_player": p["id"]}, gw,
                    )
                    if det:
                        extra = compactar_detalle(det)
                        if cerrada:
                            cache[clave_p] = extra

            jugadores.append({
                "id": p.get("id"),
                "name": p.get("name"),
                "pos": POSICIONES.get(pos_num, "?"),
                "points": pts_num,
                "captain": bool(p.get("captain")),
                "played": jugo,
                **extra,
            })

    goles_pos = {"PT": 0, "DF": 0, "MC": 0, "DL": 0}
    for j in jugadores:
        if j["pos"] in goles_pos:
            goles_pos[j["pos"]] += j["goals"]

    if GOLES_ENCAJADOS_MODO == "defensa":
        encajados = sum(j["goalsConceded"] for j in jugadores if j["played"] and j["pos"] in ("PT", "DF"))
    else:
        encajados = sum(j["goalsConceded"] for j in jugadores if j["played"] and j["pos"] == "PT")

    ugw = (data.get("userGameWeeks") or {}).get(str(gw)) or {}
    resultado = {
        "goals": sum(j["goals"] for j in jugadores),
        "goalsByPos": goles_pos,
        "redCards": sum(j["redCards"] for j in jugadores),
        "goalsConceded": encajados,
        "formation": ugw.get("formation"),
        "lineupPoints": puntos_alineacion,
        "players": jugadores,
    }
    if cerrada:
        cache[clave_m] = resultado
    return resultado


# --------------------------------------------------------------------------
# Descarga
# --------------------------------------------------------------------------
def pedir_gw(session, gw, carpeta_debug, etiqueta):
    try:
        resp = session.post(URL_STANDINGS, params={"gw": gw}, headers=HEADERS, timeout=15)
    except Exception as e:
        print(f"  [!] Error de red en {etiqueta}: {e}")
        return None

    print(
        f"   {etiqueta} (gw={gw}) | status={resp.status_code} | len={len(resp.text)} | "
        f"hash={hashlib.md5(resp.content).hexdigest()[:8]}"
    )
    with open(os.path.join(carpeta_debug, f"{etiqueta}.html"), "w", encoding="utf-8") as f:
        f.write(resp.text)

    if resp.status_code != 200:
        return None
    return resp.text


def main():
    print("=" * 65)
    print(" INICIANDO EXTRACTOR AUTOMÁTICO DE MISTER FANTASY")
    print("=" * 65)

    session = requests.Session()
    carpeta_debug = os.path.join(CARPETA_SCRIPT, "debug")
    os.makedirs(carpeta_debug, exist_ok=True)

    # 1. Petición semilla: de aquí sale el mapa jornada -> gw
    print(f"-> Petición inicial (gw={GW_SEMILLA}) para leer el selector de jornadas...")
    html_semilla = pedir_gw(session, GW_SEMILLA, carpeta_debug, "semilla")
    if html_semilla is None:
        print("[!] No se pudo descargar la petición inicial. Revisa las credenciales.")
        input("\nPresiona ENTER para cerrar la ventana...")
        return

    mapa = leer_selector_jornadas(html_semilla, GW_SEMILLA)
    if not mapa:
        print("[!] No se encontró el selector de jornadas. Se usa el mapa de respaldo.")
        mapa = dict(JORNADAS_RESPALDO)
    print("   Jornadas detectadas:", {f"J{n}": gw for n, gw in sorted(mapa.items())})

    # 2. Descargar cada jornada
    datos = {}  # n -> {"general": {...}, "jornada": {...}}
    hechos = set()
    while True:
        pendientes = sorted(n for n in mapa if n not in hechos)
        if not pendientes:
            break
        n = pendientes[0]
        hechos.add(n)
        gw = mapa[n]
        etiqueta = f"J{n}"

        print(f"-> Descargando {etiqueta} (gw={gw})...")
        html = html_semilla if gw == GW_SEMILLA else pedir_gw(session, gw, carpeta_debug, etiqueta)
        if html is None:
            continue

        for k, v in leer_selector_jornadas(html, gw).items():
            mapa.setdefault(k, v)

        listas = extraer_listas(html)
        if len(listas) < 2:
            print(f"   [!] {etiqueta}: solo {len(listas)} lista(s) en la respuesta; se omite.")
            continue
        general, jornada = listas[0], listas[1]

        if all(f["points"] == 0 for f in jornada):
            print(f"   {etiqueta}: todos con 0 puntos (jornada sin jugar); se omite.")
            continue

        datos[n] = {
            "general": {f["id"]: f for f in general},
            "jornada": {f["id"]: f for f in jornada},
        }
        print(f"   {etiqueta}: {len(general)} usuarios en general, {len(jornada)} en jornada")
        time.sleep(0.4)

    if not datos:
        print("[!] No se obtuvo ninguna jornada con datos.")
        input("\nPresiona ENTER para cerrar la ventana...")
        return

    # 3. Alineaciones, goles y tarjetas (puede tardar la primera vez; luego usa la caché)
    cache = cargar_cache()
    extras = {}
    sesion_ok = True
    print("\n-> Descargando alineaciones y detalle de jugadores...")
    for n in sorted(datos):
        if not sesion_ok:
            break
        gw = mapa[n]
        for uid, fj in datos[n]["jornada"].items():
            try:
                extras[(n, uid)] = extra_manager(session, uid, fj["slug"], gw, cache)
            except ErrorSesion as e:
                print(f"\n[!] {e}. Las credenciales han caducado o hay un problema de red.")
                print("    Se guardan los datos obtenidos; actualiza credenciales.env y vuelve a ejecutar.")
                sesion_ok = False
                break
            guardar_cache(cache)
        print(f"   J{n} completada")
    guardar_cache(cache)

    # 4. Construir el JSON
    managers = {}
    matchdays = {}
    acumulados = {}

    for n in sorted(datos):
        clave = f"J{n}"
        matchdays[clave] = {}
        for uid, fj in datos[n]["jornada"].items():
            fg = datos[n]["general"].get(uid, fj)
            if uid not in managers:
                iniciales = "".join(p[0].upper() for p in fg["name"].split()[:2]) or "MF"
                managers[uid] = {
                    "id": uid,
                    "name": fg["name"],
                    "teamName": fg["name"],
                    "avatar": iniciales,
                    "color": COLORES_AVATAR[len(managers) % len(COLORES_AVATAR)],
                }

            acumulados[uid] = acumulados.get(uid, 0) + fj["points"]

            ex = extras.get((n, uid))
            if ex and ex["lineupPoints"] != fj["points"]:
                print(
                    f"   [?] {clave} / {fg['name']}: puntos de la alineación ({ex['lineupPoints']}) "
                    f"distintos de los de la clasificación ({fj['points']})"
                )

            matchdays[clave][uid] = {
                "points": fj["points"],
                "totalPoints": acumulados[uid],
                "position": fj["position"],
                "playersPlayed": fj["playersPlayed"],
                "squadValue": fj["squadValue"],
                "formation": ex["formation"] if ex else None,
                "goals": ex["goals"] if ex else 0,
                "goalsByPos": ex["goalsByPos"] if ex else {"PT": 0, "DF": 0, "MC": 0, "DL": 0},
                "redCards": ex["redCards"] if ex else 0,
                "goalsConceded": ex["goalsConceded"] if ex else 0,
                "players": ex["players"] if ex else [],
            }

    if EVENTOS_VISTOS:
        print("\nTipos de evento detectados en los jugadores:", sorted(EVENTOS_VISTOS))

    # 5. Comprobación: la suma de jornadas debe coincidir con el total general actual
    ultima = max(datos)
    print("\nComprobación (suma de jornadas vs total general actual):")
    for uid, fg in datos[ultima]["general"].items():
        suma = acumulados.get(uid, 0)
        estado = "OK" if suma == fg["points"] else "NO COINCIDE"
        print(f"   {fg['name'][:30]:<30} suma={suma:>4} | total={fg['points']:>4} | {estado}")

    # Obtener la hora actual exacta en la península española
    zona_espana = ZoneInfo("Europe/Madrid")
    ahora_espana = datetime.now(zona_espana)

    resultado = {
        "leagueName": "Golómetro 2.0",
        "season": "2026/2027",
        "lastUpdated": ahora_espana.strftime("%d/%m/%Y a las %H:%M"),
        "managers": list(managers.values()),
        "matchdays": matchdays,
    }

    archivo_salida = os.path.join(CARPETA_SCRIPT, "mister_fantasy_data.json")
    with open(archivo_salida, "w", encoding="utf-8") as f:
        json.dump(resultado, f, ensure_ascii=False, indent=2)

    print("\n" + "=" * 65)
    print(" ¡PROCESO COMPLETADO!")
    print(f" Archivo guardado en: {archivo_salida}")
    print("=" * 65)
    #input("\nPresiona ENTER para cerrar la ventana...")#


if __name__ == "__main__":
    main()
