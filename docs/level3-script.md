# Script de nivel 3 y su despliegue

`pipeline/nivel3_agrupar.py` es la **copia canónica** del script que agrupa los trades del nivel 2 en operaciones:

- **El pipeline de captura** lo ejecuta cada día desde la carpeta de datos para generar `nivel3_operaciones_YYYYMMDD.csv`.
- **El dashboard** importa sus funciones para reconstruir las operaciones, de modo que solo existe una lógica de agrupación.

El script solo usa la biblioteca estándar y se ejecuta igual que siempre:

```bash
python3 nivel3_agrupar.py nivel2_trades_YYYYMMDD.csv nivel1_candidatos_YYYYMMDD.csv nivel3_operaciones_YYYYMMDD.csv
```

## Qué cambió en el refactor de la Fase 0

La salida es **idéntica byte a byte**, igual que el mensaje de consola. Los cambios son internos:

| Cambio | Para qué |
|---|---|
| `preparar_filas()`, separada de `cargar()` | El dashboard le pasa filas ya leídas y normalizadas |
| `resumen_pata()` y `patas_de()`, extraídas de `resumen()` | Detalle por pata para el dashboard; `resumen()` las sigue usando |
| `id_operacion()` | ID estable `YYYYMMDD-SIMBOLO-HH:MM:SS.mmm-TC` |
| `resumir_todas()`, `pasa_umbral()` y `filtrar_por_umbral()`, separadas de `main()` | Agrupar y aplicar ediciones manuales antes de filtrar por umbral |
| `escribir_operaciones()`, separada de `main()` | Claridad; `main()` solo encadena las piezas |
| Lectura y escritura con `encoding='utf-8'` explícito | En Windows el script anterior fallaba al escribir `→` (calendars y diagonales). En Linux no cambia nada |
| Error claro si el nivel 2 no tiene trades | Antes fallaba con un `IndexError` poco explicativo |

La garantía la dan los tests de [`tests/test_no_regression.py`](../tests/test_no_regression.py):

- Con los datos reales de cada día con nivel 2, el script nuevo produce exactamente el mismo CSV y el mismo mensaje que la versión congelada del 01/10/2026 (`tests/legacy/`). Si el día tiene cancelaciones, se compara con la versión congelada sobre el mismo nivel 2 sin ellas (ver más abajo).
- Lo mismo con un escenario sintético escrito en las variantes de esquema conocidas.
- Para los días sin cancelaciones cuyo nivel 3 lo generó esa versión, también coincide con el CSV guardado.

## Cambio de salida del 19/10/2026: cancelaciones

Antes de agrupar, el script quita las filas de cancelación (`CANC`, `CNCL`, `CNCO`, `CNOL`) y el trade que anula cada una ([decisión 0015](decisiones/0015-quitar-cancelaciones.md)). Con un nivel 2 sin cancelaciones, la salida no cambia. Si las hay:

- el CSV es el que habría generado la versión anterior con ese nivel 2 sin esas filas;
- la consola añade una segunda línea, por ejemplo `1 cancelaciones quitadas junto con el trade que anulan`.

En las capturas analizadas afecta al 02/10 y al 07/10: cada uno pierde dos operaciones que no llegaron a ejecutarse.

## Cómo desplegar una nueva versión

El dashboard nunca escribe en la carpeta de datos, así que el despliegue es manual:

1. Comprueba que los tests pasan: `pytest`.
2. Copia `pipeline/nivel3_agrupar.py` a la carpeta de datos (solo ese fichero, sustituyendo el anterior).
3. Verifica la copia comparando hashes; deben coincidir:

   ```bash
   sha256sum pipeline/nivel3_agrupar.py <carpeta de datos>/nivel3_agrupar.py
   ```

   En Windows, desde cmd: `certutil -hashfile <fichero> SHA256` (un fichero cada vez); desde PowerShell: `Get-FileHash <fichero1>, <fichero2>`.

4. Actualiza el hash esperado en las instrucciones del pipeline de captura: el pipeline calcula el SHA-256 del script antes de ejecutarlo y para si no coincide, así que si te saltas este paso el nivel 3 del día siguiente no se generará.
5. Añade la versión al historial de abajo y haz commit.

`python -m tape_dashboard.report` avisa si la copia de la carpeta de datos no coincide con la del repositorio; a partir de la Fase 3, la interfaz también.

## Historial de versiones

| Versión | SHA-256 | Desplegada | Notas |
|---|---|---|---|
| 01/10/2026 | `6420fc62206f331be4501939e1b5dfaa4c7f7a5bf02ccda83e881e744c4f662c` | 01/10/2026 | Versión de referencia. Su copia congelada en `tests/legacy/` tiene un comentario generalizado (ver [decisión 0006](decisiones/0006-oraculo-congelado-y-datos-sinteticos.md)), así que su hash es otro; el comportamiento es idéntico |
| Fase 0 | — | no | Refactor sin cambios de salida; no hacía falta desplegarlo |
| 19/10/2026 | `59962f5b960389732e1a0b2425b04e74a94f5b0ae3adafc0fbacbedadff247a2` | 19/10/2026 | Quita las cancelaciones y el trade que anulan |
| 21/10/2026 | `aea159f50faf93ed6b7fef345d884e6ac8e38247275287c3ebc542b64d8c571a` | pendiente | Generaliza un comentario sobre la procedencia de los nombres de columna; misma salida |
