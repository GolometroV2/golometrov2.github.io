# Golómetro V2 · reglas para el agente

Proyecto: página de una liga de Mister Fantasy. Una sola página (`index.html`, sin librerías externas de datos) que lee los JSON que generan los scripts de Python y GitHub Actions. Idioma de la página y de los textos: **español de España**. Pestañas: Clasificación, Equipos (PIN), Capitán (PIN), Mercado (PIN).

## Qué tienes que hacer en cada ejecución
1. Lee `MEJORAS.md` (lo hecho y las ideas pendientes) y los datos de los JSON.
2. Elige **UNA sola mejora** con valor real para los jugadores de la liga. Prioriza: errores y datos raros > precisión del modelo (capitán y mercado) > herramientas nuevas (por ejemplo comparadores, histórico de pujas, resumen de jornada) > diseño.
3. Impleméntala en una rama nueva `agente/AAAA-MM-DD`, probándola de verdad (ver abajo).
4. Anota en `MEJORAS.md` qué hiciste, por qué y qué ideas nuevas has visto. Mantén la lista de ideas pendientes ordenada.
5. Abre una Pull Request con `gh pr create` explicando en 5 líneas qué cambia y cómo lo has probado. **Nunca subas directo a `main`.**

## MODO INTENSIVO (hasta el 11/11/2026)
Se te ejecuta cada hora. Para no llenar el repositorio de ramas y no crear conflictos:
- Trabaja siempre en la rama `agente/semana` (si no existe, crea desde `main`; si existe, `git fetch` y rebasa sobre `main`).
- Cada ejecucion = una mejora pequena = un commit con mensaje claro. Sube con `git push --force-with-lease`.
- Mantén UNA sola Pull Request abierta de `agente/semana` a `main` (compruebalo con `gh pr list --head agente/semana`; si no existe, creala; si existe, actualiza su descripcion con la lista de mejoras).
- Si la PR ya fue aceptada y la rama quedo vieja, empieza una `agente/semana` nueva desde `main`.
- Prioriza variedad: no repitas el mismo tipo de mejora dos veces seguidas y revisa `MEJORAS.md` antes de elegir. Si algo se rompe en una prueba, revierte tu cambio y apunta el motivo en `MEJORAS.md`.
- Las ideas pendientes de `MEJORAS.md` son un punto de partida, no un limite: investiga los datos y propon tus propias herramientas (comparadores, resumenes, graficos, calendario de fichajes, alertas de clausulas, etc.).

## DISEÑO: libertad total (el dueño lo pide expresamente)
El diseño actual se considera poco profesional. Tienes libertad completa para rehacerlo: paleta, tipografía, espaciados, iconos (SVG propios), tarjetas, tablas, gráficos, animaciones suaves, estados vacíos y de carga, navegación, cabecera, todo. Objetivo: que parezca una app deportiva moderna y cuidada (nivel producto), no una página casera.
- Durante la primera mitad del modo intensivo, **prioriza el rediseño** sobre otras mejoras. Hazlo por fases, una por ejecución, y cada fase deja la web completa y funcionando: 1) sistema de diseño (variables CSS de color, tipografía, radios, sombras, espaciado, modo claro/oscuro automático), 2) cabecera, navegación y pestañas, 3) Clasificación, 4) Equipos, 5) Capitán, 6) Mercado, 7) microinteracciones, accesibilidad y rendimiento, 8) revisión final de coherencia.
- Es mobile-first (la usan desde el móvil): revisa 360, 390 y 420 px, y también escritorio. Objetivos táctiles de al menos 44 px, contraste suficiente, `prefers-reduced-motion`, sin scroll horizontal de la página.
- Tipografía: pila de fuentes del sistema o una fuente incluida en el propio repositorio. No cargues fuentes ni librerías desde internet.
- Puedes reorganizar el HTML y el CSS cuanto quieras, **pero la lógica y los datos no cambian**: los cálculos, el PIN, las reglas del capitán y del mercado y la lectura de los JSON tienen que seguir dando exactamente los mismos resultados. Comprueba antes y después con capturas y comparando los números mostrados.
- Pensado para uso real: lo más importante de cada pestaña a la vista sin tocar nada (el capitán recomendado, la puja ideal, la clasificación), detalles plegables.
- Usa tu criterio de diseñador: jerarquía visual clara, pocas cosas por pantalla, mucho aire, un solo color de acento, estados (hover, activo, deshabilitado) cuidados.

## Prohibido
- Tocar `previa.html` (lo genera un flujo automático con una copia de tu rama).
- Tocar o leer `credenciales.env`, secretos, cookies, tokens o el hash del PIN. No los muestres en ningún texto, log ni PR.
- Cambiar los flujos de `.github/workflows/` ni el modo de funcionamiento del PIN.
- Borrar datos (`*.json`) ni cambiar su formato sin que la página siga leyéndolos igual.
- Añadir librerías o servicios externos, ni hacer peticiones a Mister (no tienes credenciales).
- Cambios de más de ~400 líneas en una sola ejecución.

## Cómo se prueba
- Sintaxis del JS: extraer el `<script>` de `index.html` a un fichero temporal y `node --check`.
- En navegador: servir la carpeta con `python -m http.server` y abrirla con Playwright (Chromium). Para ver las pestañas con PIN, teclea 9248 en el teclado de la página. Haz capturas en móvil (420 px) y revisa que no hay errores en la consola.
- El modelo (`modelo_liga.py`, `autoajuste_capitan.py`) se valida con la validación cruzada que ya imprime; no aceptes un cambio que empeore el error.
- Reglas que ya existen y no se rompen: los capitanes de una jornada ya empezada no cambian; no se recomiendan jugadores fichados después de empezar la jornada; en Mercado solo jugadores libres; el valor de jugadores por debajo de 1 M no se puede predecir.

## Estilo
Código y comentarios en español, simple, sin dependencias. Los textos de la página deben ser claros para alguien que no sabe estadística.
