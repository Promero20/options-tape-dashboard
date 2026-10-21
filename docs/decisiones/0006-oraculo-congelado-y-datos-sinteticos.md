# 0006. No regresión con una copia congelada del script y datos sintéticos

- **Fecha:** 2026-10-16
- **Estado:** aceptada

## Contexto

El refactor del script no debe cambiar su salida (regla 3). Hace falta contra qué comparar:

- El original de la carpeta de datos se sustituirá en cuanto se despliegue la versión nueva.
- Los CSV de nivel 3 guardados no sirven para todos los días: varios los generaron versiones anteriores del script.
- No se pueden versionar datos reales (regla 2), y en GitHub no hay datos con los que probar.

## Decisión

- **Oráculo**: una copia congelada de la versión del 01/10/2026 en `tests/legacy/`, protegida por un test de SHA-256 y excluida de la conversión de finales de línea de git. No es una segunda lógica: solo la usan los tests. Al publicar el repositorio se generalizó un comentario de esa copia (sobre la procedencia de los nombres de columna); antes de fijar su nuevo hash se comprobó que su salida (CSV y consola) es idéntica a la del original en las 14 capturas reales y en las 5 variantes sintéticas.
- **Datos reales**: el test ejecuta el script legacy y el nuevo sobre cada día con nivel 2 y exige que el CSV y el mensaje de consola sean idénticos byte a byte. Si no encuentra la carpeta de datos, se omite.
- **Datos sintéticos**: un escenario generado por código (no se versiona ningún CSV) que cubre los casos del script y las variantes de esquema conocidas. Corre siempre, también en GitHub.

## Alternativas descartadas

- **Salidas "golden" guardadas**: derivadas de datos reales, así que no se pueden versionar, y si se pierden se pierde el oráculo.
- **Comparar solo con los nivel 3 guardados**: solo coinciden los generados por la versión vigente.

## Consecuencias

- El dashboard usa siempre los datos reales; los sintéticos solo existen dentro de los tests.
- Si se cambia la salida del script a propósito, el test debe demostrar que ese es el único cambio. Con las cancelaciones ([0015](0015-quitar-cancelaciones.md)) se hizo transformando la entrada del oráculo, sin congelar una versión nueva.
