# 0011. Al completar una pata, el usuario elige el tipo de operación

- **Fecha:** 2026-10-16
- **Estado:** aceptada (modifica el formulario de la especificación)

## Contexto

La especificación pedía, para la pata que falta, un campo «lado» (comprada o vendida), y recalcular la operación «con la misma lógica». Pero el script deduce el lado de cada pata de su agresividad (precio frente a bid/ask), y una pata manual no tiene bid/ask: habría que inventarle una agresividad. Además, en órdenes multi-leg la agresividad de cada pata es una evidencia débil del lado.

## Decisión

En el formulario de la pestaña 2, el usuario introduce los datos de la pata (tipo, strike, expiración, precio y tamaño) y **elige el tipo de operación** (bull call, bear put, bull put, straddle…) de un catálogo filtrado según las patas. El tipo fija el lado de cada pata y, con él, el destino. Concretamente:

- La pata manual entra en `resumen()` del script **sin agresividad**. El script ya excluye de la media las patas sin agresividad, así que la columna «agresividad» refleja solo lo medido.
- Estructura, premium, tamaño, condiciones y horas salen del script.
- Lados, dirección, destino y precio neto salen del tipo elegido. El precio neto se calcula con la función del propio script, pasándole esos lados.
- Si el tipo elegido contradice el lado medido de la pata conocida, se avisa, pero no se impide.

## Alternativas descartadas

- **Agresividad sintética ±1 según el lado**: mezcla valores inventados con medidos en la columna de agresividad.
- **Pedir bid/ask de la pata manual**: más datos a teclear, y sigue dependiendo de la agresividad para deducir el lado.

## Consecuencias

- El catálogo de tipos y su relación con los destinos se define en la Fase 2.
- Pendiente de confirmar: usar el mismo selector en la pestaña 1 para corregir multi-legs completas.
