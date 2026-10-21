# 0016. An operation with stock is discarded even if it has incomplete legs

- **Date:** 2026-10-19
- **Status:** accepted

## Context

The specification sends operations with stock (`TLET`, `TLAT`, `TLCT`, `TLFT`, `TASL`, `TESL`, `TFSL`) to discarded, and those with incomplete legs to tab 2. But almost every operation with stock is also "incomplete": the script flags as incomplete any multi-leg with a single option leg, and in these the other leg is the stock. In the data analysed, that is 38 of the 39 operations with stock above the threshold.

## Decision

The stock rule wins: they are discarded.

## Rejected alternatives

- **Sending them to tab 2**: the missing leg is the stock, and the form only accepts options.

## Consequences

Tab 2 only shows option multi-legs missing an option leg.
