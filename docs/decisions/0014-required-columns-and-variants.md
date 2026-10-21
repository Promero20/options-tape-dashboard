# 0014. Minimal required columns, and new variants loaded with a warning

- **Date:** 2026-10-19
- **Status:** accepted

## Context

The specification asks for a CSV that matches no known schema variant to be reported, with its name and the missing columns, without ignoring or silently patching it. But "not matching" can mean two things: something essential is missing, or the header is different (another order, an extra or missing informational column) and the data is still usable. The pipeline changes its schema often: there are already five level-1 variants and five level-2 variants.

## Decision

- **Required** columns are only those the level-3 script or the dashboard need. Level 1: symbol, price, expiration, type and strike. Level 2: contract identification, time, price, size, bid, ask, condition, premium and aggressiveness. If any is missing, the file is not used and is reported with its name and the missing columns.
- A header that does not exactly match any **known variant** but has the required columns is loaded, with a "new variant" warning that lists the missing optional columns and the unknown ones.
- The known variants are recorded in `schemas.py` and in the [data contract](../data-contract.md). A test checks that every real file matches one of them.

## Rejected alternatives

- **Rejecting any unknown header**: a change in column order or a new informational column would leave the day without data.
- **Silently accepting any resolvable header**: it contradicts the specification.

## Consequences

When the pipeline changes its schema, the dashboard keeps working and says so. The variant is then added to the registry.
