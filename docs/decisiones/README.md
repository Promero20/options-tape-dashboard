# Registro de decisiones

Una entrada breve por cada decisión relevante: qué se decidió, por qué y qué alternativas se descartaron. Las cuatro primeras vienen de la [especificación](../../especificacion.md); el resto se tomaron al contrastarla con los datos reales.

| # | Decisión | Estado |
|---|---|---|
| [0001](0001-reconstruir-desde-nivel2.md) | Las operaciones se reconstruyen desde el nivel 2 | aceptada |
| [0002](0002-una-sola-logica-de-agrupacion.md) | Una sola lógica de agrupación: el dashboard importa el script | aceptada |
| [0003](0003-ediciones-en-ficheros-propios.md) | Ediciones manuales en ficheros propios; las huérfanas no se borran | aceptada |
| [0004](0004-un-destino-por-operacion.md) | Cada operación va a un único destino | aceptada |
| [0005](0005-copia-canonica-del-script.md) | La copia canónica del script vive en este repositorio | aceptada |
| [0006](0006-oraculo-congelado-y-datos-sinteticos.md) | No regresión con una copia congelada del script y datos sintéticos generados en los tests | aceptada |
| [0007](0007-formato-id-operacion.md) | El ID de operación incluye la Trade Condition | aceptada |
| [0008](0008-rangos-por-fecha-de-captura.md) | Los selectores de rango usan la fecha de captura | aceptada |
| [0009](0009-descartar-22-09.md) | El 22/09 se descarta | aceptada |
| [0010](0010-operacion-en-varias-capturas.md) | Una operación repetida en varias capturas cuenta una vez | aceptada |
| [0011](0011-pata-manual-tipo-de-operacion.md) | Al completar una pata, el usuario elige el tipo de operación | aceptada |
| [0012](0012-marcar-ratios-anomalos.md) | Se marcan las multi-leg con ratio de tamaños anómalo | aceptada |
| [0013](0013-universo-pestana-2.md) | Pestaña 2: selector de día y solo operaciones por encima del umbral | aceptada |
| [0014](0014-columnas-obligatorias-y-variantes.md) | Columnas obligatorias mínimas y variantes nuevas con aviso | aceptada |
| [0015](0015-quitar-cancelaciones.md) | Las cancelaciones se quitan en el script, junto con el trade que anulan | aceptada |
| [0016](0016-acciones-e-incompletas.md) | Una operación con acciones se descarta aunque tenga patas incompletas | aceptada |
| [0017](0017-frontera-de-la-agresividad.md) | Una agresividad de exactamente ±0,25 es lado indeterminado | aceptada |
| [0018](0018-diagonales-de-credito.md) | Diagonales de crédito: la dirección es la de la pata de más premium | aceptada |
| [0019](0019-almacen-de-ediciones.md) | Las ediciones manuales se guardan en un SQLite local | aceptada |
| [0020](0020-correccion-de-multi-legs.md) | Las multi-legs se corrigen eligiendo el tipo de operación | aceptada |
| [0021](0021-direccion-del-listado.md) | El listado muestra la dirección de la clasificación | aceptada |
| [0022](0022-call-put-y-sinteticos.md) | Call + put con distinta expiración y sintéticos se descartan, como los risk reversals | aceptada |

## Decisiones pendientes

- **Risk reversal**: ¿se separa de straddles y strangles y va al neto direccional? Hoy se descarta, y con él los sintéticos y las call + put con distinta expiración ([0022](0022-call-put-y-sinteticos.md)).
- **Umbral para precios por debajo de $1**: el script les aplica el tramo de 3 M; se mantiene mientras no aparezcan (ver [reglas de negocio](../reglas-negocio.md#1-umbral-de-premium-por-precio-del-subyacente)).
- **Frontera de la agresividad en el script**: alinear su columna `direccion` con la especificación cambiaría su salida ([0017](0017-frontera-de-la-agresividad.md)).
- **Stack de interfaz** y **uso solo local o desde otros dispositivos** (antes de la Fase 3).
- **Idioma de la documentación** al publicar.

## Plantilla

```markdown
# NNNN. Título

- **Fecha:** AAAA-MM-DD
- **Estado:** propuesta | aceptada | sustituida por NNNN

## Contexto
## Decisión
## Alternativas descartadas
## Consecuencias
```
