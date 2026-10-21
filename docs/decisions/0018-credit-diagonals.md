# 0018. Credit diagonals: the direction is that of the leg with the most premium

- **Date:** 2026-10-19
- **Status:** accepted

## Context

The specification sends every diagonal to net directional, credit ones too, at the bought leg's strike, with the nearest expiration and a premium of "bought − sold". In a credit diagonal that difference is negative, and the specification does not say which direction it has. For example: far call bought for 1M and near call sold for 1.5M.

## Decision

- **Direction**: that of the leg with the most premium, which is the same one the script computes. If the bought leg dominates, call = bull and put = bear; if the sold one dominates, sold call = bear and sold put = bull.
- **Amount**: |bought − sold|, with the sign of that direction.
- **Strike and expiration**: as in the specification (bought leg, nearest expiration).

In the example: −0.5M (bearish) at the bought call's strike.

## Rejected alternatives

- **Sending credit diagonals to walls**, like credit verticals: it contradicts the specification's explicit assumption.
- **Using the bought leg's direction with a negative amount**: a "bull" with negative premium cannot be drawn as diverging bars.

## Consequences

For debit diagonals the result is the same as with the specification's literal rule. In the captures analysed there is one credit diagonal above the threshold.
