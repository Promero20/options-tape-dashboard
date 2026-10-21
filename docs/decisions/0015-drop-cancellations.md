# 0015. Cancellations are dropped in the script, together with the trade they cancel

- **Date:** 2026-10-19
- **Status:** accepted (deliberately changes the level-3 script's output)

## Context

The 02/10 and 07/10 captures each contain a trade with condition `CANC`. Each one cancels an earlier trade on the same contract, with the same size and price. The script grouped them as ordinary trades, so the level 3 of those days contained two operations above the threshold that never went through: the cancelled trade and the cancellation itself.

## Decision

Before grouping, `quitar_cancelaciones()` in `pipeline/nivel3_agrupar.py` drops every row with a cancellation condition (`CANC`, `CNCL`, `CNCO`, `CNOL`) and the trade it cancels. That trade is the most recent earlier one with the same contract, size and price, because the tape does not say which one it is. If none is found, the cancellation is dropped anyway and a warning is given. The console adds a line with the count.

Since the change is in the script, the pipeline and the dashboard see the same thing.

## Rejected alternatives

- **Dropping them only in the dashboard**: the pipeline's level 3 would keep showing operations that never existed, and there would be two logics.
- **Keeping them and flagging them in the list**: their premium would still count in the charts.

## Consequences

- The regression test now compares the script with the frozen version run on the same level 2 **without the cancellations and the trades they cancel**. Without cancellations it is the same file, and the output is still byte-for-byte identical. This proves it is the only change, without freezing a new version.
- The validation recognises level-3 files produced before the change ("previous version").
- The script has to be deployed to the pipeline ([level3-script.md](../level3-script.md)).
