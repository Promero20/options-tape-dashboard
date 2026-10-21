# 0004. Cada operación va a un único destino

- **Fecha:** 2026-10-15 (especificación)
- **Estado:** aceptada

## Contexto

Los gráficos de la pestaña 1 suman premium por strike o por expiración. Si una operación contara a la vez en el neto direccional y en las paredes, ese premium se contaría dos veces.

## Decisión

Cada operación va a uno solo de estos destinos: neto direccional, paredes, total de indeterminadas o total de descartadas. Las patas incompletas sin completar quedan pendientes en la pestaña 2. La tabla de reglas está en la [especificación](../../specification.md#classification-rules).

## Consecuencias

- La suma de premium de todos los destinos debe ser igual al premium total (se comprobará con un test en la Fase 2).
- Los casos reales que la tabla no cubre se resuelven antes de la Fase 2.
