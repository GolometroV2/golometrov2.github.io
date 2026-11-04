# Registro de mejoras del agente

El agente lee este archivo al empezar y lo actualiza al terminar.

## En curso (lo está haciendo Claude a mano: NO lo toques, elige otra cosa)
- Fase 5 Capitán (tarjeta destacada), Duelo cara a cara, fase 6 Mercado, gráfica de valor de plantilla en Equipos.

## Hecho
- (el agente irá añadiendo aquí cada mejora con su fecha)
- 2026-11-04: en móvil (360 px) la barra de pestañas se desplaza y, al pulsar Mercado, se reiniciaba y la pestaña activa quedaba fuera de pantalla. Ahora se centra la pestaña activa. Probado con Playwright a 360 px, sin errores de consola. El resto de la página no desborda.
- 2026-11-04: quitada la carga de la fuente Inter desde Google Fonts (CLAUDE.md prohíbe recursos externos); ahora pila de fuentes del sistema. Añadido `prefers-reduced-motion`. Probado a 360 px: sin desborde ni errores de consola. Idea: si se quiere una fuente propia, incluirla en el repositorio.
- 2026-11-04 (rediseño fase 1/8, sistema de diseño): variables CSS de color (oscuro y claro automático con `prefers-color-scheme`), de radios, sombra y espaciado; los tintes y colores fijos (insignias, tooltip, gráfico SVG, avisos) ahora salen de variables; botones y pestañas con 44 px táctiles. Lógica y datos intactos. Probado a 390 px en oscuro y claro: sin errores de consola ni scroll horizontal. Siguiente: fase 2 (cabecera y navegación).
- 2026-11-04 (rediseño fase 2/8, cabecera y navegación): cabecera translúcida con logo SVG propio, pestañas tipo control segmentado con la activa en acento, título más marcado. Corregido un fallo de la fase 1: en modo oscuro las variables `--accBg`, `--redBg`... se referenciaban a sí mismas (inválidas) y los tintes de insignias no se veían; ahora tienen sus valores. Probado a 360/420/1280 px, oscuro y claro, sin errores ni scroll horizontal. Siguiente: fase 3 (Clasificación).
- 2026-11-04 (rediseño fase 3/8, Clasificación): filas como tarjetas con medalla oro/plata/bronce, líder resaltado, barra fina de puntos relativa al líder, selector «Ordenar por» más compacto y con etiqueta, detalle desplegable integrado en la tarjeta. Los números no cambian (solo HTML/CSS). Probado a 360 (oscuro) y 420 px (claro): sin errores de consola ni scroll horizontal. La rama `agente/semana` se rehízo desde `main` (la PR anterior ya estaba fusionada) recuperando las fases 1 y 2. Siguiente: fase 4 (Equipos).
- 2026-11-04 (hecho a mano por Claude, fases 1 y 2 del rediseño): paleta «Noche de estadio» (azul de foco + amarillo de tarjeta como único acento, verde/rojo solo para sube/baja, modo claro incluido), tarjetas con borde fino sin sombra, marcador con cifras tabulares en la clasificación y **navegación inferior** con icono sobre texto para el pulgar. Próxima fase: 3 (Clasificación: filas y cabecera de jornada).
- 2026-11-04 (a mano por Claude, petición del dueño): **La carrera** (la gráfica de evolución rehecha: posición jornada a jornada con curvas, distancia al líder y mapa de calor por jornada; tocar un manager lo resalta), **Capitanes de la temporada** (podio con foto y escudo, lista con caras, vistas «Fallos» y «Por manager» con barras por jornada) y funcionalidad nueva **Crónica de la jornada** (ganador, mejor capitán, jugador de la jornada, remontada, batacazo, lluvia de goles y farolillo rojo, con flechas para cambiar de jornada). Fotos: `fotos/indice.json` (lo genera `seguimiento_equipos.py`) + CDN de Mister como respaldo.
- 2026-11-04 (rediseño fase 4/8, Equipos): selector de manager en una sola fila con scroll horizontal (antes ocupaba media pantalla), resumen con tarjetas y barra de valor relativa al mayor, cabecera de manager y jugadores como tarjetas. Solo HTML/CSS: valores y tendencias idénticos. Probado a 360 (oscuro) y 420 px (claro), sin errores ni scroll horizontal. Siguiente: fase 5 (Capitán, sobre la lista única de riesgo).
- 2026-11-04 (rediseño fase 5/8, Capitán): sobre la lista única de riesgo, el mejor capitán va destacado arriba con la etiqueta «Capitán recomendado», su porqué en una frase y foto grande; el detalle (coste, beneficio, riesgo) queda plegado en «Ver por qué»; el selector de manager pasa a una sola fila deslizable. Solo HTML/CSS: puntos extra, orden y cálculos idénticos. Probado a 360 (oscuro) y 420 px (claro), sin errores de consola ni scroll horizontal. Siguiente: fase 6 (Mercado).

## Ideas del dueño (máxima prioridad, léelas siempre)
- Capitán con un solo algoritmo de riesgo (sin pestañas de modo): ya implementado en main; el rediseño de Capitán debe partir de esa lista única. Ver CLAUDE.md.
- Rehacer el diseño completo de forma profesional, moderna y actual (ver sección DISEÑO de CLAUDE.md). Fases: 1 sistema de diseño, 2 cabecera y navegación, 3 Clasificación, 4 Equipos, 5 Capitán, 6 Mercado, 7 microinteracciones y accesibilidad, 8 revisión final.

## Ideas pendientes (de más a menos valor)
1. Revisar que cada pestaña se ve bien en móvil pequeño (360 px) y corregir lo que se corte.
2. Historial de pujas ideales frente al precio real de cierre (cuando haya datos suficientes) para calibrar la puja.
3. Resumen automático de la jornada: mejor y peor plantilla, mejor capitán, mayor fichaje.
4. Comparador de dos jugadores (puntos esperados, valor, partido).
5. Gráfico de la evolución del valor de plantilla de cada manager.
