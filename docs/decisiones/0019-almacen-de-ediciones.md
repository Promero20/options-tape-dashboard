# 0019. Las ediciones manuales se guardan en un SQLite local

- **Fecha:** 2026-10-19
- **Estado:** aceptada

## Contexto

Las ediciones manuales (correcciones de dirección o de tipo de operación, y patas añadidas) van en ficheros propios del dashboard ([0003](0003-ediciones-en-ficheros-propios.md)). Más adelante se añadirán las posiciones, con varias patas y vínculos a operaciones, y su importación desde tastytrade.

## Decisión

Un único fichero SQLite, `ediciones.sqlite`, en la carpeta de datos del usuario (configurable y fuera de git). Se usa `sqlite3` de la biblioteca estándar. El esquema está en el [contrato de datos](../data-contract.md#manual-edits).

La lectura para el informe abre el fichero en modo solo lectura y no lo crea si no existe. La aplicación de las ediciones trabaja sobre una instantánea en memoria, con funciones puras que se prueban sin base de datos.

## Alternativas descartadas

- **JSON**: más fácil de leer a mano, pero sin restricciones de integridad ni escrituras atómicas, y peor para las posiciones relacionales de la Fase 6.

## Consecuencias

- Para inspeccionar o hacer copia de seguridad de las ediciones basta con copiar un fichero.
- Si en el futuro el dashboard se usa desde varios dispositivos, habrá que revisar dónde vive ese fichero.
