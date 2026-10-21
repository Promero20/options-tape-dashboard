# 0021. El listado muestra la dirección de la clasificación

- **Fecha:** 2026-10-19
- **Estado:** aceptada

## Contexto

El script calcula `direccion` solo con la pata de más premium. A veces eso no cuadra con el destino: una multi-leg con una pata indeterminada puede salir «bull» y, sin embargo, ir a indeterminadas.

## Decisión

La columna «dirección» del listado es la que resulta de la clasificación, coherente con el destino, y es la que edita el usuario. La `direccion` del script se conserva como columna secundaria.

## Alternativas descartadas

- **Mostrar la del script**: el destino no cuadraría con la dirección que se ve.

## Consecuencias

Las dos columnas pueden diferir. La diferencia es informativa, no un error.
