# 0011. When completing a leg, the user picks the operation type

- **Date:** 2026-10-16
- **Status:** accepted (amends the specification's form)

## Context

For the missing leg, the specification asked for a "side" field (bought or sold) and for the operation to be recomputed "with the same logic". But the script infers each leg's side from its aggressiveness (price versus bid/ask), and a manual leg has no bid/ask: it would need an invented aggressiveness. Besides, in multi-leg orders each leg's aggressiveness is weak evidence of its side.

## Decision

In the tab 2 form, the user enters the leg's data (type, strike, expiration, price and size) and **picks the operation type** (bull call, bear put, bull put, straddle…) from a catalogue filtered by the legs. The type sets each leg's side and, with it, the destination. Specifically:

- The manual leg goes into the script's `resumen()` **without aggressiveness**. The script already leaves legs without aggressiveness out of the average, so the aggressiveness column reflects measured values only.
- Structure, premium, size, conditions and times come from the script.
- Sides, direction, destination and net price come from the chosen type. The net price is computed with the script's own function, passing it those sides.
- If the chosen type contradicts the known leg's measured side, a warning is shown, but it is not blocked.

## Rejected alternatives

- **A synthetic ±1 aggressiveness depending on the side**: it mixes invented and measured values in the aggressiveness column.
- **Asking for the manual leg's bid/ask**: more data to type in, and it still relies on aggressiveness to infer the side.

## Consequences

- The type catalogue and how it maps to destinations are defined in phase 2 ([business rules](../business-rules.md#manual-corrections)).
- The same selector is used in tab 1 to correct complete multi-legs ([0020](0020-correcting-multi-legs.md)).
