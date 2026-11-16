# 0036. Single-leg conditions are grouped by bursts, relevant chunks and side

- **Date:** 2026-11-16
- **Status:** accepted (deliberately changes the level-3 script's output)

## Context

The script grouped every trade with two mechanisms: A, trades on different contracts with the same condition at most 50 ms apart, and B, trades on the same contract and condition at most 120 s after the previous one. On the real data, both made up operations:

- **B on liquid contracts.** Small trades from different actors, a few seconds apart, were chained for minutes into one large operation, and buys and sells were mixed in it. Many single-leg operations above the threshold existed only because of that chaining.
- **A on single-leg conditions.** Prints with conditions such as AUTO or ISOI on two contracts of the same underlying that happened to coincide within 50 ms were joined into verticals and diagonals that no order had sent.

Multi-leg conditions are different: the order is declared as multi-leg, and its legs print together.

## Decision

**Side of each trade.** Bought if its aggressiveness is > +0.25, sold if it is < −0.25, undetermined in between, at the boundary or without data. The script's `lado()` uses `ZONA_MUERTA` and `TOLERANCIA_ZONA_MUERTA` (10⁻⁹), the same boundary as the dashboard ([0017](0017-aggressiveness-boundary.md)), and the script's `direccion` and net price use it too. The dashboard's `leg_side()` calls it, so there is one boundary in the whole project.

**Multi-leg conditions** (`MULTI_LEG`: `MLET`, `MLAT`, `MLFT`, `MESL`, `MLCT`, `MFSL` and the options-with-stock ones): unchanged. Mechanism A only joins trades of these conditions, and B works as before.

**Single-leg conditions** (all the others): different contracts are never joined. Within each contract and condition:

1. **Burst.** Trades on the same side with at most `VENTANA_RAFAGA_S` = 1.0 s between consecutive ones form a chunk. "Consecutive" counts only the trades on that side, so a trade on the other side in between does not break the burst.
2. **Relevant chunk.** A chunk is relevant if its premium reaches the smaller of the underlying's threshold and `FRACCION_ESTIMADO` = 10 % of the contract's `premium_estimado` in level 1. Without an estimate, the minimum is 10 % of the threshold. If the underlying has no price in level 1, every chunk is relevant, as the threshold does not filter it either.
3. **Chaining.** By start time, a relevant chunk joins the operation in progress if it starts at most `VENTANA_S` = 120 s after that operation's last trade and its side is compatible: the same, or either of them undetermined. There is one operation in progress per contract and condition. The operation's side is that of its first chunk with a side; a relevant chunk on the opposite side closes it and opens a new one.
4. **A chunk that is not relevant** is an operation of its own and is never chained.

No trade disappears: every trade is in exactly one operation.

**New fields per operation,** at the end of the level-3 CSV: `lado` (`compra`, `venta` or `indeterminado`), `n_trozos`, `premium_trozo_mayor_M`, and `lado_de_trozo_menor` (true when the largest chunk is undetermined and the side comes from a smaller one). They are empty for operations of multi-leg conditions, which have no chunks. The `direccion` of a single-leg operation comes from its `lado`.

**Classification.** For an operation of single-leg conditions, the leg's side is the operation's side, not the leg's average aggressiveness. Manual corrections still prevail.

**Operation ID.** `id_operacion()` does not change. Under the new rule, two single-leg operations can start on the same millisecond, underlying and condition (a buy and a sell of the same contract, or two contracts), so `ids_operaciones()` resolves those collisions: the operation with the most premium keeps the ID, and the others add their contract and side, for example `20261013-XYZ-10:00:00.000-AUTO-20261120-185C-venta`. The suffix depends only on the content, so the ID stays stable across captures.

**The whole history** is rebuilt with the new rule. Edits whose ID no longer exists become orphans: they are shown and never deleted ([0003](0003-edits-in-own-files.md)). An edit whose operation now falls below the threshold stays attached to it, but the operation is no longer listed.

**Tab 1** marks with ◐ an operation whose side comes from a smaller chunk and with ≡ one with more than 10 chunks, each with its note. The Chunks and Largest chunk (M) columns are available in the columns pop-up, hidden by default.

**Validation and regression.**

- The script before this change is frozen as `tests/legacy/nivel3_agrupar_20261021.py`, with a hash test. A stored level 3 identical to its output is a "previous grouping rule"; if the frozen copies cannot be run, a stored file with the previous header is "not checked".
- The regression test keeps the history proven: that copy must produce, byte for byte, what the copy of 01/10 produces without cancellations ([0015](0015-drop-cancellations.md)).
- The new output is compared with that copy by invariants, on the real data and on the synthetic scenario: operations of multi-leg conditions keep the same trades and summary (only `direccion` and the net price may change at the ±0.25 boundary), every new single-leg operation is contained in an old one, no trade or premium is lost, and the console and the CSV keep their format.

## Rejected alternatives

- **Filtering in the dashboard and keeping the script**: two grouping logics ([0002](0002-single-grouping-logic.md)), and the pipeline's level 3 would keep the made-up operations.
- **Only shortening the 120 s window**: buys and sells would still be mixed, and a large order split over a few minutes would be cut into pieces.
- **Bursts by side without the relevance test**: small prints from different actors would still be chained.
- **A new ID format for every operation**: every existing edit would become an orphan. A numeric suffix on collisions depends on the reading order ([0007](0007-operation-id-format.md)).
- **Applying the rule only from the deployment day**: the history would mix two rules, and the charts over a date range would add up operations built in different ways.
- **Changing mechanism B for multi-leg conditions as well**: it is left as it is. Some multi-leg operations above the threshold last more than 5 minutes; whether that needs a different rule is a pending decision.

## Consequences

- There are fewer single-leg operations above the threshold, with less premium, and the charts change over the whole history.
- New level-3 variant N3-D ([data contract](../data-contract.md#level-3-operations)); the stored files from before the deployment show up in the validation as "previous grouping rule".
- [0007](0007-operation-id-format.md) is amended: the ID is unique through `ids_operaciones()`, no longer by construction alone. [0017](0017-aggressiveness-boundary.md) is amended: the script now uses the same boundary, which closes its pending decision.
- The script has to be deployed to the pipeline, and its expected hash updated ([level3-script.md](../level3-script.md)).
