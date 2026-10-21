# 0014. Columnas obligatorias mínimas y variantes nuevas con aviso

- **Fecha:** 2026-10-19
- **Estado:** aceptada

## Contexto

La especificación pide reportar un CSV que no encaje en ninguna variante de esquema conocida, con su nombre y las columnas que faltan, sin ignorarlo ni parchearlo en silencio. Pero «no encajar» puede significar dos cosas: que falte algo imprescindible, o que el encabezado sea distinto (otro orden, una columna informativa de más o de menos) y los datos sigan sirviendo. El pipeline cambia de esquema a menudo: ya hay cinco variantes del nivel 1 y cinco del nivel 2.

## Decisión

- **Obligatorias** son solo las columnas que necesitan el script de nivel 3 o el dashboard. Nivel 1: símbolo, precio, expiración, tipo y strike. Nivel 2: identificación del contrato, hora, precio, tamaño, bid, ask, condición, premium y agresividad. Si falta alguna, el fichero no se usa y se reporta con su nombre y las columnas que faltan.
- Un encabezado que no coincide exactamente con ninguna **variante conocida** pero tiene las obligatorias se carga, con un aviso de «variante nueva» que detalla las columnas opcionales que faltan y las desconocidas.
- Las variantes conocidas se registran en `schemas.py` y en el [contrato de datos](../data-contract.md). Un test comprueba que todos los ficheros reales encajan en una de ellas.

## Alternativas descartadas

- **Rechazar todo encabezado desconocido**: un cambio de orden o una columna informativa nueva dejaría el día sin datos.
- **Aceptar en silencio cualquier encabezado resoluble**: contradice la especificación.

## Consecuencias

Cuando el pipeline cambie de esquema, el dashboard seguirá funcionando y lo avisará. La variante se añadirá entonces al registro.
