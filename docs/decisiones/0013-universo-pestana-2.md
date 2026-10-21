# 0013. Pestaña 2: selector de día y solo operaciones por encima del umbral

- **Fecha:** 2026-10-16
- **Estado:** aceptada

## Contexto

Antes de aplicar el umbral hay unas 150 operaciones con patas incompletas por captura, casi todas de premium pequeño; después del umbral quedan unas 10. Completar cada una exige buscar a mano la pata que falta.

## Decisión

La pestaña 2 tiene su propio selector de día por fecha de captura (por defecto «hoy», con el mismo comportamiento que en [0008](0008-rangos-por-fecha-de-captura.md)) y solo lista las operaciones incompletas que superan el umbral con la pata conocida.

## Alternativas descartadas

- **Listar todas las incompletas**: demasiadas, y casi todas irrelevantes.
- **Umbral por defecto con un interruptor para ver todas**: el usuario prefiere no verlas.

## Consecuencias

Una operación que solo superaría el umbral al añadir la pata que falta no aparece en la pestaña 2.
