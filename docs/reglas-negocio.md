# Reglas de negocio

Reglas que aplican el pipeline de captura y el dashboard. La implementación de referencia de la agrupación es [`pipeline/nivel3_agrupar.py`](../pipeline/nivel3_agrupar.py): el dashboard importa sus funciones y no las reimplementa.

## 1. Umbral de premium por precio del subyacente

Una operación solo es relevante si su premium total (en dólares, sumando todas sus patas) alcanza el umbral del tramo de precio de su subyacente. El precio sale del nivel 1 del mismo día de captura.

| Precio del subyacente | Umbral | Intervalo exacto que aplica el script |
|---|---|---|
| $1 – $50 | ≥ $500.000 | `1 ≤ precio < 50` |
| $50 – $200 | ≥ $1.000.000 | `50 ≤ precio < 200` |
| > $200 | ≥ $3.000.000 | `precio ≥ 200`, **y también `precio < 1`** |

Detalles que fija el script (`umbral_premium` y `pasa_umbral`):

- Los límites de $50 y $200 pertenecen al tramo superior: a $50 se exige 1 M y a $200 se exigen 3 M.
- Un precio por debajo de $1 cae en el tramo de 3 M. La especificación no define ese caso y probablemente no es intencionado. Corregirlo cambiaría la salida del script, así que queda como decisión pendiente; hasta ahora no ha aparecido ningún subyacente por debajo de $1.
- Si un símbolo del nivel 2 no tiene precio en el nivel 1, la operación **no se descarta**.
- El umbral se compara con el premium **bruto** en dólares. La conversión a millones (`premium_total_M`) es solo de presentación.

Ejemplos: con el subyacente a $30, una operación de $500.000 pasa y una de $499.999,99 no. A $50 exactos, una de $999.999 no pasa.

## 2. Agresividad y lado de cada trade

Para cada trade del nivel 2:

```
mid         = (bid + ask) / 2
half_spread = (ask − bid) / 2
agresividad = (precio del trade − mid) / half_spread
```

- `+1`: ejecutado en el ask (comprador agresivo). `−1`: ejecutado en el bid (vendedor agresivo). Por encima de `+1` o por debajo de `−1`: pagando más que el ask o vendiendo por debajo del bid.
- Si `bid = ask`, la agresividad queda vacía (`spread_cero = True`). No se pone 0, porque 0 significaría "cerca del punto medio".
- Una pata es **comprada** si su agresividad es > +0,25, **vendida** si es < −0,25, e **indeterminada** entre ambos valores (`ZONA_MUERTA = 0.25`).
- La agresividad de una pata es la media de las de sus trades ponderada por tamaño, contando solo los trades que la tienen.

## 3. Agrupación de trades en operaciones

**Antes de agrupar se quitan las cancelaciones.** Una fila con condición `CANC`, `CNCL`, `CNCO` o `CNOL` no es un trade: anula uno anterior. Se quitan la cancelación y el trade que anula, que es el más reciente anterior con el mismo contrato, tamaño y precio ([decisión 0015](decisiones/0015-quitar-cancelaciones.md)).

Un grupo de trades es una operación: lo que parece ser una única orden o un único actor. Hay dos mecanismos, que se combinan con union-find (si un trade queda enlazado por cualquiera de los dos, todo su grupo se une):

**A) Patas de una orden multi-leg.** Trades de contratos **distintos** del mismo subyacente, con la **misma Trade Condition** y separados como mucho por **50 ms** (`TOL_MS`). Una orden multi-leg imprime todas sus patas en el mismo instante y con el mismo código de mecanismo.

**B) Troceado dentro de un contrato.** Trades del **mismo** contrato, con la **misma Trade Condition** y separados como mucho por **120 s** (`VENTANA_S`) del anterior.

Consecuencia: **todas las filas de una operación comparten la misma Trade Condition**, porque los dos mecanismos solo unen trades de la misma condición.

Ejemplo: una call comprada en tres trades AUTO a las 10:00:00, 10:01:00 y 10:02:30 es una sola operación (cada trade está a menos de 120 s del anterior). Otro trade AUTO del mismo contrato a las 10:10:00 es una operación aparte.

### Datos que calcula el script por operación

- **Estructura** inferida de los contratos: `single_leg_call` o `single_leg_put`, `vertical` (mismo tipo y expiración), `calendar/diagonal` (más de una expiración), `straddle` (call + put en el mismo strike) y `straddle/strangle/risk-reversal` (call + put en strikes distintos).

  Es una etiqueta orientativa, sin el lado de cada pata. Por ejemplo, `vertical` también cubre tres patas del mismo tipo y expiración. Las reglas de clasificación (Fase 2) usarán el detalle por pata, no esta etiqueta.
- **Patas incompletas**: hay alguna Trade Condition multi-leg (`MLET`, `MLAT`, `MLFT`, `MESL`, `MLCT`, `MFSL`, o las de opciones con acciones) y solo se ha capturado una pata.
- **Con acciones** (`stock_option`): alguna condición de opciones con acciones (`TLET`, `TLAT`, `TLCT`, `TLFT`, `TASL`, `TESL`, `TFSL`).
- **Dirección** (`direccion`): sale de la pata con más premium. Si es comprada, call = bull y put = bear; si es vendida, al revés; en la zona muerta, `indeterminado`.
- **Precio neto**:
  - Single-leg: precio medio ponderado por tamaño.
  - Multi-leg: suma de los precios medios con signo (+ si la pata se compró, − si se vendió). Solo se calcula si todas las patas tienen lado claro.
  - Vacío si faltan patas o si algún lado es ambiguo.

## 4. Identificador de operación

Cada operación tiene un ID estable, que es al que apuntan las ediciones manuales y las posiciones:

```
YYYYMMDD-SIMBOLO-HH:MM:SS.mmm-TC        p. ej. 20261013-XYZ-11:00:00.100-MLET
```

Son la fecha y hora con milisegundos del **primer trade** de la operación, su subyacente y su Trade Condition.

- La Trade Condition hace falta porque en los datos reales hay grupos distintos que empiezan en el mismo contrato y el mismo milisegundo con condiciones diferentes (p. ej. AUTO e ISOI).
- Con ella, el ID es **único dentro de una captura por construcción**: dos grupos con el mismo subyacente, milisegundo y condición ya habrían quedado unidos por el mecanismo A o el B.
- La misma operación puede aparecer en dos capturas si el pipeline consultó el mismo contrato y la misma fecha dos veces. En ese caso tiene el mismo ID en ambas, y el dashboard se queda con la captura más reciente.

Ver la [decisión 0007](decisiones/0007-formato-id-operacion.md).

## 5. Clasificación de operaciones

Implementación: [`src/tape_dashboard/rules/`](../src/tape_dashboard/rules/). Cada operación por encima del umbral va a **un único destino** ([decisión 0004](decisiones/0004-un-destino-por-operacion.md)), así que ningún premium se cuenta dos veces:

| Destino | Dónde se ve |
|---|---|
| `neto` | Gráfico de neto direccional: premium con signo (bull +, bear −) en su strike y expiración |
| `paredes` | Gráfico de paredes: premium por strike vendido, como soporte o resistencia |
| `indeterminada` | Single-leg sin lado claro: marca propia en el gráfico de neto, en su strike y expiración |
| `indeterminada multi-leg` | Total aparte (premium bruto) |
| `descartada` | Total aparte (premium bruto) |
| `pendiente` | Pestaña 2, hasta completar la pata que falta |

### Lado de cada pata

Una pata es **comprada** si su agresividad es > +0,25, **vendida** si es < −0,25, e **indeterminada** entre ambas, en la frontera o sin dato.

La agresividad se calcula con coma flotante, así que un trade a un cuarto del half-spread sale como 0,2499999… o como 0,2500000…3. Hay 37 patas así en los datos reales. Se aplica una tolerancia de 10⁻⁹ para que la frontera sea siempre indeterminada, como dice la especificación ([decisión 0017](decisiones/0017-frontera-de-la-agresividad.md)).

### Reglas, por orden de precedencia

| # | Caso | Destino | Strike | Expiración | Premium |
|---|---|---|---|---|---|
| 1 | Con acciones (`TLET`, `TLAT`, `TLCT`, `TLFT`, `TASL`, `TESL`, `TFSL`), aunque tenga patas incompletas ([0016](decisiones/0016-acciones-e-incompletas.md)) | descartada | — | — | bruto |
| 2 | Patas incompletas (multi-leg declarada con una sola pata) | pendiente | — | — | bruto |
| 3 | Tres patas o más | descartada | — | — | bruto |
| 4 | Single-leg comprada | neto (call = bull, put = bear) | el suyo | la suya | total |
| 5 | Single-leg vendida | paredes (put = soporte, call = resistencia) | el suyo | la suya | total |
| 6 | Single-leg con lado indeterminado | indeterminada | el suyo | la suya | total |
| 7 | Call + put: straddle, strangle, sintético, risk reversal, o con distinta expiración ([0022](decisiones/0022-call-put-y-sinteticos.md)) | descartada, sea cual sea el lado | — | — | bruto |
| 8 | Calendar puro (mismo tipo y strike, distinta expiración) | descartada, sea cual sea el lado | — | — | bruto |
| 9 | Vertical o diagonal con alguna pata indeterminada | indeterminada multi-leg | — | — | bruto |
| 10 | Vertical o diagonal con las dos patas del mismo lado ([0020](decisiones/0020-correccion-de-multi-legs.md)) | indeterminada multi-leg | — | — | bruto |
| 11 | Vertical de débito (pata comprada > pata vendida) | neto | pata comprada | común | comprada − vendida |
| 12 | Vertical de crédito (pata vendida > pata comprada) | paredes | pata vendida | común | vendida − comprada |
| 13 | Diagonal (lados claros), también de crédito ([0018](decisiones/0018-diagonales-de-credito.md)) | neto, con la dirección de la pata de más premium | pata comprada | la más cercana | \|comprada − vendida\| |

Si una vertical tiene el mismo premium en las dos patas (ni débito ni crédito), va a indeterminadas multi-leg.

**Dirección.** En el neto, la del signo. En las paredes, una put vendida o un bull put spread es alcista (soporte) y una call vendida o un bear call spread es bajista (resistencia). Las indeterminadas son `indeterminado`; las descartadas y pendientes no tienen. **Esta es la dirección que muestra y edita el listado**; la columna `direccion` del script (que sale solo de la pata de más premium) queda como dato secundario ([decisión 0021](decisiones/0021-direccion-del-listado.md)).

### Ejemplos

- **Bear put de la especificación**: put 100 comprada por 10 M y put 90 vendida por 5 M. Vertical de débito: neto, strike 100, −5 M (bajista).
- **Bull put spread**: put 100 vendida por 6 M y put 90 comprada por 2 M. Vertical de crédito: paredes, soporte en el strike 100, 4 M.
- **Diagonal de crédito**: call 125 de enero comprada por 1 M y call 130 de noviembre vendida por 1,5 M. Neto en el strike 125, expiración de noviembre. La pata de más premium es la call vendida, así que es bajista: −0,5 M.
- **Long straddle**: call y put del mismo strike, las dos compradas. Descartada.

### Correcciones manuales

- **Single-leg**: el usuario fija la dirección, y con ella el lado. Bull sobre una call = comprada (neto); bull sobre una put = vendida (paredes, soporte); bear sobre una call = vendida (paredes, resistencia); bear sobre una put = comprada (neto); indeterminado = indeterminada.
- **Dos patas**: el usuario elige el **tipo de operación** de un catálogo filtrado por la geometría de las patas ([decisiones 0011](decisiones/0011-pata-manual-tipo-de-operacion.md) y [0020](decisiones/0020-correccion-de-multi-legs.md)). El tipo fija el lado de cada pata y la operación se clasifica con las mismas reglas.

| Geometría | Tipos que se ofrecen |
|---|---|
| Vertical de calls | bull call (débito: compra el strike bajo), bear call (crédito: vende el strike bajo) |
| Vertical de puts | bear put (débito: compra el strike alto), bull put (crédito: vende el strike alto) |
| Diagonal | compra el vencimiento cercano, compra el vencimiento lejano |
| Calendar | largo (compra el lejano), corto (vende el lejano) |
| Call + put, mismo strike | straddle comprado o vendido, sintético largo o corto |
| Call + put, strikes distintos | strangle comprado o vendido, risk reversal alcista o bajista |
| Call + put, distinta expiración | compra la call y vende la put, al revés, compra las dos, vende las dos |
| Cualquiera | no lo sé (indeterminada multi-leg) |

Si el tipo elegido contradice el lado medido de una pata (por ejemplo, la agresividad dice compra y el tipo dice venta), se avisa, pero se respeta la elección. Si las patas cambian y el tipo deja de encajar (por ejemplo, porque se borró una pata manual), la corrección se ignora con un aviso, pero no se borra.

Las correcciones no se aplican a operaciones pendientes: primero hay que completar la pata.

### Patas añadidas a mano

Una pata manual entra en la operación como una fila de trade más: con la hora y la Trade Condition del primer trade (así el ID no cambia) y **sin agresividad**. Estructura, premium, tamaño y horas se recalculan con las funciones del script. La columna «agresividad» sigue reflejando solo lo medido, porque el script excluye de la media las patas sin dato. El lado lo fija el tipo de operación elegido.

### Ratio de tamaños anómalo

Una multi-leg cuya pata más grande tiene **10 veces o más** contratos que la más pequeña se marca para revisión ([decisión 0012](decisiones/0012-marcar-ratios-anomalos.md)). En los datos reales, las multi-leg por encima del umbral tienen ratios de 1 a 5,9, y a partir de ahí saltan a 11,9 y más. No cambia el destino.
