# 0005. La copia canónica del script vive en este repositorio

- **Fecha:** 2026-10-16
- **Estado:** aceptada

## Contexto

El pipeline de captura ejecuta `nivel3_agrupar.py` desde la carpeta de datos, y el dashboard necesita importarlo (ver [0002](0002-una-sola-logica-de-agrupacion.md)). Dos copias que evolucionan por separado acabarían divergiendo. A la vez, el dashboard nunca escribe en la carpeta de datos.

## Decisión

La versión canónica está en `pipeline/nivel3_agrupar.py`, con su historial y sus tests. Cuando cambia, el usuario la copia a la carpeta de datos (procedimiento en [level3-script.md](../level3-script.md)). A partir de la Fase 3, el dashboard compara los hashes de las dos copias y avisa si difieren.

## Alternativas descartadas

- **Mantener el original en la carpeta de datos y que el dashboard lo importe desde ahí**: sin historial ni tests, y el dashboard dependería de código que no controla.
- **Enlace simbólico desde la carpeta de datos al repositorio**: hay que crearlo dentro de esa carpeta, y no está claro que el entorno del pipeline lo resuelva.

## Consecuencias

- El despliegue en el pipeline es un paso manual, pero es raro y verificable.
- El script tiene que seguir siendo un fichero autónomo, solo con la biblioteca estándar.
- Es la única excepción a la convención de identificadores en inglés: el script ya tenía su API en español (`cargar`, `agrupar`, `resumen`…), y las funciones nuevas (`patas_de`, `id_operacion`, `filtrar_por_umbral`…) siguen esa nomenclatura para que el módulo sea coherente. El código del dashboard y los tests usan identificadores en inglés.
