# 0004. Each operation goes to a single destination

- **Date:** 2026-10-15 (specification)
- **Status:** accepted

## Context

The tab 1 charts add up premium by strike or by expiration. If an operation counted both in net directional and in walls, its premium would be counted twice.

## Decision

Each operation goes to exactly one of these destinations: net directional, walls, the undetermined total or the discarded total. Incomplete legs that have not been completed stay pending in tab 2. The rules table is in the [specification](../../specification.md#classification-rules).

## Consequences

- The premium of all destinations must add up to the total premium (a test checks it since phase 2).
- The real cases the table does not cover are resolved before phase 2.
