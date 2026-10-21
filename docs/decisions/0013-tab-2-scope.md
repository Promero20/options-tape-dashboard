# 0013. Tab 2: day selector and only operations above the threshold

- **Date:** 2026-10-16
- **Status:** accepted

## Context

Before applying the threshold there are about 150 operations with incomplete legs per capture, almost all with small premium; after the threshold about 10 remain. Completing each one means looking for the missing leg by hand.

## Decision

Tab 2 has its own day selector by capture date (defaulting to "today", with the same behaviour as in [0008](0008-ranges-by-capture-date.md)) and only lists incomplete operations that are above the threshold with the known leg.

## Rejected alternatives

- **Listing every incomplete operation**: too many, and almost all irrelevant.
- **Threshold by default with a switch to show everything**: the user prefers not to see them.

## Consequences

An operation that would only pass the threshold once the missing leg is added does not appear in tab 2.
