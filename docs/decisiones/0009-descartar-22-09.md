# 0009. El 22/09 se descarta

- **Fecha:** 2026-10-16
- **Estado:** aceptada

## Contexto

`nivel2_trades_20260922.csv` solo tiene cabecera, sin trades. Su `nivel3_operaciones_20260922.csv` sí contiene 30 operaciones, generadas por una versión antigua del script: no traen detalle por pata, y la estructura de las single-leg no indica si son call o put.

## Decisión

El 22/09 se descarta, como indica la especificación. El informe de datos lo mostrará como «nivel 3 sin nivel 2».

## Alternativas descartadas

- **Importar las 30 operaciones del nivel 3 en modo degradado**: no se podrían clasificar con fiabilidad (falta el lado de cada pata y, en las single-leg, el tipo), y abriría un segundo camino de carga solo para un día.

## Consecuencias

Esas 30 operaciones no aparecen en el dashboard. Si más adelante se quisieran, se revisaría esta decisión.
