# Golómetro V2 · reglas para el agente

Proyecto: página de una liga de Mister Fantasy. Una sola página (`index.html`, sin librerías externas de datos) que lee los JSON que generan los scripts de Python y GitHub Actions. Idioma de la página y de los textos: **español de España**. Pestañas: Clasificación, Equipos, Capitán y Mercado, todas abiertas (el dueño quitó el PIN el 04/11/2026: no lo vuelvas a poner).

**Paleta: verde «Carbón y verde»** (la de la primera versión). El dueño no quiere amarillo como acento: no lo cambies.

## Datos de titularidad (prioridad absoluta del dueño)
`alineaciones.json` (lo genera `alineaciones_ff.py` cada 2 horas desde futbolfantasy.com) da la probabilidad de ser titular de cada jugador en su próximo partido. El capitán y el mercado la usan (80 % Futbol Fantasy, 20 % modelo propio, función `capMezclaFF`). `alineaciones_historial.json` guarda la última probabilidad antes de cada partido: cuando haya varias jornadas, `autoajuste_capitan.py` ya calibra solo cuánto juega de verdad quien FF da con cada % (`parametros_capitan.json` → `futbolFantasy.tramos`, función `capFFCalib` en la página); no lo dupliques. No hagas más peticiones a futbolfantasy.com ni cambies el ritmo del lector.

## Capitán: UN SOLO algoritmo (decisión del dueño, 04/11/2026)
Ya no existen las tres pestañas «Seguro / Equilibrado / Arriesgado»: **no las vuelvas a crear**. La pestaña Capitán tiene una sola lista y el propio algoritmo decide el riesgo: puntuación = (multiplicador − 1) × (puntos esperados + k × posible subida − l × posible bajada), con `k` y `l` calibrados cada día por `autoajuste_capitan.py` con las jornadas pasadas (`parametros_capitan.json` → `riesgo`, `CAP.RIESGO` en la página). Cada tarjeta explica el coste (multiplicador por valor), el beneficio (puntos esperados) y el riesgo (techo, suelo, probabilidad de jugar). El panel «Análisis del riesgo» muestra la evidencia. Al rediseñar la pestaña Capitán (fase 5), hazlo sobre este diseño: una lista única, el mejor capitán destacado arriba con su porqué en una frase, y el detalle plegable. Si tu rama tiene conflictos con `main` en `index.html`, rebasa y **conserva la lógica de `main`** (riesgo único, probabilidades de Futbol Fantasy) aplicando tus cambios visuales encima.

## Qué tienes que hacer en cada ejecución
1. Lee `MEJORAS.md` (lo hecho y las ideas pendientes) y los datos de los JSON.
2. Elige **UNA sola mejora** con valor real para los jugadores de la liga. Prioridad: errores graves de datos > **rediseño por fases (sección DISEÑO; mientras queden fases por hacer, es lo que toca)** > precisión del modelo (capitán y mercado) > herramientas nuevas (comparadores, histórico de pujas, resumen de jornada). Los arreglos pequeños (una fuente, una barra) no cuentan como fase: cada ejecución debe avanzar una fase entera del rediseño, con cambios visibles.
3. Impleméntala en una rama nueva `agente/AAAA-MM-DD`, probándola de verdad (ver abajo).
4. Anota en `MEJORAS.md` qué hiciste, por qué y qué ideas nuevas has visto. Mantén la lista de ideas pendientes ordenada.
5. Abre una Pull Request con `gh pr create` explicando en 5 líneas qué cambia y cómo lo has probado. **Nunca subas directo a `main`.**

## MODO INTENSIVO (hasta el 11/11/2026)
Se te ejecuta cada hora. Para no llenar el repositorio de ramas y no crear conflictos:
- Trabaja siempre en la rama `agente/semana`. Si no existe, créala desde `main`. Si existe: `git fetch origin` y `git checkout agente/semana && git pull --rebase origin agente/semana`; para traer cambios de `main`, usa `git merge origin/main` (nunca `rebase` sobre main).
- **Claude también sube commits a esta rama a mano.** Nunca reescribas su historia: prohibido `git push --force`, `--force-with-lease`, `reset` o rebase de commits ya subidos. Sube con `git pull --rebase origin agente/semana && git push origin agente/semana`; si falla, repite el pull y vuelve a subir.
- Cada ejecucion = una mejora pequena = un commit con mensaje claro.
- Mantén UNA sola Pull Request abierta de `agente/semana` a `main` (compruebalo con `gh pr list --head agente/semana`; si no existe, creala; si existe, actualiza su descripcion con la lista de mejoras).
- Si la PR ya fue aceptada y la rama quedo vieja, empieza una `agente/semana` nueva desde `main`.
- Prioriza variedad: no repitas el mismo tipo de mejora dos veces seguidas y revisa `MEJORAS.md` antes de elegir. Si algo se rompe en una prueba, revierte tu cambio y apunta el motivo en `MEJORAS.md`.
- Las ideas pendientes de `MEJORAS.md` son un punto de partida, no un limite: investiga los datos y propon tus propias herramientas (comparadores, resumenes, graficos, calendario de fichajes, alertas de clausulas, etc.).

## DISEÑO: libertad total (el dueño lo pide expresamente)
El diseño actual se considera poco profesional. Tienes libertad completa para rehacerlo: paleta, tipografía, espaciados, iconos (SVG propios), tarjetas, tablas, gráficos, animaciones suaves, estados vacíos y de carga, navegación, cabecera, todo. Objetivo: que parezca una app deportiva moderna y cuidada (nivel producto), no una página casera.
- Durante la primera mitad del modo intensivo, **prioriza el rediseño** sobre otras mejoras. Hazlo por fases, una por ejecución, y cada fase deja la web completa y funcionando: 1) sistema de diseño (variables CSS de color, tipografía, radios, sombras, espaciado, modo claro/oscuro automático), 2) cabecera, navegación y pestañas, 3) Clasificación, 4) Equipos, 5) Capitán, 6) Mercado, 7) microinteracciones, accesibilidad y rendimiento, 8) revisión final de coherencia.
- Es mobile-first (la usan desde el móvil): revisa 360, 390 y 420 px, y también escritorio. Objetivos táctiles de al menos 44 px, contraste suficiente, `prefers-reduced-motion`, sin scroll horizontal de la página.
- Tipografía: pila de fuentes del sistema o una fuente incluida en el propio repositorio. No cargues fuentes ni librerías desde internet.
- Puedes reorganizar el HTML y el CSS cuanto quieras, **pero la lógica y los datos no cambian**: los cálculos, las reglas del capitán y del mercado y la lectura de los JSON tienen que seguir dando exactamente los mismos resultados. Comprueba antes y después con capturas y comparando los números mostrados.
- Pensado para uso real: lo más importante de cada pestaña a la vista sin tocar nada (el capitán recomendado, la puja ideal, la clasificación), detalles plegables.
- Usa tu criterio de diseñador: jerarquía visual clara, pocas cosas por pantalla, mucho aire, un solo color de acento, estados (hover, activo, deshabilitado) cuidados.

## Prohibido
- Tocar `previa.html` (lo genera un flujo automático con una copia de tu rama).
- Tocar o leer `credenciales.env`, secretos, cookies o tokens. No los muestres en ningún texto, log ni PR.
- Cambiar los flujos de `.github/workflows/`.
- Borrar datos (`*.json`) ni cambiar su formato sin que la página siga leyéndolos igual.
- Añadir librerías o servicios externos, ni hacer peticiones a Mister (no tienes credenciales).
- Cambios de más de ~400 líneas en una sola ejecución.

## Cómo se prueba
- Sintaxis del JS: extraer el `<script>` de `index.html` a un fichero temporal y `node --check`.
- En navegador: servir la carpeta con `python -m http.server` y abrirla con Playwright (Chromium). Haz capturas en móvil (420 px) y revisa que no hay errores en la consola.
- El modelo (`modelo_liga.py`, `autoajuste_capitan.py`) se valida con la validación cruzada que ya imprime; no aceptes un cambio que empeore el error.
- Reglas que ya existen y no se rompen: los capitanes de una jornada ya empezada no cambian; no se recomiendan jugadores fichados después de empezar la jornada; en Mercado solo jugadores libres; el valor de jugadores por debajo de 1 M no se puede predecir.

## Estilo
Código y comentarios en español, simple, sin dependencias. Los textos de la página deben ser claros para alguien que no sabe estadística.
