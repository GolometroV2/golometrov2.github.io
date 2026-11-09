# Golómetro V2 · reglas para el agente

Proyecto: página de una liga de Mister Fantasy. Una sola página (`index.html`, sin librerías externas de datos) que lee los JSON que generan los scripts de Python y GitHub Actions. Idioma de la página y de los textos: **español de España**. Pestañas: Clasificación, Equipos, Capitán y Mercado. **PIN (decisión del dueño, 06/11/2026): las funciones de IA son solo para él**; sus amigos ven solo lo estadístico. Capitán y Mercado piden el PIN (variable `iaOk`, se recuerda en el móvil con localStorage) y en las demás pestañas las previsiones y consejos van envueltos en `soloIA(...)` («Tu jornada» salvo la predicción, «Cláusulas que merecen la pena», «Valor dentro de una semana», «Candidatos a vender», la previsión de mañana). No quites el PIN ni lo pongas en lo estadístico (clasificación, predicción, previa, marcador, fichajes, ¿Quién clausula mejor?). Cualquier herramienta nueva de previsión o recomendación va con `soloIA`.

**Paleta: verde «Carbón y verde»** (la de la primera versión). El dueño no quiere amarillo como acento: no lo cambies.

## Datos de titularidad (prioridad absoluta del dueño)
`alineaciones.json` (lo genera `alineaciones_ff.py` cada 2 horas desde futbolfantasy.com) da la probabilidad de ser titular de cada jugador en su próximo partido. El capitán y el mercado la usan (80 % Futbol Fantasy, 20 % modelo propio, función `capMezclaFF`). `alineaciones_historial.json` guarda la última probabilidad antes de cada partido: cuando haya varias jornadas, `autoajuste_capitan.py` ya calibra solo cuánto juega de verdad quien FF da con cada % (`parametros_capitan.json` → `futbolFantasy.tramos`, función `capFFCalib` en la página); no lo dupliques. No hagas más peticiones a futbolfantasy.com ni cambies el ritmo del lector.

## Estadísticas externas (decisión del dueño, 06/11/2026)
El dueño pidió usar SofaScore (Mister puntúa con su nota) y otras fuentes de estadísticas. `estadisticas_externas.py` (cuotas de football-data.co.uk y Understat por defecto; SofaScore solo si se pide; sin credenciales, respetando robots.txt) guarda en `externo/` y `modelo_externo.py` genera `estadisticas.json` (cuotas -> goles esperados por partido, xG/xA/nota por jugador, conversión nota -> puntos y validación). Lo ejecuta cada día el flujo `.github/workflows/estadisticas.yml`, que el dueño autorizó expresamente el 06/11/2026 (los demás flujos siguen sin tocarse). **SofaScore rechaza a los servidores de GitHub con su protección antirobots y no se esquiva**: nada de hacerse pasar por un navegador (curl_cffi, Playwright, cabeceras falsas) ni de usar el navegador del dueño para descargarlo; el lector se identifica como `GolometroBot`. Si se pide SofaScore, se guarda un fichero por jornada en `externo/sofascore/<temporada>/`. La página lo usa si existe (`extPartido`, `extAjusteXg`); la corrección por xG solo se aplica si `validacion.mejora > 0`. No añadas más fuentes ni subas el ritmo de peticiones.

## Modelo de partido (pedido del dueño, 06/11/2026: «que se rija por las estadísticas»)
- **Goles esperados de cada partido**: cuotas si existen; si no, `modelo_externo.py` → `mercado()` (fuerza de ataque y defensa ajustada a las cuotas de los partidos ya jugados, fuente `"mercado"` en `estadisticas.json`). Validado J3-J11: correlación con los goles reales 0,54 frente a 0,36 del modelo de goles propio.
- **Puntos según el partido**: `modelo_liga.py` → `modelo_partido()` (`parametros_capitan.json` → `liga.partido`): con toda LaLiga, puntos sobre su nivel según goles encajados/marcados (0-4+) y el reparto alrededor. La web (`capPartido`, `capPartidoJugador`) lo mezcla con Poisson para la media y el riesgo de cada jugador (p. ej. riesgo de goleada de un defensa). Colas calibradas: `CAP.PART_BAJO`, `PART_GOLEADA`, `PART_ALTO`. Si falta `liga.partido`, se usa la fórmula anterior. No vuelvas a fijar a mano sensibilidades del rival: mídelas.

## Plan del parón, Escudo anticláusulas y Tus rivales (pedido del dueño, 06/11/2026, solo con PIN)
En la pestaña Mercado (`bloquePlanParon`, `bloqueEscudo`, `bloqueLeerRivales`). Usan `liga.valorPersist` (inercia del valor a varios días) y `liga.pujas` (quién puja por cada libre, `pIntencion`, también en `pGanarPuja`), que calcula y valida `modelo_liga.py` cada día. Reglas de Mister dichas por el dueño: la cláusula es el 150 % de lo pagado (o del valor si ya vale más); subirla al 200 % cuesta el 20 % de esa base y al 250 % el 40 %; tras fichar hay 3 días en los que no se puede clausular. El saldo lo escribe el dueño y solo se guarda en su móvil (localStorage `saldo`). No los saques del PIN.

## Capitán: UN SOLO algoritmo (decisión del dueño, 04/11/2026)
Ya no existen las tres pestañas «Seguro / Equilibrado / Arriesgado»: **no las vuelvas a crear**. La pestaña Capitán tiene una sola lista y el propio algoritmo decide el riesgo: puntuación = (multiplicador − 1) × (puntos esperados + k × posible subida − l × posible bajada), con `k` y `l` calibrados cada día por `autoajuste_capitan.py` con las jornadas pasadas (`parametros_capitan.json` → `riesgo`, `CAP.RIESGO` en la página). Cada tarjeta explica el coste (multiplicador por valor), el beneficio (puntos esperados) y el riesgo (techo, suelo, probabilidad de jugar). El panel «Análisis del riesgo» muestra la evidencia. Al rediseñar la pestaña Capitán (fase 5), hazlo sobre este diseño: una lista única, el mejor capitán destacado arriba con su porqué en una frase, y el detalle plegable. Si tu rama tiene conflictos con `main` en `index.html`, rebasa y **conserva la lógica de `main`** (riesgo único, probabilidades de Futbol Fantasy) aplicando tus cambios visuales encima.

## Qué tienes que hacer en cada ejecución
1. Lee `MEJORAS.md` (lo hecho y las ideas pendientes) y los datos de los JSON.
2. Elige **UNA sola mejora** con valor real para los jugadores de la liga. Prioridad: errores graves de datos > **hoja de ruta del parón (sección PARÓN, hasta el 20/11)** > precisión del modelo (capitán y mercado) > otras herramientas nuevas. Las 8 fases del rediseño ya están hechas (04-08/11): no las repitas. Los arreglos pequeños (una fuente, una barra) no cuentan: cada ejecución debe dejar algo nuevo y visible.
3. Impleméntala en una rama nueva `agente/AAAA-MM-DD`, probándola de verdad (ver abajo).
4. Anota en `MEJORAS.md` qué hiciste, por qué y qué ideas nuevas has visto. Mantén la lista de ideas pendientes ordenada.
5. Abre una Pull Request con `gh pr create` explicando en 5 líneas qué cambia y cómo lo has probado. **Nunca subas directo a `main`.**

## MODO INTENSIVO (hasta el 20/11/2026, fin del parón de selecciones; el dueño lo amplió el 09/11 y autorizó cambiar esa fecha en `agente.yml`)
Se te ejecuta cada hora. Para no llenar el repositorio de ramas y no crear conflictos:
- Trabaja siempre en la rama `agente/semana`. Si no existe, créala desde `main`. Si existe: `git fetch origin` y `git checkout agente/semana && git pull --rebase origin agente/semana`; para traer cambios de `main`, usa `git merge origin/main` (nunca `rebase` sobre main).
- **Claude también sube commits a esta rama a mano.** Nunca reescribas su historia: prohibido `git push --force`, `--force-with-lease`, `reset` o rebase de commits ya subidos. Sube con `git pull --rebase origin agente/semana && git push origin agente/semana`; si falla, repite el pull y vuelve a subir.
- Cada ejecucion = una mejora pequena = un commit con mensaje claro.
- Mantén UNA sola Pull Request abierta de `agente/semana` a `main` (compruebalo con `gh pr list --head agente/semana`; si no existe, creala; si existe, actualiza su descripcion con la lista de mejoras).
- Si la PR ya fue aceptada y la rama quedo vieja, empieza una `agente/semana` nueva desde `main`.
- Prioriza variedad: no repitas el mismo tipo de mejora dos veces seguidas y revisa `MEJORAS.md` antes de elegir. Si algo se rompe en una prueba, revierte tu cambio y apunta el motivo en `MEJORAS.md`.
- Las ideas pendientes de `MEJORAS.md` son un punto de partida, no un limite: investiga los datos y propon tus propias herramientas (comparadores, resumenes, graficos, calendario de fichajes, alertas de clausulas, etc.).

## PARÓN (09-20/11/2026): herramientas visuales muy avanzadas (pedido del dueño, 09/11)
El dueño quiere herramientas «que sean una locura estéticamente», al nivel de las mejores apps deportivas, para enseñarlas y compartirlas en los grupos de WhatsApp. Tienes mano libre; estas reglas no se saltan:
- Una herramienta (o una parte entera de una grande) por ejecución, terminada y probada. Nada a medias a la vista.
- Solo HTML, CSS, SVG y Canvas propios: sin librerías, sin fuentes ni imágenes de internet. Fotos y escudos de `fotos/`; si falta una foto, iniciales o camiseta del color del equipo (`esCamiseta`).
- Mobile-first (360/390/420 px y escritorio) y fluido en el móvil: anima `transform` y `opacity`, para lo que no se ve y respeta siempre `prefers-reduced-motion`. Sin scroll horizontal de la página.
- Paleta verde del sistema de diseño, sin amarillo de acento. Lo estadístico, para todos; previsiones y consejos, con `soloIA`.
- Reutiliza lo que ya existe en vez de duplicarlo: `htmlCampo3D` (campo en 3D), el estudio de imágenes (`ES_*`, `abrirEstudio`, láminas de 1080×1350), `cara()`, `fotoDe()`.
- Mismos números que la vista normal: compruébalo con capturas antes y después.

Orden (de más a menos valor; anota en `MEJORAS.md` lo que hagas). Si se te ocurre algo mejor, adelante, pero mira antes que no exista:
1. Campo 3D en más sitios: once ideal de la temporada, plantilla de cada manager en Equipos (once probable con su valor) y once recomendado del Capitán (con PIN).
2. «Wrapped» de cada manager: historias a pantalla completa que se pasan con el dedo (mejor jornada, peor capitán, fichaje estrella, dinero ganado con ventas, rival al que más ganó…), con transiciones y botón para compartirlas como imágenes del estudio.
3. Cromo del jugador en su ficha: carta con brillo metálico verde que se inclina siguiendo el dedo (sin giroscopio), puntos por jornada en minigráfica, valor y próximo rival; compartible.
4. Repetición de la liga: carrera de barras animada jornada a jornada (avatares que se adelantan, botón ▶ y barra de tiempo). Es distinta de «La carrera», que es una gráfica de líneas.
5. Red de traspasos: managers en círculo y arcos animados de fichajes y cláusulas entre ellos (grosor = dinero); tocar un manager deja solo sus movimientos.
6. Línea del tiempo de la temporada: hitos de cada jornada (líder, récord, fichaje más caro, goleada) con desplazamiento horizontal.
7. Más láminas en el estudio de imágenes: el campo 3D dibujado en canvas para la previa y la crónica, el cromo del MVP, el «Wrapped».
8. Microinteracciones en toda la web: transición suave entre pestañas, cifras que cuentan al aparecer, estados vacíos con dibujos SVG propios.

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
