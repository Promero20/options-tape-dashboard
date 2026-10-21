# Data quality

What came up when the specification was checked against the real data, and how the dashboard handles it. To see the current state of the data folder:

```bash
python -m tape_dashboard.report          # --info also shows the informational warnings
```

This describes the 15 captures from 12/08/2026 to 15/10/2026. The repository contains no data; the frequencies below are quality indicators, not market data.

## Summary by capture

| Capture | Stored level 3 versus the reconstruction |
|---|---|
| 12/08, 17/08 | missing |
| 25/08 | old format (N3-A) |
| 09/09 | old format (N3-B) |
| 11/09, 15/09, 16/09, 24/09, 01/10 | equivalent |
| 22/09 | level 3 without level 2 |
| 02/10, 07/10 | previous version (with the cancellation) |
| 06/10, 13/10, 15/10 | identical |

That is 14 rebuildable captures, in the order of 40,000 trades in total.

## Level 3 produced by earlier versions of the script

- **Identical** (06/10, 13/10 and 15/10): the stored level 3 matches the reconstruction byte for byte.
- **Previous version** (02/10 and 07/10): it matches byte for byte what the script produced before it dropped cancellations (see below).
- **Equivalent** (11/09 to 01/10): same operations, in the same order and with the same values. Only the single-leg label differs: the script then wrote `single_leg`, and now writes `single_leg_call` or `single_leg_put`.
- **Old format**: on 25/08 the threshold was not applied (all operations are stored) and grouping was slightly different. On 09/09 there was no strike, expiration or operation date.
- **Missing**: the pipeline did not produce a level 3 on 12/08 or 17/08. Both days are still rebuilt from level 2.

## 22/09 has no trades

Its level 2 has only a header. Its level 3 does store 30 operations from an old version, but without per-leg detail. The day is discarded ([decision 0009](decisions/0009-discard-2026-09-22.md)).

## Size filter: ≥ 10, not > 10

The specification said trades arrive filtered with `tradeSize > 10`. But between 15% and 35% of the rows in each capture have a size of exactly 10, and none is smaller: the actual filter is **≥ 10**. It does not affect the logic.

## Cancellations

There are two trades with condition `CANC`, one in the 02/10 capture and one in the 07/10 capture. None had been seen before.

- Each one cancels an earlier trade on the same contract, with the same size and price.
- The 01/10 version of the script did not treat them specially: the cancelled trade and the cancellation became two operations, and all four were above the threshold. The stored level 3 of those days therefore contains operations that never went through.
- Since 19/10 the script drops the cancellation and the trade it cancels before grouping ([decision 0015](decisions/0015-drop-cancellations.md)). The stored level 3 of those two days shows up in the validation as "previous version".

## Operations repeated across captures

Four operations from 14/09 appear in both the 15/09 and the 16/09 captures, because the pipeline queried the same contracts for that date again. In one of them the number of trades differs between captures. None is above the threshold. In multi-day ranges, the one from the most recent capture counts ([decision 0010](decisions/0010-operation-in-several-captures.md)).

## Level-2 oddities that do not change the logic

| Oddity | Frequency | Handling |
|---|---|---|
| Crossed quote (bid > ask) | 19 rows | With a negative `half_spread`, the sign of the aggressiveness is inverted. Reported; not corrected |
| Identical rows | 42–386 per capture | Level 2 has no trade ID, so legitimate repeated prints (same millisecond, price, size and venue) cannot be told apart from capture duplicates. They are kept, as the script does |
| Zero spread | 4–109 per capture | Empty `agresividad` and `spread_cero = True`: undetermined side |
| Exchange codes with a trailing line break (`"U\r"`) | 32 values | Trimmed; the script does not use them |
| Unknown exchange (`?`) | 37 values, all on 24/09 | Kept as is |
| Exchange as a letter (`C`, `N`) or as a name (`CBOE`, `NYSE`), depending on the capture | | Kept as is |

## Formats that change between captures

All of them are covered in the [data contract](data-contract.md):

- `fecha_consultada` as `MM/DD/YYYY` (09/09 to 15/09).
- `last_trade` in four formats.
- `type` in upper or lower case.
- `strike` with 0, 1 or 2 decimals.
- `fecha_volumen` with several dates separated by `;`.

## Questionable groupings

The 50 ms cross with the same Trade Condition, chained by union-find, sometimes joins prints that do not look like the same order: for example, multi-legs with one leg of thousands of contracts and another of a few dozen. Grouping is not changed; the list will flag them ([decision 0012](decisions/0012-flag-anomalous-size-ratios.md)).

## The original script on Windows

The 01/10 level-3 script wrote with the system's default encoding. On Linux, where the pipeline runs, that is UTF-8; on Windows (cp1252) it failed when writing the `→` character of calendars and diagonals. The version in `pipeline/` always writes UTF-8.
