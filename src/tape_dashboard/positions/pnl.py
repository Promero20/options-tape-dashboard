"""What a position made (decision 0031). Pure functions; amounts in dollars, dates as ISO strings."""

from datetime import date

from ..rules.sides import BUY

MULTIPLIER = 100
OPEN, PARTIAL, CLOSED = "open", "partially closed", "closed"

_ZERO = 1e-9


def _sign(leg):
    return 1 if leg.side == BUY else -1


def leg_pnl(leg):
    """Result of a closed leg, before commissions; None while it is open."""
    if not leg.closed:
        return None
    return _sign(leg) * (leg.exit_price - leg.entry_price) * leg.quantity * MULTIPLIER


def status(position):
    closed = sum(1 for leg in position.legs if leg.closed)
    if closed == 0:
        return OPEN
    return CLOSED if closed == len(position.legs) else PARTIAL


def is_closed(position):
    return status(position) == CLOSED


def closing_date(position):
    """The date of the last leg to close, once all of them are; None until then."""
    return max(leg.exit_date for leg in position.legs) if is_closed(position) else None


def net_pnl(position):
    """Sum of the legs minus commissions, once the position is closed; None until then."""
    return sum(leg_pnl(leg) for leg in position.legs) - position.commissions if is_closed(position) else None


def entry_net(position):
    """Net premium at the opening: positive if it was a debit, negative if it was a credit."""
    return sum(_sign(leg) * leg.entry_price * leg.quantity * MULTIPLIER for leg in position.legs)


def pnl_pct(position):
    """Net P&L as a percentage of the net premium at the opening; None if open or if that premium is 0."""
    pnl, base = net_pnl(position), abs(entry_net(position))
    return None if pnl is None or base < _ZERO else pnl / base * 100


def days_held(position):
    """Calendar days from the opening to the last close; None until the position is closed."""
    closed_on = closing_date(position)
    return None if closed_on is None else (date.fromisoformat(closed_on) - date.fromisoformat(position.opened_on)).days


def expired_legs(position, today):
    """Legs still open after their expiration. They are only flagged: an ITM option does not expire at 0."""
    return [leg for leg in position.legs if not leg.closed and leg.exp_date < today.isoformat()]


def cumulative(closes):
    """Cumulative P&L per closing date from (closing date, P&L) pairs, in date order."""
    totals = {}
    for closed_on, pnl in closes:
        totals[closed_on] = totals.get(closed_on, 0.0) + pnl
    running, points = 0.0, []
    for closed_on in sorted(totals):
        running += totals[closed_on]
        points.append((closed_on, running))
    return points
