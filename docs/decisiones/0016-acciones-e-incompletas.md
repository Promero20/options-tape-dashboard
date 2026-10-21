# 0016. Una operación con acciones se descarta aunque tenga patas incompletas

- **Fecha:** 2026-10-19
- **Estado:** aceptada

## Contexto

La especificación manda las operaciones con acciones (`TLET`, `TLAT`, `TLCT`, `TLFT`, `TASL`, `TESL`, `TFSL`) a descartadas, y las de patas incompletas a la pestaña 2. Pero casi todas las operaciones con acciones son también «incompletas»: el script marca como incompleta cualquier multi-leg con una sola pata de opción, y en ellas la otra pata es la acción. En los datos analizados son 38 de las 39 con acciones que superan el umbral.

## Decisión

Manda la regla de las acciones: se descartan.

## Alternativas descartadas

- **Mandarlas a la pestaña 2**: la pata que falta es la acción, y el formulario solo admite opciones.

## Consecuencias

La pestaña 2 solo muestra multi-legs de opciones a las que les falta una pata de opción.
