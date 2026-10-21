# Plan por fases

Cada fase termina con los tests pasando, la documentación al día y un commit. Las decisiones que se toman por el camino van al [registro de decisiones](decisiones/README.md).

| Fase | Contenido | Estado |
|---|---|---|
| 0 | Andamiaje y refactor de `nivel3_agrupar.py` con test de no regresión | **hecha** |
| 1 | Capa de datos: esquemas, normalización y reconstrucción de operaciones | **hecha** |
| 2 | Clasificación, catálogo de tipos de operación y ediciones manuales (lógica pura) | **hecha** |
| 3 | Aplicación y pestaña 1: listado | pendiente |
| 4 | Pestaña 1: gráficos de neto direccional y paredes | pendiente |
| 5 | Pestaña 2: patas incompletas | pendiente |
| 6 | Pestaña 3: posiciones | pendiente |
| 7 | GEX del SPY (nuevo fichero de entrada y panel) | pendiente |

La Fase 2 va antes de la interfaz porque la necesitan el popup de dirección, los gráficos y la pestaña 2. Es además la lógica de negocio con más riesgo, y se prueba mejor sin interfaz.

## Fase 0: andamiaje y refactor con no regresión

- Repositorio: `.gitignore` (ningún dato versionado), `.gitattributes`, `pyproject.toml`, README y registro de decisiones.
- `pipeline/nivel3_agrupar.py` refactorizado: cálculo por pata, ID de operación y umbral separado de la agrupación, con la salida intacta ([detalle](level3-script.md)).
- Copia congelada de la versión anterior en `tests/legacy/` como oráculo.

**Terminada cuando:** la salida del script nuevo es idéntica byte a byte a la del congelado para cada día real con nivel 2 y para el escenario sintético en cada variante de esquema; coincide con los nivel 3 guardados que generó esa versión; y la carpeta de datos queda intacta. ✔

## Fase 1: capa de datos y reconstrucción

- Ruta de datos configurable (variable de entorno, fichero de configuración o `../tape_data` por defecto).
- Esquema canónico de cada CSV, con alias y registro de las variantes conocidas. Un fichero al que le falten columnas obligatorias se reporta con su nombre y las columnas que faltan; un encabezado nuevo pero resoluble se carga con aviso.
- Normalización de valores: tipos, fechas, booleanos y contrato reconstruido.
- Reconstrucción por captura con las funciones del script, deduplicando por ID entre capturas.
- Validación contra el nivel 3 guardado.
- Informe por consola (`python -m tape_dashboard.report`).
- Documentación: `contrato-datos.md`, `calidad-datos.md` y `arquitectura.md`.

**Terminada cuando:** el informe sobre los datos reales es correcto y pasan los tests de normalización por variante, encabezado inválido, deduplicación y unicidad de IDs. ✔

## Fase 2: clasificación, catálogo y ediciones

- Destino único de cada operación según las reglas de la especificación, usando el detalle por pata.
- Catálogo de tipos de operación (bull call, bear put, straddle…) que fija el lado de cada pata ([0011](decisiones/0011-pata-manual-tipo-de-operacion.md)).
- Almacén local de ediciones (direcciones, patas manuales, tipos elegidos), con detección de huérfanas.
- Marca de ratio de tamaños anómalo ([0012](decisiones/0012-marcar-ratios-anomalos.md)).

**Terminada cuando:** hay tests de cada regla de la especificación, de cada tipo del catálogo, de los casos reales sin regla y de conservación del premium. ✔

Incluye además el cambio del script para quitar las cancelaciones ([0015](decisiones/0015-quitar-cancelaciones.md)).

## Fases 3 a 7

- **3**: aplicación con las tres pestañas; listado con orden y filtros, selector de rango por fecha de captura, popup de dirección, avisos (esquemas, huérfanas, script del pipeline desactualizado).
- **4**: gráficos de neto direccional y de paredes.
- **5**: pestaña 2, con selector de día, listado de incompletas por encima del umbral y formulario con tipo de operación.
- **6**: posiciones, historial y P&L, con un modelo preparado para una futura importación de solo lectura desde tastytrade.
- **7**: fichero del GEX del SPY y su panel.
