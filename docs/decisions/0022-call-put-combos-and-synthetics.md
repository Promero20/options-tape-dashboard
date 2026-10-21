# 0022. Call + put with different expirations, and synthetics, are discarded like risk reversals

- **Date:** 2026-10-19
- **Status:** accepted, pending the decision on risk reversals

## Context

The specification discards straddles, strangles and risk reversals, and leaves open whether risk reversals should go to net. It does not mention two other call + put combinations that appear in the data:

- with **different expirations**: there is one above the threshold, which the script labels `calendar/diagonal`;
- with the **same strike and opposite sides** (long or short synthetic): the script labels it `straddle`.

Both have a clear direction, like the risk reversal.

## Decision

They are discarded, like risk reversals today. When risk reversals are decided, they will be revisited with them.

## Rejected alternatives

- **Sending them to net now**: it would pre-empt the pending decision on risk reversals, which belongs to the user.

## Consequences

In the captures analysed, the only one affected above the threshold is the combination with different expirations.
