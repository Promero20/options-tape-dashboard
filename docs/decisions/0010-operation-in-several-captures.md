# 0010. An operation repeated in several captures counts once

- **Date:** 2026-10-16
- **Status:** accepted

## Context

If the same contract appears in level 1 on two consecutive days with the same `fecha_volumen`, the pipeline gets its Time & Sales twice, and the same operation shows up in both captures with the same ID. It has already happened between the 15/09 and 16/09 captures.

## Decision

In a multi-day range, an operation with the same ID in several captures counts once: the one from the **most recent capture** is kept, and the data report mentions it.

## Rejected alternatives

- **Keeping the first capture**: the most recent one is the one the user last reviewed in the "today" view.
- **No de-duplication**: the premium would be counted twice in the charts.

## Consequences

De-duplication happens in the data layer (phase 1). It does not apply to "today", which has a single capture.
