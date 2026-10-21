# The level-3 script and its deployment

`pipeline/nivel3_agrupar.py` is the **canonical copy** of the script that groups level-2 trades into operations:

- **The capture pipeline** runs it every day from the data folder to produce `nivel3_operaciones_YYYYMMDD.csv`.
- **The dashboard** imports its functions to rebuild the operations, so there is only one grouping logic.

The script uses only the standard library and runs as it always has. Its identifiers and console messages are in Spanish:

```bash
python3 nivel3_agrupar.py nivel2_trades_YYYYMMDD.csv nivel1_candidatos_YYYYMMDD.csv nivel3_operaciones_YYYYMMDD.csv
```

## What changed in the phase 0 refactor

The output is **byte-for-byte identical**, and so is the console message. The changes are internal:

| Change | Why |
|---|---|
| `preparar_filas()`, split from `cargar()` | The dashboard passes it rows that are already read and normalised |
| `resumen_pata()` and `patas_de()`, extracted from `resumen()` | Per-leg detail for the dashboard; `resumen()` still uses them |
| `id_operacion()` | Stable ID `YYYYMMDD-SYMBOL-HH:MM:SS.mmm-TC` |
| `resumir_todas()`, `pasa_umbral()` and `filtrar_por_umbral()`, split from `main()` | Group and apply manual edits before filtering by threshold |
| `escribir_operaciones()`, split from `main()` | Clarity; `main()` only chains the pieces |
| Explicit `encoding='utf-8'` for reading and writing | On Windows the previous script failed when writing `→` (calendars and diagonals). Nothing changes on Linux |
| Clear error if level 2 has no trades | It used to fail with an unhelpful `IndexError` |

The guarantee comes from the tests in [`tests/test_no_regression.py`](../tests/test_no_regression.py):

- With the real data of every day with level 2, the new script produces exactly the same CSV and console message as the frozen 01/10/2026 version (`tests/legacy/`). If the day has cancellations, it is compared with the frozen version run on the same level 2 without them (see below).
- The same with a synthetic scenario written in every known schema variant.
- For days without cancellations whose level 3 was produced by that version, it also matches the stored CSV.

## Output change of 19/10/2026: cancellations

Before grouping, the script drops cancellation rows (`CANC`, `CNCL`, `CNCO`, `CNOL`) and the trade each one cancels ([decision 0015](decisions/0015-drop-cancellations.md)). With a level 2 without cancellations, the output does not change. If there are any:

- the CSV is the one the previous version would have produced from that level 2 without those rows;
- the console adds a second line, for example `1 cancelaciones quitadas junto con el trade que anulan`.

In the captures analysed it affects 02/10 and 07/10: each loses two operations that never went through.

## How to deploy a new version

The dashboard never writes to the data folder, so deployment is manual:

1. Check that the tests pass: `pytest`.
2. Copy `pipeline/nivel3_agrupar.py` to the data folder (only that file, replacing the previous one).
3. Check the copy by comparing hashes; they must match:

   ```bash
   sha256sum pipeline/nivel3_agrupar.py <data folder>/nivel3_agrupar.py
   ```

   On Windows, from cmd: `certutil -hashfile <file> SHA256` (one file at a time); from PowerShell: `Get-FileHash <file1>, <file2>`.

4. Update the expected hash in the capture pipeline's instructions: the pipeline computes the script's SHA-256 before running it and stops if it does not match, so if you skip this step the next day's level 3 will not be produced.
5. Add the version to the history below and commit.

`python -m tape_dashboard.report` warns if the copy in the data folder does not match the repository's; from phase 3, the interface will too.

## Version history

| Version | SHA-256 | Deployed | Notes |
|---|---|---|---|
| 01/10/2026 | `6420fc62206f331be4501939e1b5dfaa4c7f7a5bf02ccda83e881e744c4f662c` | 01/10/2026 | Reference version. Its frozen copy in `tests/legacy/` has one generalised comment (see [decision 0006](decisions/0006-frozen-oracle-and-synthetic-data.md)), so its hash differs; the behaviour is identical |
| Phase 0 | — | no | Refactor without output changes; no need to deploy it |
| 19/10/2026 | `59962f5b960389732e1a0b2425b04e74a94f5b0ae3adafc0fbacbedadff247a2` | 19/10/2026 | Drops cancellations and the trades they cancel |
| 21/10/2026 | `aea159f50faf93ed6b7fef345d884e6ac8e38247275287c3ebc542b64d8c571a` | pending | Generalises a comment about where the column names come from; same output |
