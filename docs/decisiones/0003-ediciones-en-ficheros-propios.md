# 0003. Ediciones manuales en ficheros propios

- **Fecha:** 2026-10-15 (especificación)
- **Estado:** aceptada

## Contexto

El usuario corrige direcciones, añade patas que faltan y registra posiciones. Los CSV del pipeline son la fuente original y no deben modificarse.

## Decisión

Toda edición manual se guarda en ficheros del dashboard, fuera de la carpeta de datos del pipeline y fuera de git, y se aplica sobre los datos al cargar. Cada edición apunta a un ID de operación. Si ese ID deja de existir (por ejemplo, porque cambió la lógica de agrupación), la edición se muestra como **huérfana** para revisarla; nunca se borra en silencio.

## Alternativas descartadas

- **Escribir las ediciones en los CSV del pipeline**: mezcla datos capturados con decisiones del usuario y viola la regla de solo lectura.

## Consecuencias

- El ID de operación tiene que ser estable y único (ver [0007](0007-formato-id-operacion.md)).
- El formato del almacén de ediciones se define en la Fase 2.
