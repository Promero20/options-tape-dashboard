# 0010. Una operación repetida en varias capturas cuenta una vez

- **Fecha:** 2026-10-16
- **Estado:** aceptada

## Contexto

Si el mismo contrato aparece en el nivel 1 de dos días seguidos con la misma `fecha_volumen`, el pipeline obtiene su Time & Sales dos veces, y la misma operación sale en las dos capturas con el mismo ID. Ya ha ocurrido entre las capturas del 15/09 y el 16/09.

## Decisión

En un rango de varios días, una operación con el mismo ID en varias capturas se cuenta una sola vez: se conserva la de la **captura más reciente** y se avisa en el informe de datos.

## Alternativas descartadas

- **Conservar la primera captura**: la más reciente es la que el usuario ha revisado por última vez en la pestaña «hoy».
- **No deduplicar**: el premium se contaría dos veces en los gráficos.

## Consecuencias

La deduplicación se hace en la capa de datos (Fase 1). En «hoy» no aplica, porque solo hay una captura.
