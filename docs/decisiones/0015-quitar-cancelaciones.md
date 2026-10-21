# 0015. Las cancelaciones se quitan en el script, junto con el trade que anulan

- **Fecha:** 2026-10-19
- **Estado:** aceptada (cambia a propósito la salida del script de nivel 3)

## Contexto

En las capturas del 02/10 y del 07/10 hay un trade con condición `CANC`. Cada uno anula un trade anterior del mismo contrato, mismo tamaño y mismo precio. El script los agrupaba como trades normales, de modo que el nivel 3 de esos días contenía dos operaciones por encima del umbral que no llegaron a ejecutarse: el trade anulado y la propia cancelación.

## Decisión

Antes de agrupar, `quitar_cancelaciones()` en `pipeline/nivel3_agrupar.py` quita cada fila con condición de cancelación (`CANC`, `CNCL`, `CNCO`, `CNOL`) y el trade que anula. Ese trade es el más reciente anterior a la cancelación con el mismo contrato, tamaño y precio, porque el tape no indica cuál es. Si no se encuentra, la cancelación se quita igualmente y se avisa. La consola añade una línea con el recuento.

Como el cambio está en el script, el pipeline y el dashboard ven lo mismo.

## Alternativas descartadas

- **Quitarlas solo en el dashboard**: el nivel 3 del pipeline seguiría mostrando operaciones que no existieron, y habría dos lógicas.
- **Dejarlas y marcarlas en el listado**: el premium contaría igualmente en los gráficos.

## Consecuencias

- El test de no regresión compara ahora el script con la versión congelada ejecutada sobre el mismo nivel 2 **sin las cancelaciones ni los trades que anulan**. Si no hay cancelaciones, es el mismo fichero y la salida sigue siendo idéntica byte a byte. Así se demuestra que este es el único cambio, sin congelar una versión nueva.
- La validación reconoce los nivel 3 generados antes del cambio («versión anterior»).
- Hay que desplegar el script en el pipeline ([level3-script.md](../level3-script.md)).
