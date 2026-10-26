# 0028. In-the-money walls are shown, marked, and can be hidden

- **Date:** 2026-10-26
- **Status:** accepted

## Context

The specification describes a sold put as a support wall below the price and a sold call as a resistance wall above it. In the real data, almost half of the walls above the threshold sit on the other side of the price of their own capture: 39 of 81. Of those, 34 are sold calls below the price and 5 are sold puts above it, and 13 are more than 15% away from it. A wall that is already in the money may reflect motives other than defending a level, and the data cannot tell which.

## Decision

- The walls chart draws every wall at its strike, as before. In-the-money (ITM) walls get a lighter colour and "ITM" in their legend entry and tooltip.
- A "Show ITM walls" checkbox, on by default, hides them.
- A wall is ITM when it is a support with its strike above the price, or a resistance with its strike below it. The price is that of the operation's own capture, the closest available to when it traded. A strike exactly at the price is not ITM.
- The destination does not change: they are still walls, and the classification is untouched.

## Rejected alternatives

- **Drawing them like the rest**: it would hide a pattern that affects half the walls.
- **Leaving them out of the chart, with a separate total**: it changes what the chart counts without a business decision behind it; with the checkbox they are one click away.
- **Reclassifying them**: a business decision outside this phase. If it is ever taken, it gets its own entry.

## Consequences

- The chart can show a support above the price line or a resistance below it, and the colour says why.
- ITM is measured against each operation's capture price, while the line shows the latest price. If the price has moved since, a wall can be on one side of the line and be marked the other way.
