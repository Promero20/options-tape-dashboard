# 0022. Call + put con distinta expiración y sintéticos se descartan, como los risk reversals

- **Fecha:** 2026-10-19
- **Estado:** aceptada, a la espera de la decisión sobre risk reversals

## Contexto

La especificación descarta straddles, strangles y risk reversals, y deja pendiente si el risk reversal debe ir al neto. No menciona otras dos combinaciones de call + put que aparecen en los datos:

- con **distinta expiración**: hay una por encima del umbral, que el script etiqueta `calendar/diagonal`;
- con el **mismo strike y lados opuestos** (sintético largo o corto): el script lo etiqueta `straddle`.

Ambas tienen una dirección clara, igual que el risk reversal.

## Decisión

Se descartan, igual que los risk reversals hoy. Cuando se decida sobre los risk reversals, se revisarán con ellos.

## Alternativas descartadas

- **Llevarlas ya al neto**: adelantaría la decisión pendiente sobre risk reversals, que corresponde al usuario.

## Consecuencias

En las capturas analizadas, la única afectada por encima del umbral es la combinación con distinta expiración.
