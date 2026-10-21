# 0001. Las operaciones se reconstruyen desde el nivel 2

- **Fecha:** 2026-10-15 (especificación)
- **Estado:** aceptada

## Contexto

El pipeline de captura deja cada día un `nivel3_operaciones_YYYYMMDD.csv` con las operaciones ya agrupadas, pero ese fichero ha cambiado de formato con las versiones del script: los más antiguos no tienen strike, expiración ni filtro por umbral. Además, no trae el detalle por pata, que el dashboard necesita para clasificar.

## Decisión

El dashboard reconstruye las operaciones desde `nivel2_trades_*.csv` (más el precio del nivel 1), con el mismo código que genera el nivel 3. El CSV de nivel 3 solo se usa para validar que la reconstrucción coincide.

## Alternativas descartadas

- **Leer el nivel 3 tal cual**: obliga a soportar cada formato histórico y no da detalle por pata.

## Consecuencias

- Todos los días quedan con el formato actual y con detalle por pata.
- Un día sin nivel 2 no se puede reconstruir (ver [0009](0009-descartar-22-09.md)).
