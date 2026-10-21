# 0008. Los selectores de rango usan la fecha de captura

- **Fecha:** 2026-10-16
- **Estado:** aceptada (modifica un supuesto de la especificación)

## Contexto

La especificación suponía que los selectores filtran por la fecha de la operación, es decir, cuándo se negoció. Pero el cambio de open interest se publica con retraso: la captura de un día contiene trades de 1 a 4 días hábiles antes. Con ese criterio, el selector «hoy» estaría siempre vacío.

## Decisión

Todos los selectores de rango (hoy, última semana, último mes, personalizado), en las pestañas 1 y 2 y en los gráficos, filtran por la **fecha de captura**. «Hoy» es la captura de hoy; si todavía no la hay (fin de semana, festivo o el pipeline aún no ha corrido), se muestra la última captura con un aviso visible. La fecha de la operación se sigue mostrando como columna.

## Alternativas descartadas

- **«Hoy» por captura y el resto por fecha de operación**: dos criterios distintos en la misma pantalla.

## Consecuencias

- Cada operación pertenece a una captura.
- En rangos de varios días puede aparecer la misma operación en dos capturas (ver [0010](0010-operacion-en-varias-capturas.md)).
