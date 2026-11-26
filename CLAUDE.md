# Golómetro V2 · reglas para el agente

Proyecto: página de una liga de Mister Fantasy. Una sola página (`index.html`, sin librerías externas de datos) que lee los JSON que generan los scripts de Python y GitHub Actions. Idioma de la página y de los textos: **español de España**. Pestañas: Clasificación, Equipos, Capitán y Mercado. **PIN (decisión del dueño, 06/11/2026): las funciones de IA son solo para él**; sus amigos ven solo lo estadístico. Capitán y Mercado piden el PIN (variable `iaOk`, se recuerda en el móvil con localStorage) y en las demás pestañas las previsiones y consejos van envueltos en `soloIA(...)` («Tu jornada» salvo la predicción, «Candidatos a vender», la previsión de mañana). No quites el PIN ni lo pongas en lo estadístico (clasificación, predicción, previa, marcador, fichajes, ¿Quién clausula mejor?). Cualquier herramienta nueva de previsión o recomendación va con `soloIA`.

**Paleta: verde «Carbón y verde»** (la de la primera versión). El dueño no quiere amarillo como acento: no lo cambies.

## Datos de titularidad (prioridad absoluta del dueño)
`alineaciones.json` (lo genera `alineaciones_ff.py` cada 2 horas desde futbolfantasy.com) da la probabilidad de ser titular de cada jugador en su próximo partido. El capitán y el mercado la usan (80 % Futbol Fantasy, 20 % modelo propio, función `capMezclaFF`). `alineaciones_historial.json` guarda la última probabilidad antes de cada partido: cuando haya varias jornadas, `autoajuste_capitan.py` ya calibra solo cuánto juega de verdad quien FF da con cada % (`parametros_capitan.json` → `futbolFantasy.tramos`, función `capFFCalib` en la página); no lo dupliques. No hagas más peticiones a futbolfantasy.com ni cambies el ritmo del lector.

## Estadísticas externas (decisión del dueño, 06/11/2026)
El dueño pidió usar SofaScore (Mister puntúa con su nota) y otras fuentes de estadísticas. `estadisticas_externas.py` (cuotas de football-data.co.uk y Understat por defecto; SofaScore solo si se pide; sin credenciales, respetando robots.txt) guarda en `externo/` y `modelo_externo.py` genera `estadisticas.json` (cuotas -> goles esperados por partido, xG/xA/nota por jugador, conversión nota -> puntos y validación). Lo ejecuta cada día el flujo `.github/workflows/estadisticas.yml`, que el dueño autorizó expresamente el 06/11/2026 (los demás flujos siguen sin tocarse). **SofaScore rechaza a los servidores de GitHub con su protección antirobots y no se esquiva**: nada de hacerse pasar por un navegador (curl_cffi, Playwright, cabeceras falsas) ni de usar el navegador del dueño para descargarlo; el lector se identifica como `GolometroBot`. Si se pide SofaScore, se guarda un fichero por jornada en `externo/sofascore/<temporada>/`. La página lo usa si existe (`extPartido`, `extAjusteXg`); la corrección por xG solo se aplica si `validacion.mejora > 0`. No añadas más fuentes ni subas el ritmo de peticiones.

## Modelo de partido (pedido del dueño, 06/11/2026: «que se rija por las estadísticas»)
- **Goles esperados de cada partido**: cuotas si existen; si no, `modelo_externo.py` → `mercado()` (fuerza de ataque y defensa ajustada a las cuotas de los partidos ya jugados, fuente `"mercado"` en `estadisticas.json`). Validado J3-J11: correlación con los goles reales 0,54 frente a 0,36 del modelo de goles propio.
- **Puntos según el partido**: `modelo_liga.py` → `modelo_partido()` (`parametros_capitan.json` → `liga.partido`): con toda LaLiga, puntos sobre su nivel según goles encajados/marcados (0-4+) y el reparto alrededor. La web (`capPartido`, `capPartidoJugador`) lo mezcla con Poisson para la media y el riesgo de cada jugador (p. ej. riesgo de goleada de un defensa). Colas calibradas: `CAP.PART_BAJO`, `PART_GOLEADA`, `PART_ALTO`. Si falta `liga.partido`, se usa la fórmula anterior. No vuelvas a fijar a mano sensibilidades del rival: mídelas.

## Plan del parón, Escudo anticláusulas y Tus rivales (pedido del dueño, 06/11/2026, solo con PIN)
En la pestaña Mercado, que desde la limpieza del 26/11 tiene **solo 5 bloques** bajo una cabecera con la plantilla y el saldo: «Tu jugada de hoy» (`bloqueJugada`, antes el Plan), «Libres de hoy» con filtros Todos / Para tu once / Para invertir y el simulador de puja dentro (`bloqueLibres`), «Tu plantilla» (`bloqueEscudo`), la **Mesa de operaciones** plegada (`bloqueMesa`, `mesaOptimo`) y «Tus rivales y cómo se puja» plegado (`bloqueRivalesMer`: `bloqueLeerRivales`, `bloquePujasLiga`, `bloqueMercadoAyer`). No añadas bloques sueltos a Mercado: lo nuevo va dentro de uno de estos cinco. Usan `liga.valorPersist` (inercia del valor a varios días) y `liga.pujas` (quién puja por cada libre, `pIntencion`, también en `pGanarPuja`), que calcula y valida `modelo_liga.py` cada día. Reglas de Mister dichas por el dueño: la cláusula es el 150 % de lo pagado (o del valor si ya vale más); subirla al 200 % cuesta el 20 % de esa base y al 250 % el 40 %; tras fichar hay 3 días en los que no se puede clausular. El saldo lo escribe el dueño y solo se guarda en su móvil (localStorage `saldo`). No los saques del PIN.

## Capitán: UN SOLO algoritmo (decisión del dueño, 04/11/2026)
Ya no existen las tres pestañas «Seguro / Equilibrado / Arriesgado»: **no las vuelvas a crear**. La pestaña Capitán tiene una sola lista y el propio algoritmo decide el riesgo: puntuación = (multiplicador − 1) × (puntos esperados + k × posible subida − l × posible bajada), con `k` y `l` calibrados cada día por `autoajuste_capitan.py` con las jornadas pasadas (`parametros_capitan.json` → `riesgo`, `CAP.RIESGO` en la página). Cada tarjeta explica el coste (multiplicador por valor), el beneficio (puntos esperados) y el riesgo (techo, suelo, probabilidad de jugar). El panel «Análisis del riesgo» muestra la evidencia. Al rediseñar la pestaña Capitán (fase 5), hazlo sobre este diseño: una lista única, el mejor capitán destacado arriba con su porqué en una frase, y el detalle plegable. Si tu rama tiene conflictos con `main` en `index.html`, rebasa y **conserva la lógica de `main`** (riesgo único, probabilidades de Futbol Fantasy) aplicando tus cambios visuales encima.

## AGENTES AUTÓNOMOS (decisión del dueño, 26/11/2026)
Cuatro agentes trabajan solos con tareas programadas de Claude (ya no con el flujo `agente.yml`, que está desactivado: el reloj de GitHub se saltaba más del 90 % de las ejecuciones). El dueño pidió que **publiquen solos**: lo que el Revisor aprueba se fusiona en `main` sin esperarle. Por eso las reglas de abajo no se saltan nunca.

| Agente | Cuándo (hora de Madrid) | Rama | Qué hace |
|---|---|---|---|
| **Vigilante de datos** | cada día, 07:43 | `agente/datos` | Comprueba que los JSON están al día y que la web cuadra con ellos; arregla errores de datos o de la página. Relanza los flujos de datos atrasados. |
| **Analista del modelo** | lunes y jueves, 10:37 | `agente/modelo` | Mejora la precisión del capitán y del mercado (`modelo_liga.py`, `autoajuste_capitan.py`, lógica de la página). |
| **Creador de herramientas** | martes, jueves y sábado, 12:29 | `agente/herramientas` | Una herramienta nueva, útil y vistosa por ejecución (sección «Ideas» de `MEJORAS.md`; antes, lo pendiente de las fases del parón). |
| **Revisor** | cada día, 13:47 y 22:47 | — | Prueba las Pull Requests de los demás, fusiona las que pasan y vigila que todos los agentes y flujos sigan vivos. |

**En estas sesiones GitHub solo responde por la API REST**: usa `gh api repos/…` para PRs, issues, comentarios y fusiones (`gh pr create`, `gh issue` y otros que usan GraphQL fallan).

### Reglas comunes (los tres que programan)
1. Repositorio `GolometroV2/golometrov2.github.io` (clónalo con `gh repo clone` si no está). Lee este fichero y `MEJORAS.md` antes de elegir qué hacer.
2. Trabaja **solo en tu rama**. Si no existe, créala desde `origin/main`. Si existe: `git fetch origin`, `git checkout <rama>`, `git pull --no-rebase origin <rama>` y `git merge origin/main`. Nunca `push --force`, `reset` ni rebase de lo ya subido. Nunca subas a `main`.
3. **Una sola mejora por ejecución**, de menos de ~400 líneas, probada como dice «Cómo se prueba». Si no encuentras nada que merezca la pena o la prueba falla, no subas nada (y deshaz lo hecho).
4. Anota en `MEJORAS.md`, en «## Hecho», una línea que empiece por `- AAAA-MM-DD (<agente>)` con qué, por qué y cómo lo probaste. Si al traer cambios choca `MEJORAS.md`, quédate con las líneas de los dos lados.
5. Una sola Pull Request abierta por rama hacia `main`: búscala con `gh api "repos/GolometroV2/golometrov2.github.io/pulls?head=GolometroV2:<rama>&state=open"` y créala si no hay (`gh api repos/GolometroV2/golometrov2.github.io/pulls -f title=… -f head=<rama> -f base=main -f body=…`), o añade tu mejora a su descripción. En la descripción, 5 líneas: qué cambia y cómo lo probaste.
6. Si tu PR tiene un comentario del Revisor con fallos, arréglalos antes que nada.
7. Al terminar, deja un comentario en el issue **«Estado de los agentes»** (`gh api repos/GolometroV2/golometrov2.github.io/issues/<n>/comments -f body=…`; el número está al final de esta sección): `✅ <agente> · <fecha y hora> · <una frase>` o `⚠️ <agente> · … · <qué falló>`. Es el latido que mira el Revisor.

Issue de latidos: **#26** («Estado de los agentes»).

### Revisor: cuándo se fusiona (si falla una sola condición, NO se fusiona)
- La PR viene de `agente/datos`, `agente/modelo` o `agente/herramientas`. Nada de otras ramas (la antigua `agente/semana`, PR #25, queda en espera: no se fusiona).
- **Estructura de la web (limpieza del 26/11, pedido del dueño: «la web está muy sucia, hay herramientas parecidas»):** Clasificación = tabla y podio, Tu jornada, Predicción/Previa, Crónica, Pronóstico, Comparador y 5 grupos con pestañas (Evolución, Cara a cara, Capitanes, Cómo juega cada uno, Récords y premios); Equipos = valor de plantilla y 3 grupos (Valor, Cómo es cada manager, Fichajes); Mercado = los 5 bloques de arriba. **No se aceptan tarjetas sueltas nuevas**: una herramienta nueva entra como pestaña de un grupo que ya existe (`htmlGrupo`) o sustituye a otra que haga lo mismo. Rechaza lo que repita algo que ya hay o que solo sea vistoso.
- No toca `.github/workflows/`, `previa.html`, `credenciales.env` ni secretos; no borra JSON ni cambia su formato; no quita el PIN ni saca de `soloIA` una previsión o consejo; no mete amarillo de acento ni librerías o peticiones externas nuevas.
- Con `origin/main` mezclado dentro y sin conflictos: `node --check` del script de `index.html`; Playwright sirviendo la carpeta con `python -m http.server`, las 4 pestañas a 360, 390 y 420 px, con y sin PIN, claro y oscuro: **cero errores de consola y sin scroll horizontal**; capturas revisadas a ojo.
- Mismos números que en `main` en lo que la PR no dice cambiar (clasificación, puntos, valores, capitán recomendado, puja ideal).
- Si toca el modelo: la validación cruzada de `modelo_liga.py` / `autoajuste_capitan.py` no empeora.
Si pasa: `gh api -X PUT repos/GolometroV2/golometrov2.github.io/pulls/<n>/merge -f merge_method=merge -f sha=<commit probado>` y comentario breve con lo probado. Si no: comentario en la PR con los fallos concretos y NO se fusiona. Una PR cada vez; tras fusionar, mezcla `main` en la siguiente antes de probarla.
Después de fusionar, abre la web oficial (o `main` servido en local) y repite la prueba: si algo se ha roto, revierte la fusión con una PR (`git revert -m 1`) y fusiónala tú mismo, explicando el motivo en el issue.

### Revisor: vigilancia
- **Agentes:** mira el último latido de cada uno en el issue. Si el Vigilante lleva más de 36 h, el Analista más de 5 días o el Creador más de 4 días sin latido, relánzalo con la herramienta de tareas programadas si la tienes; si no, avisa en el issue.
- **Flujos de datos de GitHub** (el cron de GitHub se salta ejecuciones): si el último éxito de `seguimiento.yml` tiene más de 3 h, `alineaciones.yml` más de 4 h, o `actualizar.yml`, `mercado.yml` o `estadisticas.yml` más de 26 h, lánzalo con `gh api -X POST repos/GolometroV2/golometrov2.github.io/actions/workflows/<fichero>/dispatches -f ref=main`. No cambies los ficheros de los flujos.

## PARÓN (09-20/11/2026, terminado): herramientas visuales muy avanzadas (pedido del dueño, 09/11)
El dueño quiere herramientas «que sean una locura estéticamente», al nivel de las mejores apps deportivas, para enseñarlas y compartirlas en los grupos de WhatsApp. Tienes mano libre; estas reglas no se saltan:
- Una herramienta (o una parte entera de una grande) por ejecución, terminada y probada. Nada a medias a la vista.
- Solo HTML, CSS, SVG y Canvas propios: sin librerías, sin fuentes ni imágenes de internet. Fotos y escudos de `fotos/`; si falta una foto, iniciales o camiseta del color del equipo (`esCamiseta`).
- Mobile-first (360/390/420 px y escritorio) y fluido en el móvil: anima `transform` y `opacity`, para lo que no se ve y respeta siempre `prefers-reduced-motion`. Sin scroll horizontal de la página.
- Paleta verde del sistema de diseño, sin amarillo de acento. Lo estadístico, para todos; previsiones y consejos, con `soloIA`.
- Las alineaciones se ven siempre en el campo 3D (`htmlCampo3D`, decisión del dueño 09/11): no vuelvas a poner selector Plano/3D, ni giro ni diagonal. Los puntos de una jornada (y los esperados) llevan los colores de Mister (`tramoPts`, `colPts`, clases `mp-*`); no inventes otra escala.
- Reutiliza lo que ya existe en vez de duplicarlo: `htmlCampo3D` (campo en 3D), `cuadricula` (mapa tipo bolsa), `htmlGrupo` (tarjeta con pestañas: lo nuevo entra aquí), el estudio de imágenes (`ES_*`, `abrirEstudio`, láminas de 1080×1350; para una lámina nueva añade su lista a `ES_SETS` y su dato a `EST_DAT`), las historias (`wrTodos`, `abrirWrapped`), el cromo (`cromoDatos`, `abrirCromo`), `cara()`, `fotoDe()`.
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

### Fase 2 del parón (desde el 10/11): modernizar toda la web y herramientas de vanguardia (pedido del dueño)
Los 8 puntos de arriba ya están hechos. El dueño: «modernizar toda la web y crear más herramientas futuristas y de vanguardia, impresionantes visualmente, con los datos ya recabados». Ya hay: podio de la Clasificación, cinta «Ahora» bajo la cabecera, «Explora la liga» (tarjetas deslizables) y la Bolsa de LaLiga (Equipos). El mapa de la conquista, la galaxia y el radar de pujas se quitaron el 26/11 por no ser útiles: no los recuperes. Ideas, de más a menos valor (mira `MEJORAS.md` antes; si algo ya existe, mejóralo en vez de duplicarlo):
1. «Explora» también en Equipos (y en Capitán y Mercado con PIN): tarjetas deslizables arriba que llevan a cada bloque, para que las pestañas no sean una lista interminable.
2. Láminas para compartir de la Bolsa, el mapa de la conquista y la galaxia (estudio de imágenes, `ES_SETS`).
3. Ficha del jugador como pantalla de app: cabecera con la foto grande sobre el color de su equipo, cifras grandes y el cromo arriba.
4. (Hecho: «El partido en 3D», `ptAbrir`.) Ampliarlo: partido de la jornada en la Crónica (1.º contra 2.º), y una «liga de partidos» (clasificación si cada jornada fuese un cara a cara).
5. Jornada en directo como «actividad en vivo»: tarjeta fija arriba mientras se juega, con los puntos de cada manager subiendo y quién va ganando.
6. Mercado (con PIN): radar de pujas, un sónar animado con los libres según su puja ideal y la probabilidad de llevárselos.
7. Capitán (con PIN): la distribución de puntos posible de cada candidato (curva o violín) en vez de solo techo y suelo.

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
