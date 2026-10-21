# 0017. An aggressiveness of exactly ±0.25 is an undetermined side

- **Date:** 2026-10-19
- **Status:** accepted

## Context

The specification says a leg is bought if its aggressiveness is **> +0.25**: the boundary is undetermined. The level-3 script uses `abs(agr) < 0.25` for its `direccion` column and for the net price, so there the boundary counts as a clear side.

Besides, aggressiveness is computed in floating point, and a trade at a quarter of the half-spread comes out as 0.2499999999999989 or as 0.25000000000000333, depending on rounding. There are 37 such legs in the real data, and the script classifies them by that noise.

## Decision

The dashboard's classification follows the specification: the boundary is undetermined, with a 10⁻⁹ tolerance to absorb floating-point noise.

The script is not touched: changing it would alter its output (the `direccion` and `precio_neto` columns). Aligning it is a separate decision.

## Rejected alternatives

- **Following the script's convention**: it contradicts the specification and depends on rounding.

## Consequences

On those legs, the script's `direccion` column can say bull or bear while the classification says undetermined. The list shows the classification's ([0021](0021-direction-shown-in-the-list.md)).
