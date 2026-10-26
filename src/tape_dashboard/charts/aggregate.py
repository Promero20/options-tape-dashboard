"""
What the net directional and walls charts show, computed from classified
operations (see docs/business-rules.md, section 6). Pure functions: no Dash
or Plotly. Each operation already has a single destination, so every dollar
lands in exactly one place: a net bar, an undetermined marker, a wall or one
of the two totals.
"""

from collections import Counter
from dataclasses import dataclass

from ..rules.classification import BULL, DISCARDED, NET, SUPPORT, UNDETERMINED_MULTI, UNDETERMINED_SINGLE, WALLS

EXPIRATION, STRIKE = "expiration", "strike"
AXES = (EXPIRATION, STRIKE)


@dataclass(frozen=True)
class NetBucket:
    """One bar of the net directional chart. Premiums in dollars, all positive."""
    key: object             # expiration (ISO date) or strike
    bull: float = 0.0
    bear: float = 0.0
    undetermined: float = 0.0
    n_bull: int = 0
    n_bear: int = 0
    n_undetermined: int = 0

    @property
    def net(self):
        return self.bull - self.bear


@dataclass(frozen=True)
class Totals:
    """Gross premium shown as separate totals under the net chart."""
    undetermined_multi: float = 0.0
    n_undetermined_multi: int = 0
    discarded: float = 0.0
    n_discarded: int = 0


@dataclass(frozen=True)
class WallLevel:
    """Premium of the walls at one strike, of one kind, in or out of the money."""
    strike: float
    wall: str               # support / resistance
    itm: bool
    premium: float
    count: int


def for_symbol(items, symbol):
    return [item for item in items if item.operation.symbol == symbol]


def symbol_counts(items):
    """(symbol, number of operations), alphabetically: the options of the underlying selector."""
    return sorted(Counter(item.operation.symbol for item in items).items())


def net_buckets(items, axis):
    """Bull, bear and undetermined single-leg premium by expiration or by strike, sorted by key."""
    if axis not in AXES:
        raise ValueError(f"unknown axis: {axis!r}")
    sums = {}
    for item in items:
        c = item.classification
        if c.destination not in (NET, UNDETERMINED_SINGLE):
            continue
        key = c.expiration if axis == EXPIRATION else c.strike
        bucket = sums.setdefault(key, {"bull": 0.0, "bear": 0.0, "undetermined": 0.0,
                                       "n_bull": 0, "n_bear": 0, "n_undetermined": 0})
        if c.destination == UNDETERMINED_SINGLE:
            kind = "undetermined"
        else:
            kind = "bull" if c.direction == BULL else "bear"
        bucket[kind] += abs(c.premium)
        bucket[f"n_{kind}"] += 1
    return [NetBucket(key, **values) for key, values in sorted(sums.items())]


def side_totals(items):
    multi = [item.classification.premium for item in items
             if item.classification.destination == UNDETERMINED_MULTI]
    discarded = [item.classification.premium for item in items
                 if item.classification.destination == DISCARDED]
    return Totals(sum(multi), len(multi), sum(discarded), len(discarded))


def is_itm(item):
    """
    A wall on the other side of the price of its capture: a support above it
    or a resistance below it (decision 0028). At the price, or without a
    price, it is not ITM.
    """
    c, price = item.classification, item.operation.price
    if c.destination != WALLS or price is None or c.strike is None:
        return False
    return c.strike > price if c.wall == SUPPORT else c.strike < price


def wall_levels(items, expirations=()):
    """Wall premium by (strike, kind, ITM), sorted. An empty `expirations` means all of them."""
    wanted = set(expirations or ())
    sums = {}
    for item in items:
        c = item.classification
        if c.destination != WALLS or (wanted and c.expiration not in wanted):
            continue
        key = (c.strike, c.wall, is_itm(item))
        premium, count = sums.get(key, (0.0, 0))
        sums[key] = (premium + c.premium, count + 1)
    return [WallLevel(*key, premium, count) for key, (premium, count) in sorted(sums.items())]


def wall_expirations(items):
    return sorted({item.classification.expiration for item in items
                   if item.classification.destination == WALLS})
