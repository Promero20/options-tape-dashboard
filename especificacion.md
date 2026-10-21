# Dashboard Tape Reading — Especificación

Oct 15, 2026 · @Pablo Romero

## Contexto

El dashboard es una aplicación local que lee los CSV diarios que genera un pipeline de captura de flujo de opciones y los muestra en tres pestañas: operaciones detectadas, operaciones por completar y posiciones reales.

El pipeline de captura queda fuera de este repositorio. Entrega tres niveles de ficheros:

1. **Nivel 1 — candidatos.** Tabla completa de contratos con aumento de open interest del día. Se calcula `premium_estimado = mid × oi_chg × 100`, se toma el top N (hoy N=25) y se filtra por umbral de premium según el precio del subyacente. Para los seleccionados se identifica la fecha real del volumen (`fecha_volumen`). Fichero: `nivel1_candidatos_YYYYMMDD.csv`.
2. **Nivel 2 — trades.** Time & Sales de cada candidato reconciliado en su `fecha_volumen` (solo trades de tamaño ≥ 10), con `agresividad = (trade − mid) / half_spread`. Fichero: `nivel2_trades_YYYYMMDD.csv`.
3. **Nivel 3 — operaciones.** El script `nivel3_agrupar.py` agrupa trades en operaciones (patas simultáneas con misma Trade Condition, y troceado del mismo contrato), infiere estructura y dirección, y descarta las que no superan el umbral. Fichero: `nivel3_operaciones_YYYYMMDD.csv`.

Umbral de premium por tramo de precio del subyacente, usado en todo el proyecto:

| Precio del subyacente | Umbral de premium |
| --- | --- |
| $1 – $50 | ≥ $500.000 |
| $50 – $200 | ≥ $1.000.000 |
| > $200 | ≥ $3.000.000 |

Todos los ficheros viven en una carpeta de datos configurable. El dashboard solo lee esa carpeta; nunca escribe en ella.

## Capa de datos

Las operaciones se reconstruyen desde el nivel 2, no se leen del CSV del nivel 3: así hay una sola lógica de agrupación, se obtiene el detalle por pata y todos los días quedan con el formato actual.

### Ficheros de entrada

| Fichero | Uso en el dashboard |
| --- | --- |
| `nivel1_candidatos_YYYYMMDD.csv` | Precio del subyacente (umbral por tramo, precio de referencia en gráficos) |
| `nivel2_trades_YYYYMMDD.csv` | Fuente de las operaciones: se agrupan con el código de `nivel3_agrupar.py` |
| `nivel3_operaciones_YYYYMMDD.csv` | No se usa como fuente; solo para validar que la reconstrucción coincide |
| `gex_spy_YYYYMMDD.csv` (nuevo) | GEX del SPY en el momento de la captura (ver *Cambios fuera del dashboard*) |

### Normalización de esquemas

Los CSV históricos no comparten esquema. La capa de datos traduce todas las variantes a un esquema canónico antes de cualquier otra cosa. Variantes conocidas:

- Nivel 1: contrato en `contract_symbol` u `option_symbol`, o ausente (se reconstruye como `SYMBOL|YYYYMMDD|STRIKE.00C/P`); `open_int` u `open_interest`; `last_trade`, `last_trade_ts` o ausente; `fecha_volumen` a veces como texto con varias fechas.
- Nivel 2: nombres de la API (`tradeTime`, `lastPrice`, `tradeSize`, `tradeConditionCode`, `premium`…) frente a los canónicos (`Time`, `Trade`, `Trade Size`, `Trade Condition`, `Premium`); `Trade Condition Full` y `es_metadata_footer` opcionales; filas de pie de página a descartar.

Un fichero que no encaje en ninguna variante conocida se reporta en pantalla con el nombre del fichero y las columnas que faltan; no se ignora en silencio.

### Días sin datos recuperables

- `nivel2_trades_20260922.csv` está vacío (0 filas): el 22/09 se descarta.
- El 25/08 y el 09/09 tienen un nivel 3 con formato antiguo, pero su nivel 2 está completo: se reconstruyen sin problema.

### Identificador de operación

Cada operación recibe un ID estable: `YYYYMMDD-SIMBOLO-HH:MM:SS.mmm` (fecha y hora del primer trade del grupo). Las ediciones manuales y los vínculos con posiciones apuntan a este ID.

### Ediciones manuales

Todo lo que introduce el usuario se guarda en ficheros propios del dashboard, separados de los del pipeline, y se aplica encima de los datos al cargar:

- Patas añadidas a mano (pestaña 2).
- Direcciones asignadas o corregidas a mano (pestaña 1).
- Posiciones reales y su vínculo con operaciones (pestaña 3).

Si una edición apunta a un ID que ya no existe (por ejemplo, porque cambió la lógica de agrupación), el dashboard la muestra como huérfana para revisarla; nunca la borra.

## Reglas de clasificación

Cada operación va a uno solo de cuatro destinos: gráfico de neto direccional, gráfico de paredes, total de indeterminadas o total de descartadas. Así ningún premium se cuenta dos veces.

Una pata es **comprada** si su agresividad es > +0,25 y **vendida** si es < −0,25. Entre esos valores su lado es indeterminado.

| Estructura | Condición | Destino | Strike | Expiración | Premium |
| --- | --- | --- | --- | --- | --- |
| Single-leg call o put | Comprada | Neto direccional (call = bull, put = bear) | El del contrato | La del contrato | Premium total |
| Single-leg call o put | Vendida | Paredes (put = soporte, call = resistencia) | El del contrato | La del contrato | Premium total |
| Single-leg | Lado indeterminado | Indeterminadas, en su strike y expiración | El del contrato | La del contrato | Premium total |
| Vertical de débito | Premium pata comprada > pata vendida | Neto direccional | Pata comprada | Común | Pata comprada − pata vendida |
| Vertical de crédito | Premium pata vendida > pata comprada | Paredes | Pata vendida | Común | Pata vendida − pata comprada |
| Diagonal | Ambas patas con lado claro | Neto direccional | Pata comprada | La más cercana | Pata comprada − pata vendida |
| Multi-leg con alguna pata de lado indeterminado | — | Indeterminadas, como total aparte | — | — | Premium bruto |
| Calendar puro, straddle, strangle, risk reversal, condor, 3+ patas | — | Descartadas | — | — | Premium bruto |
| Con acciones (`TLET`, `TLAT`, `TLCT`, `TLFT`, `TASL`, `TESL`, `TFSL`) | — | Descartadas | — | — | Premium bruto |
| Patas incompletas sin completar | — | Descartadas (pendientes), hasta completarse en la pestaña 2 | — | — | Premium bruto |

Ejemplo de vertical de débito: bear put con 10M en la put 100 comprada y 5M en la put 90 vendida. Se coloca en el strike 100 con −5M (bajista).

### Dirección asignada a mano

Asignar o corregir la dirección de una operación cambia su destino según estas mismas reglas. En una single-leg la dirección implica el lado: bull sobre una call implica comprada (va al neto), y bull sobre una put implica vendida (va a paredes).

### Dirección de las paredes

Una put vendida o un bull put spread forman una pared de soporte, por debajo del precio. Una call vendida o un bear call spread forman una pared de resistencia, por encima.

## Pestaña 1 — Operaciones

Tres paneles, según el sketch: el listado de operaciones a la izquierda, el gráfico del subyacente arriba a la derecha y el GEX del SPY abajo a la derecha.

### Panel 1 — Listado de operaciones

- Operaciones del nivel 3 reconstruidas, incluidas las completadas a mano en la pestaña 2. No incluye las que tienen patas incompletas pendientes.
- Selector de rango: hoy, última semana, último mes y rango personalizado.
- Columnas: las de `nivel3_operaciones` (símbolo, estructura, strike, expiración, fecha de operación, premium en millones, `precio_neto`, agresividad, dirección, trade conditions, hora de inicio y fin).
- Ordenable y filtrable por columna.
- Clic en la celda de dirección: abre un pop-up para asignar o corregir la dirección (bull, bear o indeterminado). Las indeterminadas se resaltan para revisarlas. Una dirección editada a mano se marca visualmente.
- Seleccionar una fila fija el subyacente del panel 2.

### Panel 2 — Gráficos del subyacente

Dos gráficos del subyacente seleccionado, alternables con pestañas internas. Cada uno tiene su propio selector de rango de fechas, independiente del listado.

**Neto direccional**

- Barras divergentes: premium bull hacia arriba, premium bear hacia abajo y una marca con el neto (bull − bear) en cada barra.
- Eje X seleccionable: por fecha de expiración o por strike (uno u otro, no ambos).
- Premium indeterminado acumulado, con su propia marca en cada barra (single-leg indeterminadas).
- Indicadores aparte, como totales: multi-leg indeterminadas y combinaciones descartadas (premium bruto acumulado).

**Paredes**

- Premium neto por strike vendido: soporte (puts vendidas, bull put spreads) por debajo del precio y resistencia (calls vendidas, bear call spreads) por encima.
- Precio actual del subyacente marcado como referencia.
- Filtro por fecha de expiración.

### Panel 3 — GEX del SPY

Contexto general de mercado, independiente de la operación seleccionada. Datos del último `gex_spy_YYYYMMDD.csv`, con su hora de captura visible.

- Régimen: gamma positiva o negativa.
- Nivel del gamma flip frente al precio actual del SPY.
- Strikes principales por GEX absoluto.

## Pestaña 2 — Patas incompletas

Aquí se completan a mano las operaciones multi-leg a las que les falta una pata; al guardar, la operación pasa a la pestaña 1.

### Panel 1 — Listado

- Operaciones con `patas_incompletas = True` que aún no se han completado.
- Mismo selector de rango que la pestaña 1.
- Columnas: símbolo, contrato de la pata conocida, Trade Condition, tamaño, premium, hora de inicio y fin, fecha de operación.

### Panel 2 — Formulario de pata faltante

Al seleccionar una operación, se abre un formulario con el subyacente ya rellenado. Campos mínimos:

- Tipo (call o put), strike y fecha de expiración.
- Precio de ejecución.
- Tamaño (contratos).
- Lado: comprada o vendida.

Al guardar:

1. La pata se añade a la operación (se guarda en el fichero de ediciones manuales).
2. La operación se recalcula con la misma lógica que las demás: estructura, `precio_neto`, dirección y premium.
3. Desaparece de esta pestaña y aparece en la pestaña 1, clasificada según las reglas de clasificación.

Una pata añadida a mano se puede editar o eliminar después; al eliminarla, la operación vuelve a esta pestaña.

## Pestaña 3 — Posiciones

Registro de las posiciones reales del usuario, vinculadas a la operación que imitan, para medir qué señales funcionan y no solo el P&L global.

### Panel 1 — Posiciones abiertas

- Alta, edición y cierre manual de posiciones.
- Una posición puede tener varias patas. Campos por pata: contrato (subyacente, tipo, strike, expiración), lado (compra o venta), cantidad y precio de entrada.
- Campos por posición: fecha de apertura, comisiones, notas y operación vinculada (ID de operación, opcional, elegible desde el listado de la pestaña 1).

### Panel 2 — Historial

- Posiciones cerradas: fecha y precio de cierre por pata, P&L en $ y en %, días en posición.
- Para las vinculadas, los datos de la operación de origen (estructura, dirección, premium, agresividad), para poder filtrar el historial por ellos.

### Panel 3 — Historial gráficamente

- P&L acumulado en el tiempo.
- Más vistas cuando haga falta; el usuario las añadirá más adelante.

### Importación desde tastytrade

Fase posterior. Primero, entrada manual; el modelo de datos de posiciones debe permitir sustituirla después por una importación automática desde la API de tastytrade sin rehacer la pestaña. La disponibilidad y las condiciones de la API se verificarán al llegar a esa fase.

## Cambios fuera del dashboard

Hacen falta dos cambios en el pipeline de captura; ninguno altera lo que entrega hoy.

### 1. `nivel3_agrupar.py`: exponer patas e ID sin cambiar su salida

El dashboard importa las funciones del script en vez de reimplementarlas. Para eso:

- Extraer el cálculo por pata (contrato, tipo, strike, expiración, tamaño, premium, agresividad, precio medio) a una función propia que `resumen()` siga usando.
- Añadir una función que devuelva el ID de operación (`YYYYMMDD-SIMBOLO-HH:MM:SS.mmm`).
- Separar la agrupación del filtro por umbral, para que el dashboard pueda agrupar y aplicar las ediciones manuales antes de filtrar.
- Prueba de no regresión: el `nivel3_operaciones_YYYYMMDD.csv` que genera el script refactorizado debe ser idéntico, byte a byte, al del script actual, para cada día con nivel 2 disponible.

### 2. Nuevo fichero con el GEX del SPY

El pipeline de captura tendrá que producir un fichero nuevo, independiente de los niveles 1-3:

- Una captura al día, en el mismo momento que el resto de los datos.
- Salida: `gex_spy_YYYYMMDD.csv` en la carpeta de datos, con hora de captura, precio del SPY y GEX por strike.
- Si la fuente no da el gamma flip ni el régimen directamente, se calculan a partir del GEX por strike.

## Documentación

El proyecto se documenta a la vez que se construye, no al final: cada fase entrega su código junto con la documentación que le corresponde.

- **README**: qué hace el proyecto, captura de cada pestaña, cómo instalarlo y ejecutarlo, y estructura del repositorio.
- **Contrato de datos**: esquema canónico de cada CSV de entrada (columnas, tipos, significado) y de los ficheros de ediciones manuales. Es la puerta de entrada del proyecto: "recibe CSV con este esquema".
- **Reglas de negocio**: umbrales, cálculo de agresividad, agrupación de trades y reglas de clasificación de esta especificación, con ejemplos.
- **Arquitectura**: capa de datos, reconstrucción de operaciones, ediciones manuales y vistas, con un diagrama.
- **Registro de decisiones**: una entrada breve por decisión relevante (qué se decidió, por qué, alternativas descartadas). Las decisiones de esta especificación son las primeras entradas.
- **Tests**: de la normalización de esquemas, de las reglas de clasificación y de no regresión del script del nivel 3.

Los aspectos de publicación en GitHub (datos de ejemplo, qué no se publica) se tratarán más adelante.

## Puntos abiertos y supuestos

Los supuestos se aplican tal como están salvo que se corrijan; los puntos abiertos se deciden antes de la fase que los necesita.

### Supuestos

- El gráfico de neto y el de paredes comparten el panel 2 mediante pestañas internas, porque el sketch tiene tres paneles.
- Las multi-leg con lado indeterminado van como total aparte, no repartidas por strike.
- Las diagonales van siempre al neto direccional, incluso si son de crédito.
- La fecha que usan los selectores de rango es la fecha de la operación (cuándo se negoció), no la fecha de captura del fichero.

### Puntos abiertos

- **Risk reversal.** El script lo agrupa con straddles y strangles, así que hoy se descarta, aunque sí tiene una dirección única (call comprada + put vendida = bull). ¿Separarlo y llevarlo al neto?
- **Stack.** No decidido. Restricción: el dashboard importa código Python (`nivel3_agrupar.py`), así que el backend debe ser Python. Las opciones se propondrán en el plan.
- **Uso solo local o accesible desde otros dispositivos.** No decidido; afecta al stack y a dónde se guardan las ediciones manuales.
