"""Range selector: which capture dates a preset covers (decision 0008: ranges use the capture date)."""

from dataclasses import dataclass
from datetime import date, timedelta

TODAY, WEEK, MONTH, CUSTOM = "today", "week", "month", "custom"
PRESETS = ((TODAY, "Today"), (WEEK, "Last week"), (MONTH, "Last month"), (CUSTOM, "Custom"))


@dataclass(frozen=True)
class CaptureRange:
    start: date | None
    end: date | None
    note: str = ""          # shown above the list: fallbacks and problems

    @property
    def empty(self):
        return self.start is None or self.end is None


def _parse(value):
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def resolve_range(dataset, preset, today, custom_start=None, custom_end=None):
    """
    Today: today's capture, or the latest one before it with a note.
    Last week / last month: captures from the last 7 / 30 calendar days.
    Custom: the dates picked, in either order.
    """
    if preset == TODAY:
        day, is_today = dataset.resolve_today(today)
        if day is None:
            return CaptureRange(None, None, "There are no captures yet.")
        note = "" if is_today else f"No capture for today ({today.isoformat()}); showing the latest one ({day.isoformat()})."
        return CaptureRange(day, day, note)
    if preset == WEEK:
        return CaptureRange(today - timedelta(days=6), today)
    if preset == MONTH:
        return CaptureRange(today - timedelta(days=29), today)
    if preset == CUSTOM:
        start, end = _parse(custom_start), _parse(custom_end)
        if start is None or end is None:
            return CaptureRange(None, None, "Pick a start and an end date.")
        return CaptureRange(min(start, end), max(start, end))
    raise ValueError(f"unknown range preset: {preset!r}")
