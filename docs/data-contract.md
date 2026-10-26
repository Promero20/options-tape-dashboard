# Data contract

What the dashboard takes as input: the canonical schema of each input CSV, the alternative column names it accepts and how it normalises the values. The implementation is in [`src/tape_dashboard/data/schemas.py`](../src/tape_dashboard/data/schemas.py) and [`loading.py`](../src/tape_dashboard/data/loading.py).

## Input files

The capture pipeline, which is outside this repository, leaves its files in a data folder (see [configuration](#configuration)). The dashboard **only reads** it. Each file name carries its **capture date**, the day the pipeline took the data:

| File | Content | Use in the dashboard |
|---|---|---|
| `nivel1_candidatos_YYYYMMDD.csv` | The day's contracts with an increase in open interest, with derived fields | Underlying price: threshold and chart reference |
| `nivel2_trades_YYYYMMDD.csv` | Time & Sales of the selected candidates | Source of the operations |
| `nivel3_operaciones_YYYYMMDD.csv` | Operations grouped by `nivel3_agrupar.py` | Only to validate the reconstruction |

A CSV whose name matches none of these patterns is reported as "not recognised".

## General rules

- **Encoding** UTF-8; separator `,`; the first row is the header.
- **Columns**: each canonical column accepts one or more alternative names. Column order does not matter.
- **Required columns** are the ones the level-3 script or the dashboard need. If any is missing, the file is not used and is reported **with its name and the missing columns**.
- **Variants**: each header is compared with the known variants (tables below). A new one that has the required columns is loaded, with a warning saying it is a new variant and which columns are missing or extra ([decision 0014](decisions/0014-required-columns-and-variants.md)).
- **Values** that cannot be parsed are left empty and counted in one warning per column. They are never dropped silently.

## Level 1: candidates

One row per contract. Only the contracts selected by the pipeline (top 25 by `premium_estimado` and above the threshold) carry the reconciliation fields.

| Canonical column | Accepted names | Req. | Normalised type | Meaning |
|---|---|---|---|---|
| `symbol` | | yes | text | Underlying |
| `contract_symbol` | `option_symbol` | no | text | Contract, `SYMBOL\|YYYYMMDD\|STRIKE.00C` or `…P`. If the column is missing, it is rebuilt from symbol, expiration, strike and type |
| `price` | | yes | number | Underlying price at capture time |
| `exp_date` | | yes | ISO date | Expiration |
| `type` | | yes | `call` / `put` | Option type (arrives as `Call`/`Put`) |
| `strike` | | yes | number | Strike |
| `moneyness` | | no | number | Distance from strike to price, as given by the source |
| `bid`, `ask`, `mid` | | no | number | Contract quote and its midpoint |
| `volume` | | no | integer | Day volume |
| `open_interest` | `open_int` | no | integer | Open interest |
| `oi_chg` | | no | integer | Published change in open interest |
| `vol_oi`, `iv`, `delta` | | no | number | As given by the source |
| `last_trade` | `last_trade_ts` | no | ISO date | Date of the last trade. It arrives as epoch seconds, `YYYY-MM-DD HH:MM:SS`, `YYYY-MM-DD` or `MM/DD/YY`; only the date is kept (epoch values are read as UTC) |
| `premium_estimado` | | no | number | `mid × oi_chg × 100` |
| `dte` | | no | integer | Days to expiration |
| `fecha_volumen` | | no | list of ISO dates | Actual date or dates of the volume (separated by `;`, in any order). Empty if the contract was not selected |
| `volumen_en_fecha` | | no | integer | Volume on those dates |
| `ratio_reconciliacion` | | no | number | `volumen_en_fecha / oi_chg` |
| `reconciliacion_fallida`, `reconciliacion_ambigua` | | no | boolean or empty | Empty if the contract was not selected |

The **price of an underlying** is the one in the first row of its symbol, as the level-3 script does. In every capture analysed, all rows of a symbol have the same price.

### Known level-1 variants

| Variant | Captures | Differences |
|---|---|---|
| N1-A | 12/08, 17/08 | `contract_symbol` second, `open_int`, `last_trade_ts` (epoch) |
| N1-B | 25/08, 09/09, 11/09, 15/09 | **No contract column** (rebuilt), `last_trade` |
| N1-C | 16/09, 22/09 | `option_symbol`, `open_interest`, `last_trade` as `MM/DD/YY` |
| N1-D | 24/09, 01/10, 02/10, 06/10 | `contract_symbol` after `delta`, no `last_trade` |
| N1-E | 07/10, 13/10, 15/10 | Like N1-D, plus `last_trade` at the end |

## Level 2: Time & Sales

One row per trade. The columns the level-3 script uses **are passed to it with their original value**, so that the reconstruction is identical to the pipeline's. Only the columns the script does not use are normalised: `fecha_consultada` and the exchange codes.

| Canonical column | Accepted names | Req. | Value | Meaning |
|---|---|---|---|---|
| `symbol` | | yes | text | Underlying |
| `contract_symbol` | | yes | text | Contract, same format as in level 1 |
| `exp_date` | | yes | `YYYY-MM-DD` | Expiration |
| `strike` | | yes | numeric text | Strike (`275.0`, `900` or `612.50` depending on the capture) |
| `type` | | yes | text | `Call`/`Put` up to 22/09; `call`/`put` from 24/09 |
| `fecha_consultada` | | no | ISO date | Trading day queried. From 09/09 to 15/09 it arrived as `MM/DD/YYYY` |
| `Time` | `tradeTime` | yes | `YYYY-MM-DD HH:MM:SS.mmm` | Trade time, with milliseconds |
| `Trade` | `lastPrice` | yes | number | Execution price |
| `Trade Size` | `tradeSize` | yes | integer | Contracts. Only trades of **size ≥ 10** arrive (see [data quality](data-quality.md)) |
| `Exchange` | `lastExchange` | no | text | Execution venue; spaces and line breaks are trimmed |
| `Bid`, `Ask` | `bidPrice`, `askPrice` | yes | number | Best bid and ask at the time of the trade |
| `Bid Size`, `Ask Size` | `bidSize`, `askSize` | no | integer | |
| `Bid Exchange`, `Ask Exchange` | `bidExchange`, `askExchange` | no | text | Trimmed like `Exchange` |
| `Trade Condition` | `tradeConditionCode` | yes | code | Trade condition (`AUTO`, `MLET`, `ISOI`…) |
| `Trade Condition Full` | `tradeCondition` | no | text | Long description. In variant N2-B, `tradeCondition` is **the long text**, not the code |
| `Premium` | `premium` | yes | number | `Trade × Trade Size × 100` |
| `mid`, `half_spread` | | no | number | `(Bid + Ask) / 2` and `(Ask − Bid) / 2` |
| `agresividad` | | yes | number or empty | `(Trade − mid) / half_spread`; empty if `Bid = Ask` |
| `spread_cero` | | no | `True`/`False` | `Bid = Ask` |
| `es_cancelacion` | | no | `True`/`False` | Cancellation condition (`CANC`, `CNCL`, `CNCO`, `CNOL`) |
| `es_metadata_footer` | | no | `True`/`False` | Footer row of a download: dropped |

The aliases of the columns the script uses are exactly those in `ALIASES_COLUMNA` in `pipeline/nivel3_agrupar.py` (a test checks it).

### Known level-2 variants

| Variant | Captures | Differences |
|---|---|---|
| N2-A | 12/08 | Canonical names, with `es_metadata_footer` and without `Trade Condition Full` |
| N2-B | 17/08 | Alternative names (`tradeTime`, `lastPrice`…) and both condition columns |
| N2-C | 25/08 | Canonical, with `Trade Condition Full` and `es_metadata_footer` |
| N2-D | 09/09, 11/09, 15/09 | Canonical, no optional columns; `fecha_consultada` as `MM/DD/YYYY` |
| N2-E | 16/09, 22/09, 24/09 onwards | Canonical, with `Trade Condition Full` |

## Level 3: operations

Output of `pipeline/nivel3_agrupar.py`: one row per operation above the threshold. The dashboard does not use it as a source; it compares it with its own reconstruction. The meaning of each field is in the [business rules](business-rules.md#3-grouping-trades-into-operations).

| Variant | Captures | Columns |
|---|---|---|
| N3-C (current) | 11/09 onwards | `symbol, estructura, n_patas, n_trades, size_total, premium_total_M, precio_neto, precio_neto_metodo, agresividad_pond, direccion, trade_conditions, multi_leg_declarado, patas_incompletas, stock_option, hora_inicio, hora_fin, duracion_s, strike, fecha_expiracion, fecha_operacion` |
| N3-B | 09/09 | No `strike`, `fecha_expiracion` or `fecha_operacion`; has `patas` |
| N3-A | 25/08 | No threshold filter, `premium_total` in dollars, no net price; has `patas` |

## Rebuilt operations

For every capture with level 2, the dashboard groups **all** trades with the script's functions, including those of operations below the threshold (manual edits are applied before filtering). Each operation has:

| Field | Content |
|---|---|
| `id` | `YYYYMMDD-SYMBOL-HH:MM:SS.mmm-TC` ([business rules](business-rules.md#4-operation-id)) |
| `capture_date` | Capture date (the one the range selectors use) |
| `summary` | The script's `resumen()` row, with `premium_total` in dollars |
| `legs` | Per-leg detail from `patas_de()`: `contract_symbol, type, strike, exp_date, n_trades, size, premium, agr, precio_medio` |
| `trades` | The group's trade rows |
| `price` | Underlying price in the capture's level 1 |
| `passes_threshold` | Whether it reaches its bracket's threshold |

## Manual edits

SQLite file `edits.sqlite` in the user-data folder, outside git and outside the pipeline's data folder ([decision 0019](decisions/0019-edits-store.md)). Each edit points to an operation ID. If the ID no longer exists, the edit is listed as an orphan (in the report and in the interface's warnings banner) and is never deleted.

**`overrides`**: a correction of an operation; at most one per operation.

| Column | Type | Content |
|---|---|---|
| `operation_id` | text, key | Operation ID |
| `direction` | `bull` / `bear` / `undetermined` or null | Direction set by hand (single-leg) |
| `strategy` | text or null | Operation type from the catalogue (multi-leg), e.g. `bull_call` |
| `updated_at` | ISO date and time | Last change |

Exactly one of `direction` or `strategy` is always set.

**`manual_legs`**: legs added by hand.

| Column | Type | Content |
|---|---|---|
| `id` | integer, key | Leg identifier |
| `operation_id` | text | ID of the operation it completes |
| `option_type` | `call` / `put` | Type |
| `strike` | number > 0 | Strike |
| `exp_date` | ISO date | Expiration |
| `price` | number ≥ 0 | Execution price |
| `size` | integer > 0 | Contracts |
| `created_at`, `updated_at` | ISO date and time | |

## Positions

To be defined in phase 6, in the same user-data folder.

## Configuration

| Path | Environment variable | Key in `config.toml` | Default |
|---|---|---|---|
| Pipeline data | `TAPE_DATA_DIR` | `[paths] data_dir` | `../tape_data` |
| User data | `TAPE_USER_DATA_DIR` | `[paths] user_data_dir` | `./user_data` |
| File where the pipeline declares the script hash (optional) | `TAPE_EXPECTED_HASH_FILE` | `[pipeline] expected_hash_file` | not set: no check |

The environment variable takes precedence. Relative paths in `config.toml` are resolved from the repository root. The declared-hash check is described in [decision 0026](decisions/0026-declared-script-hash-check.md). The template is [`config.example.toml`](../config.example.toml).
