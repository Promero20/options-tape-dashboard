# Calidad de los datos

Lo que se encontró al contrastar la especificación con los datos reales, y cómo lo trata el dashboard. Para ver el estado actual de la carpeta de datos:

```bash
python -m tape_dashboard.report          # --info para ver también los avisos informativos
```

Lo descrito corresponde a las 15 capturas del 12/08/2026 al 15/10/2026. El repositorio no incluye datos; las frecuencias son indicadores de calidad, no datos de mercado.

## Resumen por captura

| Captura | Nivel 3 guardado frente a la reconstrucción |
|---|---|
| 12/08, 17/08 | no existe |
| 25/08 | formato antiguo (N3-A) |
| 09/09 | formato antiguo (N3-B) |
| 11/09, 15/09, 16/09, 24/09, 01/10 | equivalente |
| 22/09 | nivel 3 sin nivel 2 |
| 02/10, 07/10 | versión anterior (con la cancelación) |
| 06/10, 13/10, 15/10 | idéntico |

Son 14 capturas reconstruibles, del orden de 40.000 trades en total.

## Nivel 3 generado por versiones anteriores del script

- **Idéntico** (06/10, 13/10 y 15/10): el nivel 3 guardado coincide byte a byte con la reconstrucción.
- **Versión anterior** (02/10 y 07/10): coincide byte a byte con lo que generaba el script antes de quitar las cancelaciones (ver más abajo).
- **Equivalente** (11/09 a 01/10): mismas operaciones, en el mismo orden y con los mismos valores. Solo cambia la etiqueta de las single-leg: entonces el script escribía `single_leg` y ahora escribe `single_leg_call` o `single_leg_put`.
- **Formato antiguo**: el 25/08 no aplicaba el umbral (guarda todas las operaciones) y la agrupación era algo distinta. El 09/09 no tenía strike, expiración ni fecha de operación.
- **No existe**: el pipeline no generó nivel 3 el 12/08 ni el 17/08. Se reconstruyen igualmente desde el nivel 2.

## El 22/09 no tiene trades

Su nivel 2 solo tiene cabecera. Su nivel 3 sí guarda 30 operaciones de una versión antigua, pero sin detalle por pata. El día se descarta ([decisión 0009](decisiones/0009-descartar-22-09.md)).

## Filtro de tamaño: ≥ 10, no > 10

La especificación decía que los trades llegan filtrados con `tradeSize > 10`. Pero entre el 15 % y el 35 % de las filas de cada captura tienen tamaño exactamente 10, y ninguna es menor: el filtro real es **≥ 10**. No afecta a la lógica.

## Cancelaciones

Hay dos trades con condición `CANC`, uno en la captura del 02/10 y otro en la del 07/10. Hasta entonces no se habían observado.

- Cada uno cancela un trade anterior del mismo contrato, con el mismo tamaño y el mismo precio.
- La versión del script del 01/10 no los trataba de forma especial: el trade cancelado y la cancelación quedaban como dos operaciones, y las cuatro superaban el umbral. El nivel 3 guardado de esos días contiene, por tanto, operaciones que no llegaron a ejecutarse.
- Desde el 19/10, el script quita la cancelación y el trade que anula antes de agrupar ([decisión 0015](decisiones/0015-quitar-cancelaciones.md)). El nivel 3 guardado de esos dos días aparece en la validación como «versión anterior».

## Operaciones repetidas entre capturas

Cuatro operaciones del 14/09 aparecen en las capturas del 15/09 y del 16/09, porque el pipeline volvió a consultar los mismos contratos para esa fecha. En una de ellas el número de trades difiere entre capturas. Ninguna supera el umbral. En rangos de varios días cuenta la de la captura más reciente ([decisión 0010](decisiones/0010-operacion-en-varias-capturas.md)).

## Rarezas del nivel 2 que no cambian la lógica

| Rareza | Frecuencia | Tratamiento |
|---|---|---|
| Cotización cruzada (bid > ask) | 19 filas | Con `half_spread` negativo, el signo de la agresividad sale invertido. Se informa; no se corrige |
| Filas idénticas | 42–386 por captura | El nivel 2 no tiene ID de trade, así que no se pueden distinguir los prints legítimos repetidos (mismo milisegundo, precio, tamaño y exchange) de un duplicado de captura. Se conservan, como hace el script |
| Spread cero | 4–109 por captura | `agresividad` vacía y `spread_cero = True`: lado indeterminado |
| Códigos de exchange con salto de línea final (`"U\r"`) | 32 valores | Se recortan; el script no los usa |
| Exchange desconocido (`?`) | 37 valores, todos del 24/09 | Se mantienen tal cual |
| Exchange como letra (`C`, `N`) o como nombre (`CBOE`, `NYSE`), según la captura | | Se mantienen tal cual |

## Formatos que cambian entre capturas

Están todos recogidos en el [contrato de datos](contrato-datos.md):

- `fecha_consultada` en `MM/DD/YYYY` (09/09 a 15/09).
- `last_trade` en cuatro formatos.
- `type` en mayúsculas o minúsculas.
- `strike` con 0, 1 o 2 decimales.
- `fecha_volumen` con varias fechas separadas por `;`.

## Agrupaciones dudosas

El cruce de 50 ms con la misma Trade Condition, encadenado por el union-find, a veces une prints que no parecen de la misma orden. Por ejemplo, multi-legs con una pata de miles de contratos y otra de unas decenas. No se toca la agrupación; el listado las marcará ([decisión 0012](decisiones/0012-marcar-ratios-anomalos.md)).

## El script original en Windows

El script de nivel 3 del 01/10 escribía con la codificación por defecto del sistema. En Linux, donde corre el pipeline, es UTF-8; en Windows (cp1252) fallaba al escribir el carácter `→` de los calendars y diagonales. La versión de `pipeline/` escribe siempre en UTF-8.
