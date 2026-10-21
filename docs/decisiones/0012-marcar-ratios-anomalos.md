# 0012. Se marcan las multi-leg con ratio de tamaños anómalo

- **Fecha:** 2026-10-16
- **Estado:** aceptada

## Contexto

El cruce de 50 ms con la misma Trade Condition, combinado con el union-find, puede unir prints que solo coinciden por casualidad. En los datos reales hay «diagonales» con una pata de miles de contratos y otra de unas decenas: es improbable que sean una sola orden.

## Decisión

La agrupación no se toca (regla 3). El listado marca visualmente las operaciones multi-leg en las que la pata más grande tiene **10 veces o más** contratos que la más pequeña, para que el usuario las revise y, si hace falta, corrija su tipo.

El corte sale de los datos: las multi-leg por encima del umbral tienen ratios de 1 a 5,9 (las ratio spreads reales no suelen pasar de 1:3), y a partir de ahí saltan a 11,9, 21,9, 30 y hasta más de 300.

## Alternativas descartadas

- **Partir esos grupos automáticamente**: sería una segunda lógica de agrupación.

## Consecuencias

Es una ayuda visual; no cambia la clasificación por sí misma. En las capturas analizadas se marcan 9 operaciones por encima del umbral.
