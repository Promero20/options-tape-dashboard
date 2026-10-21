# 0002. Una sola lógica de agrupación

- **Fecha:** 2026-10-15 (especificación)
- **Estado:** aceptada

## Contexto

Si el dashboard agrupara los trades con su propio código, tarde o temprano divergiría del script que usa el pipeline de captura, y las operaciones del dashboard no serían las mismas que las del nivel 3.

## Decisión

El dashboard importa las funciones de `nivel3_agrupar.py` y no las reimplementa. Para poder hacerlo, el script se refactoriza (sin cambiar su salida) para exponer el cálculo por pata, el ID de operación y la separación entre agrupación y filtro por umbral.

## Alternativas descartadas

- **Reimplementar la agrupación en el dashboard**: dos lógicas que mantener en paralelo.
- **Ejecutar el script como proceso y leer su CSV**: no da acceso al detalle por pata ni permite aplicar ediciones antes del filtro.

## Consecuencias

- Cualquier cambio en la agrupación afecta a la vez al pipeline y al dashboard.
- El refactor exige un test de no regresión byte a byte (ver [0006](0006-oraculo-congelado-y-datos-sinteticos.md)).
