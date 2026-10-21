# 0017. Una agresividad de exactamente ±0,25 es lado indeterminado

- **Fecha:** 2026-10-19
- **Estado:** aceptada

## Contexto

La especificación dice que una pata es comprada si su agresividad es **> +0,25**: la frontera es indeterminada. El script de nivel 3 usa `abs(agr) < 0,25` para su columna `direccion` y para el precio neto, así que ahí la frontera cuenta como lado claro.

Además, la agresividad se calcula con coma flotante, y un trade a un cuarto del half-spread sale como 0,2499999999999989 o como 0,25000000000000333, según el redondeo. En los datos reales hay 37 patas así, y el script las clasifica por ese ruido.

## Decisión

La clasificación del dashboard sigue la especificación: la frontera es indeterminada, con una tolerancia de 10⁻⁹ para absorber el ruido de coma flotante.

El script no se toca: cambiarlo alteraría su salida (columnas `direccion` y `precio_neto`). Si se quiere alinear, se decidirá aparte.

## Alternativas descartadas

- **Seguir la convención del script**: contradice la especificación y depende del redondeo.

## Consecuencias

En esas patas, la columna `direccion` del script puede decir bull o bear mientras la clasificación dice indeterminado. El listado muestra la de la clasificación ([0021](0021-direccion-del-listado.md)).
