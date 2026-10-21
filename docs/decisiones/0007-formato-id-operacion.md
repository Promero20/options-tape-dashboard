# 0007. El ID de operación incluye la Trade Condition

- **Fecha:** 2026-10-16
- **Estado:** aceptada (modifica la especificación)

## Contexto

La especificación proponía `YYYYMMDD-SIMBOLO-HH:MM:SS.mmm` (fecha y hora del primer trade). En los datos reales ese formato no es único: hay grupos distintos que empiezan en el mismo contrato y el mismo milisegundo con Trade Conditions diferentes (p. ej. AUTO e ISOI). Ocurre en casi todos los días capturados, a veces en operaciones que superan el umbral. Las ediciones manuales apuntarían a la operación equivocada.

## Decisión

`YYYYMMDD-SIMBOLO-HH:MM:SS.mmm-TC`, donde `TC` es la Trade Condition de la operación. Lo calcula `id_operacion()` en `pipeline/nivel3_agrupar.py`.

Es único dentro de una captura por construcción: los dos mecanismos de agrupación solo unen trades de la misma condición, así que todas las filas de una operación la comparten, y dos grupos con el mismo subyacente, milisegundo y condición ya habrían quedado unidos.

## Alternativas descartadas

- **Sufijo numérico en las colisiones (`-2`, `-3`)**: depende del orden de lectura y no es estable.
- **Añadir el contrato del primer trade**: no resuelve el caso real, porque las colisiones son del mismo contrato.

## Consecuencias

- El ID cambia si cambia la lógica de agrupación; esas ediciones quedarían huérfanas (ver [0003](0003-ediciones-en-ficheros-propios.md)).
- La misma operación capturada en dos días tiene el mismo ID en ambos (ver [0010](0010-operacion-en-varias-capturas.md)).
