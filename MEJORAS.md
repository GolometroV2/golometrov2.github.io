# Registro de mejoras del agente

El agente lee este archivo al empezar y lo actualiza al terminar.

## Hecho
- (el agente irá añadiendo aquí cada mejora con su fecha)
- 2026-11-04: en móvil (360 px) la barra de pestañas se desplaza y, al pulsar Mercado, se reiniciaba y la pestaña activa quedaba fuera de pantalla. Ahora se centra la pestaña activa. Probado con Playwright a 360 px, sin errores de consola. El resto de la página no desborda.
- 2026-11-04: quitada la carga de la fuente Inter desde Google Fonts (CLAUDE.md prohíbe recursos externos); ahora pila de fuentes del sistema. Añadido `prefers-reduced-motion`. Probado a 360 px: sin desborde ni errores de consola. Idea: si se quiere una fuente propia, incluirla en el repositorio.

## Ideas del dueño (máxima prioridad, léelas siempre)
- Rehacer el diseño completo de forma profesional, moderna y actual (ver sección DISEÑO de CLAUDE.md). Fases: 1 sistema de diseño, 2 cabecera y navegación, 3 Clasificación, 4 Equipos, 5 Capitán, 6 Mercado, 7 microinteracciones y accesibilidad, 8 revisión final.

## Ideas pendientes (de más a menos valor)
1. Revisar que cada pestaña se ve bien en móvil pequeño (360 px) y corregir lo que se corte.
2. Historial de pujas ideales frente al precio real de cierre (cuando haya datos suficientes) para calibrar la puja.
3. Resumen automático de la jornada: mejor y peor plantilla, mejor capitán, mayor fichaje.
4. Comparador de dos jugadores (puntos esperados, valor, partido).
5. Gráfico de la evolución del valor de plantilla de cada manager.
