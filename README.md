# Dashboard Tape Reading

Dashboard local en Python para revisar el flujo diario de opciones. Lee los CSV que deja un pipeline de captura externo (con el esquema del [contrato de datos](docs/contrato-datos.md)), reconstruye las operaciones a partir de los trades y las muestra en tres pestañas:

1. **Operaciones**: listado de las operaciones detectadas, con gráficos de neto direccional y de paredes por subyacente, y el GEX del SPY como contexto de mercado.
2. **Patas incompletas**: operaciones multi-leg a las que les falta una pata, para completarlas a mano.
3. **Posiciones**: posiciones reales vinculadas a la operación que imitan, con su historial y P&L.

El dashboard **solo lee** la carpeta de datos, nunca la modifica, y no envía órdenes.

> **Estado:** fases 0 a 2 completadas: script de nivel 3 refactorizado con test de no regresión, capa de datos que lee, valida y reconstruye todas las capturas, y reglas de clasificación con ediciones manuales. La interfaz llega a partir de la Fase 3. El plan completo está en [docs/plan.md](docs/plan.md).

## Ficheros de entrada

```
carpeta de datos (solo lectura)
  nivel1_candidatos_YYYYMMDD.csv   candidatos por cambio de open interest
  nivel2_trades_YYYYMMDD.csv       Time & Sales de cada candidato
  nivel3_operaciones_YYYYMMDD.csv  operaciones agrupadas por pipeline/nivel3_agrupar.py
          │
          ▼
Dashboard: reconstruye las operaciones desde el nivel 2 con el mismo código del
nivel 3, aplica las ediciones manuales y clasifica.
```

Cómo se obtienen esos ficheros queda fuera de este repositorio. Las reglas de negocio (umbrales, agresividad, agrupación y clasificación) están en [docs/reglas-negocio.md](docs/reglas-negocio.md).

## Estructura del repositorio

```
pipeline/nivel3_agrupar.py   script de nivel 3: lo ejecuta el pipeline y lo importa el dashboard
src/tape_dashboard/          código del dashboard
  config.py                  rutas configurables
  data/                      capa de datos: esquemas, carga, reconstrucción, validación
  rules/                     lado de cada pata, tipos de operación y clasificación
  edits/                     ediciones manuales: almacén SQLite y aplicación sobre los datos
  report.py                  informe de los datos por consola
tests/                       tests (pytest)
tests/legacy/                copia congelada del script anterior, oráculo de no regresión
docs/                        reglas de negocio, decisiones y guías
specification.md             especificación funcional (en inglés)
```

## Instalación y tests

Requiere Python 3.11 o superior.

```bash
python -m venv .venv
.venv/Scripts/activate          # Windows; en Linux/macOS: source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

Los tests que necesitan datos reales los buscan en la carpeta de datos configurada. Si no la encuentran, se omiten. El resto (con datos sintéticos generados por los propios tests) se ejecuta siempre.

## Uso

```bash
python -m tape_dashboard.report     # inventario, validación, reparto por destino, ediciones huérfanas y avisos
```

La carpeta de datos y la de datos del usuario se configuran con las variables de entorno `TAPE_DATA_DIR` y `TAPE_USER_DATA_DIR`, o con un `config.toml` (plantilla en [`config.example.toml`](config.example.toml)).

## Datos

El repositorio no contiene datos: ningún CSV, ni ediciones manuales, ni posiciones, ni credenciales (ver `.gitignore`; un test lo comprueba). El formato de cada fichero de entrada está en el [contrato de datos](docs/contrato-datos.md).

## Documentación

- [Contrato de datos](docs/contrato-datos.md)
- [Calidad de los datos](docs/calidad-datos.md)
- [Arquitectura](docs/arquitectura.md)
- [Reglas de negocio](docs/reglas-negocio.md)
- [Script de nivel 3 y su despliegue](docs/level3-script.md)
- [Registro de decisiones](docs/decisiones/README.md)
- [Plan por fases](docs/plan.md)
