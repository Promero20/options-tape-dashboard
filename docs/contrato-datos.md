# Contrato de datos

Qué recibe el dashboard: el esquema canónico de cada CSV de entrada, los nombres alternativos que acepta y cómo normaliza los valores. La implementación está en [`src/tape_dashboard/data/schemas.py`](../src/tape_dashboard/data/schemas.py) y [`loading.py`](../src/tape_dashboard/data/loading.py).

## Ficheros de entrada

El pipeline de captura, que queda fuera de este repositorio, deja sus ficheros en una carpeta de datos (ver [configuración](#configuración)). El dashboard **solo la lee**. Cada fichero lleva en el nombre su **fecha de captura**, que es el día en que el pipeline tomó los datos:

| Fichero | Contenido | Uso en el dashboard |
|---|---|---|
| `nivel1_candidatos_YYYYMMDD.csv` | Contratos con aumento de open interest del día, con campos derivados | Precio del subyacente: umbral y referencia en gráficos |
| `nivel2_trades_YYYYMMDD.csv` | Time & Sales de los candidatos seleccionados | Fuente de las operaciones |
| `nivel3_operaciones_YYYYMMDD.csv` | Operaciones agrupadas por `nivel3_agrupar.py` | Solo para validar la reconstrucción |

Un CSV cuyo nombre no sigue ninguno de estos patrones se reporta como «no reconocido».

## Reglas generales

- **Codificación** UTF-8; separador `,`; la primera fila es el encabezado.
- **Columnas**: cada columna canónica acepta uno o varios nombres alternativos. El orden de las columnas no importa.
- **Columnas obligatorias**: son las que necesitan el script de nivel 3 o el dashboard. Si falta alguna, el fichero no se usa y se reporta **con su nombre y las columnas que faltan**.
- **Variantes**: cada encabezado se compara con las variantes conocidas (tablas de abajo). Uno nuevo que tenga las obligatorias se carga, pero se avisa de que es una variante nueva y de qué columnas faltan o sobran ([decisión 0014](decisiones/0014-columnas-obligatorias-y-variantes.md)).
- **Valores**: los que no se pueden interpretar quedan vacíos y se cuentan en un aviso por columna. Nunca se descartan en silencio.

## Nivel 1: candidatos

Una fila por contrato. Solo los contratos seleccionados por el pipeline (top 25 por `premium_estimado` y por encima del umbral) llevan los campos de reconciliación.

| Columna canónica | Nombres aceptados | Oblig. | Tipo normalizado | Significado |
|---|---|---|---|---|
| `symbol` | | sí | texto | Subyacente |
| `contract_symbol` | `option_symbol` | no | texto | Contrato, `SIMBOLO\|YYYYMMDD\|STRIKE.00C` o `…P`. Si falta la columna, se reconstruye con símbolo, expiración, strike y tipo |
| `price` | | sí | número | Precio del subyacente en la captura |
| `exp_date` | | sí | fecha ISO | Expiración |
| `type` | | sí | `call` / `put` | Tipo de opción (llega como `Call`/`Put`) |
| `strike` | | sí | número | Strike |
| `moneyness` | | no | número | Distancia del strike al precio, según la fuente |
| `bid`, `ask`, `mid` | | no | número | Cotización del contrato y su punto medio |
| `volume` | | no | entero | Volumen del día |
| `open_interest` | `open_int` | no | entero | Open interest |
| `oi_chg` | | no | entero | Cambio de open interest publicado |
| `vol_oi`, `iv`, `delta` | | no | número | Tal como los da la fuente |
| `last_trade` | `last_trade_ts` | no | fecha ISO | Fecha del último trade. Llega como epoch en segundos, `YYYY-MM-DD HH:MM:SS`, `YYYY-MM-DD` o `MM/DD/YY`; solo se conserva la fecha (el epoch se interpreta en UTC) |
| `premium_estimado` | | no | número | `mid × oi_chg × 100` |
| `dte` | | no | entero | Días a expiración |
| `fecha_volumen` | | no | lista de fechas ISO | Fecha o fechas reales del volumen (llegan separadas por `;`, en cualquier orden). Vacía si el contrato no se seleccionó |
| `volumen_en_fecha` | | no | entero | Volumen en esas fechas |
| `ratio_reconciliacion` | | no | número | `volumen_en_fecha / oi_chg` |
| `reconciliacion_fallida`, `reconciliacion_ambigua` | | no | booleano o vacío | Vacío si el contrato no se seleccionó |

El **precio de un subyacente** es el de la primera fila de su símbolo, como hace el script de nivel 3. En todas las capturas analizadas, todas las filas de un símbolo tienen el mismo precio.

### Variantes conocidas del nivel 1

| Variante | Capturas | Diferencias |
|---|---|---|
| N1-A | 12/08, 17/08 | `contract_symbol` en 2.ª posición, `open_int`, `last_trade_ts` (epoch) |
| N1-B | 25/08, 09/09, 11/09, 15/09 | **Sin columna de contrato** (se reconstruye), `last_trade` |
| N1-C | 16/09, 22/09 | `option_symbol`, `open_interest`, `last_trade` en `MM/DD/YY` |
| N1-D | 24/09, 01/10, 02/10, 06/10 | `contract_symbol` tras `delta`, sin `last_trade` |
| N1-E | 07/10, 13/10, 15/10 | Como N1-D, más `last_trade` al final |

## Nivel 2: Time & Sales

Una fila por trade. Las columnas que consume el script de nivel 3 **se le pasan con su valor original**, para que la reconstrucción sea idéntica a la del pipeline. Solo se normalizan las que el script no usa: `fecha_consultada` y los códigos de exchange.

| Columna canónica | Nombres aceptados | Oblig. | Valor | Significado |
|---|---|---|---|---|
| `symbol` | | sí | texto | Subyacente |
| `contract_symbol` | | sí | texto | Contrato, mismo formato que en el nivel 1 |
| `exp_date` | | sí | `YYYY-MM-DD` | Expiración |
| `strike` | | sí | texto numérico | Strike (`275.0`, `900` o `612.50` según la captura) |
| `type` | | sí | texto | `Call`/`Put` hasta el 22/09; `call`/`put` desde el 24/09 |
| `fecha_consultada` | | no | fecha ISO | Día de trading consultado. Del 09/09 al 15/09 llegó como `MM/DD/YYYY` |
| `Time` | `tradeTime` | sí | `YYYY-MM-DD HH:MM:SS.mmm` | Hora del trade, con milisegundos |
| `Trade` | `lastPrice` | sí | número | Precio de ejecución |
| `Trade Size` | `tradeSize` | sí | entero | Contratos. Solo llegan trades de **tamaño ≥ 10** (ver [calidad de datos](calidad-datos.md)) |
| `Exchange` | `lastExchange` | no | texto | Mercado de ejecución; se recortan espacios y saltos de línea |
| `Bid`, `Ask` | `bidPrice`, `askPrice` | sí | número | Mejor bid y ask en el momento del trade |
| `Bid Size`, `Ask Size` | `bidSize`, `askSize` | no | entero | |
| `Bid Exchange`, `Ask Exchange` | `bidExchange`, `askExchange` | no | texto | Recortados como `Exchange` |
| `Trade Condition` | `tradeConditionCode` | sí | código | Condición del trade (`AUTO`, `MLET`, `ISOI`…) |
| `Trade Condition Full` | `tradeCondition` | no | texto | Descripción larga. En la variante de la API, `tradeCondition` es **el texto largo**, no el código |
| `Premium` | `premium` | sí | número | `Trade × Trade Size × 100` |
| `mid`, `half_spread` | | no | número | `(Bid + Ask) / 2` y `(Ask − Bid) / 2` |
| `agresividad` | | sí | número o vacío | `(Trade − mid) / half_spread`; vacío si `Bid = Ask` |
| `spread_cero` | | no | `True`/`False` | `Bid = Ask` |
| `es_cancelacion` | | no | `True`/`False` | Condición de cancelación (`CANC`, `CNCL`, `CNCO`, `CNOL`) |
| `es_metadata_footer` | | no | `True`/`False` | Fila de pie de página de una descarga: se descarta |

Los alias de las columnas que usa el script son exactamente los de `ALIASES_COLUMNA` en `pipeline/nivel3_agrupar.py` (un test lo comprueba).

### Variantes conocidas del nivel 2

| Variante | Capturas | Diferencias |
|---|---|---|
| N2-A | 12/08 | Nombres canónicos, con `es_metadata_footer` y sin `Trade Condition Full` |
| N2-B | 17/08 | Nombres alternativos (`tradeTime`, `lastPrice`…) y las dos columnas de condición |
| N2-C | 25/08 | Canónicos, con `Trade Condition Full` y `es_metadata_footer` |
| N2-D | 09/09, 11/09, 15/09 | Canónicos, sin columnas opcionales; `fecha_consultada` en `MM/DD/YYYY` |
| N2-E | 16/09, 22/09, 24/09 en adelante | Canónicos, con `Trade Condition Full` |

## Nivel 3: operaciones

Salida de `pipeline/nivel3_agrupar.py`: una fila por operación que supera el umbral. El dashboard no la usa como fuente; la compara con su reconstrucción. El significado de cada campo está en las [reglas de negocio](reglas-negocio.md#3-agrupación-de-trades-en-operaciones).

| Variante | Capturas | Columnas |
|---|---|---|
| N3-C (vigente) | 11/09 en adelante | `symbol, estructura, n_patas, n_trades, size_total, premium_total_M, precio_neto, precio_neto_metodo, agresividad_pond, direccion, trade_conditions, multi_leg_declarado, patas_incompletas, stock_option, hora_inicio, hora_fin, duracion_s, strike, fecha_expiracion, fecha_operacion` |
| N3-B | 09/09 | Sin `strike`, `fecha_expiracion` ni `fecha_operacion`; con `patas` |
| N3-A | 25/08 | Sin filtro por umbral, con `premium_total` en dólares, sin precio neto; con `patas` |

## Operaciones reconstruidas

Por cada captura con nivel 2, el dashboard agrupa **todos** los trades con las funciones del script, también los de las operaciones que no superan el umbral (las ediciones manuales se aplican antes de filtrar). Cada operación tiene:

| Campo | Contenido |
|---|---|
| `id` | `YYYYMMDD-SIMBOLO-HH:MM:SS.mmm-TC` ([reglas de negocio](reglas-negocio.md#4-identificador-de-operación)) |
| `capture_date` | Fecha de captura (la que usan los selectores de rango) |
| `summary` | La fila de `resumen()` del script, con `premium_total` en dólares |
| `legs` | Detalle por pata de `patas_de()`: `contract_symbol, type, strike, exp_date, n_trades, size, premium, agr, precio_medio` |
| `trades` | Las filas de trade del grupo |
| `price` | Precio del subyacente en el nivel 1 de la captura |
| `passes_threshold` | Si supera el umbral de su tramo |

## Ediciones manuales

Fichero SQLite `ediciones.sqlite` en la carpeta de datos del usuario, fuera de git y fuera de la carpeta de datos del pipeline ([decisión 0019](decisiones/0019-almacen-de-ediciones.md)). Cada edición apunta a un ID de operación. Si el ID deja de existir, la edición se lista como huérfana (en el informe y, desde la Fase 3, en la interfaz) y nunca se borra.

**`overrides`**: corrección de una operación; como mucho una por operación.

| Columna | Tipo | Contenido |
|---|---|---|
| `operation_id` | texto, clave | ID de la operación |
| `direction` | `bull` / `bear` / `indeterminado` o nulo | Dirección fijada (single-leg) |
| `strategy` | texto o nulo | Tipo de operación del catálogo (multi-leg), p. ej. `bull_call` |
| `updated_at` | fecha y hora ISO | Última modificación |

Siempre hay exactamente una de las dos, `direction` o `strategy`.

**`manual_legs`**: patas añadidas a mano.

| Columna | Tipo | Contenido |
|---|---|---|
| `id` | entero, clave | Identificador de la pata |
| `operation_id` | texto | ID de la operación que completa |
| `option_type` | `call` / `put` | Tipo |
| `strike` | número > 0 | Strike |
| `exp_date` | fecha ISO | Expiración |
| `price` | número ≥ 0 | Precio de ejecución |
| `size` | entero > 0 | Contratos |
| `created_at`, `updated_at` | fecha y hora ISO | |

## Posiciones

Se definirán en la Fase 6, en la misma carpeta de datos del usuario.

## Configuración

| Ruta | Variable de entorno | Clave en `config.toml` | Por defecto |
|---|---|---|---|
| Datos del pipeline | `TAPE_DATA_DIR` | `[paths] data_dir` | `../tape_data` |
| Datos del usuario | `TAPE_USER_DATA_DIR` | `[paths] user_data_dir` | `./user_data` |

La variable de entorno tiene prioridad. La plantilla es [`config.example.toml`](../config.example.toml).
