# Golómetro V2 · reglas para el agente

Proyecto: página de una liga de Mister Fantasy. Una sola página (`index.html`, sin librerías externas de datos) que lee los JSON que generan los scripts de Python y GitHub Actions. Idioma de la página y de los textos: **español de España**. Pestañas: Clasificación, Equipos (PIN), Capitán (PIN), Mercado (PIN).

## Qué tienes que hacer en cada ejecución
1. Lee `MEJORAS.md` (lo hecho y las ideas pendientes) y los datos de los JSON.
2. Elige **UNA sola mejora** con valor real para los jugadores de la liga. Prioriza: errores y datos raros > precisión del modelo (capitán y mercado) > herramientas nuevas (por ejemplo comparadores, histórico de pujas, resumen de jornada) > diseño.
3. Impleméntala en una rama nueva `agente/AAAA-MM-DD`, probándola de verdad (ver abajo).
4. Anota en `MEJORAS.md` qué hiciste, por qué y qué ideas nuevas has visto. Mantén la lista de ideas pendientes ordenada.
5. Abre una Pull Request con `gh pr create` explicando en 5 líneas qué cambia y cómo lo has probado. **Nunca subas directo a `main`.**

## Prohibido
- Tocar o leer `credenciales.env`, secretos, cookies, tokens o el hash del PIN. No los muestres en ningún texto, log ni PR.
- Cambiar los flujos de `.github/workflows/` ni el modo de funcionamiento del PIN.
- Borrar datos (`*.json`) ni cambiar su formato sin que la página siga leyéndolos igual.
- Añadir librerías o servicios externos, ni hacer peticiones a Mister (no tienes credenciales).
- Cambios de más de ~400 líneas, o varias mejoras en una misma PR.
- Reescribir el diseño entero: mejora poco a poco y mantén el estilo actual (oscuro, tarjetas, verde de acento).

## Cómo se prueba
- Sintaxis del JS: extraer el `<script>` de `index.html` a un fichero temporal y `node --check`.
- En navegador: servir la carpeta con `python -m http.server` y abrirla con Playwright (Chromium). Para ver las pestañas con PIN, teclea 9248 en el teclado de la página. Haz capturas en móvil (420 px) y revisa que no hay errores en la consola.
- El modelo (`modelo_liga.py`, `autoajuste_capitan.py`) se valida con la validación cruzada que ya imprime; no aceptes un cambio que empeore el error.
- Reglas que ya existen y no se rompen: los capitanes de una jornada ya empezada no cambian; no se recomiendan jugadores fichados después de empezar la jornada; en Mercado solo jugadores libres; el valor de jugadores por debajo de 1 M no se puede predecir.

## Estilo
Código y comentarios en español, simple, sin dependencias. Los textos de la página deben ser claros para alguien que no sabe estadística.
