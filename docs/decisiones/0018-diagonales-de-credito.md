# 0018. Diagonales de crédito: la dirección es la de la pata de más premium

- **Fecha:** 2026-10-19
- **Estado:** aceptada

## Contexto

La especificación manda todas las diagonales al neto direccional, también las de crédito, en el strike de la pata comprada, con la expiración más cercana y un premium de «comprada − vendida». En una diagonal de crédito esa resta es negativa, y la especificación no dice qué dirección tiene. Por ejemplo: call lejana comprada por 1 M y call cercana vendida por 1,5 M.

## Decisión

- **Dirección**: la de la pata con más premium, que es la misma que calcula el script. Si domina la pata comprada, call = bull y put = bear; si domina la vendida, call vendida = bear y put vendida = bull.
- **Importe**: |comprada − vendida|, con el signo de esa dirección.
- **Strike y expiración**: los de la especificación (pata comprada, expiración más cercana).

En el ejemplo: −0,5 M (bajista) en el strike de la call comprada.

## Alternativas descartadas

- **Llevar las diagonales de crédito a paredes**, como las verticales de crédito: contradice el supuesto explícito de la especificación.
- **Usar la dirección de la pata comprada con importe negativo**: un «bull» con premium negativo no se puede representar en barras divergentes.

## Consecuencias

En las diagonales de débito el resultado es el mismo que con la regla literal de la especificación. En las capturas analizadas hay una diagonal de crédito por encima del umbral.
