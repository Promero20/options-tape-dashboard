# Business rules

Rules applied by the capture pipeline and the dashboard. The reference implementation of the grouping is [`pipeline/nivel3_agrupar.py`](../pipeline/nivel3_agrupar.py): the dashboard imports its functions and does not reimplement them.

## 1. Premium threshold by underlying price

An operation only matters if its total premium (in dollars, adding up all its legs) reaches the threshold of its underlying's price bracket. The price comes from the level 1 of the same capture day.

| Underlying price | Threshold | Exact interval applied by the script |
|---|---|---|
| $1 – $50 | ≥ $500,000 | `1 ≤ price < 50` |
| $50 – $200 | ≥ $1,000,000 | `50 ≤ price < 200` |
| > $200 | ≥ $3,000,000 | `price ≥ 200`, **and also `price < 1`** |

Details fixed by the script (`umbral_premium` and `pasa_umbral`):

- The $50 and $200 boundaries belong to the upper bracket: at $50 the threshold is 1M and at $200 it is 3M.
- A price below $1 falls into the 3M bracket. The specification does not define that case and it is probably unintended. Fixing it would change the script's output, so it is left as a pending decision; no underlying below $1 has appeared so far.
- If a level-2 symbol has no price in level 1, the operation is **not** dropped.
- The threshold is compared with the **gross** premium in dollars. The conversion to millions (`premium_total_M`) is for display only.

Examples: with the underlying at $30, a $500,000 operation passes and a $499,999.99 one does not. At exactly $50, a $999,999 operation does not pass.

## 2. Aggressiveness and side of each trade

For each level-2 trade:

```
mid         = (bid + ask) / 2
half_spread = (ask − bid) / 2
agresividad = (trade price − mid) / half_spread
```

- `+1`: executed at the ask (aggressive buyer). `−1`: executed at the bid (aggressive seller). Above `+1` or below `−1`: paying more than the ask or selling below the bid.
- If `bid = ask`, the aggressiveness is left empty (`spread_cero = True`). It is not set to 0, because 0 would mean "close to the midpoint".
- A leg is **bought** if its aggressiveness is > +0.25, **sold** if it is < −0.25, and **undetermined** in between (`ZONA_MUERTA = 0.25`).
- A leg's aggressiveness is the size-weighted average of its trades', counting only the trades that have one.

## 3. Grouping trades into operations

**Cancellations are dropped before grouping.** A row with condition `CANC`, `CNCL`, `CNCO` or `CNOL` is not a trade: it cancels an earlier one. Both the cancellation and the trade it cancels are dropped; the cancelled trade is the most recent earlier one with the same contract, size and price ([decision 0015](decisions/0015-drop-cancellations.md)).

A group of trades is an operation: what looks like a single order or a single actor. There are two mechanisms, combined with union-find (if a trade is linked by either one, its whole group is merged):

**A) Legs of a multi-leg order.** Trades on **different** contracts of the same underlying, with the **same Trade Condition** and at most **50 ms** apart (`TOL_MS`). A multi-leg order prints all its legs at the same instant and with the same mechanism code.

**B) An order split within one contract.** Trades on the **same** contract, with the **same Trade Condition** and at most **120 s** (`VENTANA_S`) after the previous one.

Consequence: **all the rows of an operation share the same Trade Condition**, because both mechanisms only join trades with the same condition.

Example: a call bought in three AUTO trades at 10:00:00, 10:01:00 and 10:02:30 is a single operation (each trade is less than 120 s after the previous one). Another AUTO trade on the same contract at 10:10:00 is a separate operation.

### Fields the script computes per operation

- **Structure** (`estructura`), inferred from the contracts: `single_leg_call` or `single_leg_put`, `vertical` (same type and expiration), `calendar/diagonal` (more than one expiration), `straddle` (call + put at the same strike) and `straddle/strangle/risk-reversal` (call + put at different strikes).

  It is an indicative label, without each leg's side. For example, `vertical` also covers three legs of the same type and expiration. The classification rules (section 5) use the per-leg detail, not this label.
- **Incomplete legs** (`patas_incompletas`): there is a multi-leg Trade Condition (`MLET`, `MLAT`, `MLFT`, `MESL`, `MLCT`, `MFSL`, or the options-with-stock ones) and only one leg was captured.
- **With stock** (`stock_option`): an options-with-stock condition (`TLET`, `TLAT`, `TLCT`, `TLFT`, `TASL`, `TESL`, `TFSL`).
- **Direction** (`direccion`): taken from the leg with the most premium. If it was bought, call = bull and put = bear; if sold, the other way round; in the dead zone, `indeterminado`.
- **Net price** (`precio_neto`):
  - Single-leg: size-weighted average price.
  - Multi-leg: sum of the average prices with a sign (+ if the leg was bought, − if it was sold). Only computed if every leg has a clear side.
  - Empty if legs are missing or any side is ambiguous.

## 4. Operation ID

Every operation has a stable ID, which manual edits and positions point to:

```
YYYYMMDD-SYMBOL-HH:MM:SS.mmm-TC        e.g. 20261013-XYZ-11:00:00.100-MLET
```

It is the date and millisecond time of the operation's **first trade**, its underlying and its Trade Condition.

- The Trade Condition is needed because in the real data different groups start on the same contract and the same millisecond with different conditions (e.g. AUTO and ISOI).
- With it, the ID is **unique within a capture by construction**: two groups with the same underlying, millisecond and condition would already have been merged by mechanism A or B.
- The same operation can appear in two captures if the pipeline queried the same contract and date twice. It then has the same ID in both, and the dashboard keeps the most recent capture.

See [decision 0007](decisions/0007-operation-id-format.md).

## 5. Classifying operations

Implementation: [`src/tape_dashboard/rules/`](../src/tape_dashboard/rules/). Each operation above the threshold goes to **a single destination** ([decision 0004](decisions/0004-one-destination-per-operation.md)), so no premium is counted twice:

| Destination | Where it shows |
|---|---|
| `net` | Net directional chart: signed premium (bull +, bear −) at its strike and expiration |
| `walls` | Walls chart: premium by sold strike, as support or resistance |
| `undetermined` | Single-leg without a clear side: its own marker on the net chart, at its strike and expiration |
| `undetermined multi-leg` | Separate total (gross premium) |
| `discarded` | Separate total (gross premium) |
| `pending` | Tab 2, until the missing leg is completed |

### Side of each leg

A leg is **bought** if its aggressiveness is > +0.25, **sold** if it is < −0.25, and **undetermined** in between, at the boundary or without data.

Aggressiveness is computed in floating point, so a trade at a quarter of the half-spread comes out as 0.2499999… or as 0.2500000…3. There are 37 such legs in the real data. A 10⁻⁹ tolerance makes the boundary always undetermined, as the specification says ([decision 0017](decisions/0017-aggressiveness-boundary.md)).

### Rules, in order of precedence

| # | Case | Destination | Strike | Expiration | Premium |
|---|---|---|---|---|---|
| 1 | With stock (`TLET`, `TLAT`, `TLCT`, `TLFT`, `TASL`, `TESL`, `TFSL`), even if it has incomplete legs ([0016](decisions/0016-stock-and-incomplete-legs.md)) | discarded | — | — | gross |
| 2 | Incomplete legs (declared multi-leg with a single captured leg) | pending | — | — | gross |
| 3 | Three legs or more | discarded | — | — | gross |
| 4 | Single-leg bought | net (call = bull, put = bear) | its own | its own | total |
| 5 | Single-leg sold | walls (put = support, call = resistance) | its own | its own | total |
| 6 | Single-leg with an undetermined side | undetermined | its own | its own | total |
| 7 | Call + put: straddle, strangle, synthetic, risk reversal, or different expirations ([0022](decisions/0022-call-put-combos-and-synthetics.md)) | discarded, whatever the sides | — | — | gross |
| 8 | Pure calendar (same type and strike, different expiration) | discarded, whatever the sides | — | — | gross |
| 9 | Vertical or diagonal with an undetermined leg | undetermined multi-leg | — | — | gross |
| 10 | Vertical or diagonal with both legs on the same side ([0020](decisions/0020-correcting-multi-legs.md)) | undetermined multi-leg | — | — | gross |
| 11 | Debit vertical (bought leg > sold leg) | net | bought leg | shared | bought − sold |
| 12 | Credit vertical (sold leg > bought leg) | walls | sold leg | shared | sold − bought |
| 13 | Diagonal (clear sides), credit ones too ([0018](decisions/0018-credit-diagonals.md)) | net, with the direction of the leg with the most premium | bought leg | the nearest | \|bought − sold\| |

If a vertical has the same premium on both legs (neither debit nor credit), it goes to undetermined multi-leg.

**Direction.** On the net chart, the sign gives it. On the walls chart, a sold put or a bull put spread is bullish (support) and a sold call or a bear call spread is bearish (resistance). Undetermined ones are `undetermined`; discarded and pending ones have none. **This is the direction the list shows and edits**; the script's `direccion` column (taken only from the leg with the most premium) is kept as secondary data ([decision 0021](decisions/0021-direction-shown-in-the-list.md)).

### Examples

- **The specification's bear put**: 100 put bought for 10M and 90 put sold for 5M. Debit vertical: net, strike 100, −5M (bearish).
- **Bull put spread**: 100 put sold for 6M and 90 put bought for 2M. Credit vertical: walls, support at strike 100, 4M.
- **Credit diagonal**: January 125 call bought for 1M and November 130 call sold for 1.5M. Net at strike 125, November expiration. The leg with the most premium is the sold call, so it is bearish: −0.5M.
- **Long straddle**: call and put at the same strike, both bought. Discarded.

### Manual corrections

- **Single-leg**: the user sets the direction, and with it the side. Bull on a call = bought (net); bull on a put = sold (walls, support); bear on a call = sold (walls, resistance); bear on a put = bought (net); undetermined = undetermined.
- **Two legs**: the user picks the **operation type** from a catalogue filtered by the legs' geometry ([decisions 0011](decisions/0011-manual-leg-operation-type.md) and [0020](decisions/0020-correcting-multi-legs.md)). The type sets each leg's side and the operation is classified with the same rules.

| Geometry | Types offered |
|---|---|
| Call vertical | bull call (debit: buys the low strike), bear call (credit: sells the low strike) |
| Put vertical | bear put (debit: buys the high strike), bull put (credit: sells the high strike) |
| Diagonal | buys the near expiration, buys the far expiration |
| Calendar | long (buys the far one), short (sells the far one) |
| Call + put, same strike | long or short straddle, long or short synthetic |
| Call + put, different strikes | long or short strangle, bullish or bearish risk reversal |
| Call + put, different expirations | buys the call and sells the put, the reverse, buys both, sells both |
| Any | don't know (undetermined multi-leg) |

If the chosen type contradicts a leg's measured side (for example, the aggressiveness says buy and the type says sell), a warning is shown but the choice is kept. If the legs change and the type no longer fits (for example, because a manual leg was deleted), the correction is ignored with a warning, but not deleted.

Corrections do not apply to pending operations: the missing leg has to be completed first.

### Legs added by hand

A manual leg joins the operation as one more trade row: with the time and Trade Condition of the first trade (so the ID does not change) and **without aggressiveness**. Structure, premium, size and times are recomputed with the script's functions. The aggressiveness column keeps reflecting measured values only, because the script leaves legs without data out of the average. The side is set by the operation type chosen.

How it works in the interface ([decision 0030](decisions/0030-manual-legs.md)):

- It is entered in tab 2, which lists the pending operations of one capture that are above the threshold ([decision 0013](decisions/0013-tab-2-scope.md)). The form starts from the known leg's type, expiration and size.
- One manual leg per operation, and the operation type is required ("Don't know" is one of the options). Before saving, the form shows where the operation will go.
- It is edited or deleted from the operation's pop-up in tab 1. Deleting it also deletes the operation type chosen with it, and the operation goes back to tab 2. Clearing only the type keeps the leg, and the operation becomes an undetermined multi-leg.
- If a stored leg can no longer be applied, the operation is pending again with a note, and saving from tab 2 replaces the leg.

### Anomalous size ratio

A multi-leg whose largest leg has **10 times or more** the contracts of its smallest one is flagged for review ([decision 0012](decisions/0012-flag-anomalous-size-ratios.md)). In the real data, multi-legs above the threshold have ratios from 1 to 5.9, and then jump to 11.9 and more. It does not change the destination.

## 6. Charts

Implementation: [`src/tape_dashboard/charts/`](../src/tape_dashboard/charts/). The charts show one underlying over the chart panel's own range of capture dates, with the same operations as the list: above the threshold, with the manual edits applied, each operation once and without pending ones ([decision 0029](decisions/0029-chart-panel-controls.md)).

### Net directional

- One bar per expiration or per strike, to choose. They are the strike and expiration the classification assigns (section 5): the bought leg's strike for a debit vertical or a diagonal, and the nearest expiration for a diagonal.
- Bull premium upwards and bear premium downwards, with a marker for the net (bull − bear) on each bar that has directional operations.
- The premium of the undetermined single-legs, added up per bar, has its own marker. It is not part of the net.
- Under the chart, two totals of gross premium: undetermined multi-legs and discarded operations.
- By strike, a vertical line marks the reference price.

### Walls

- Premium of the operations in `walls` by sold strike, as support or resistance. The strike is on the vertical axis, so supports are expected below the price line and resistances above it.
- **In-the-money walls** ([decision 0028](decisions/0028-in-the-money-walls.md)): a support with its strike above the price, or a resistance with its strike below it, using the price of the operation's own capture. At exactly the price it is not ITM. They have a lighter colour and can be hidden.
- Filter by expiration; with none selected, all of them count.
- A horizontal line marks the reference price.

### Reference price

The underlying's price in the latest capture up to the end of the range whose level 1 includes it, shown with that capture's date.

### Every dollar in one place

Each operation has a single destination, so its premium lands in exactly one place: a net bar, an undetermined marker, a wall or one of the two totals. The tests check it for every underlying in the real data.
