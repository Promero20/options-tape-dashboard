"""Plotly figures of the net directional and walls charts, built from charts.aggregate."""

import plotly.graph_objects as go

from ..rules.classification import RESISTANCE, SUPPORT
from .aggregate import AXES, EXPIRATION

M = 1_000_000

COLORS = {
    "bull": "#1a7f37", "bear": "#c62828", "net": "#1f2933", "undetermined": "#8a8f98", "price": "#2f6fd6",
    (SUPPORT, False): "#1a7f37", (SUPPORT, True): "#a9d8b5",
    (RESISTANCE, False): "#c62828", (RESISTANCE, True): "#f0b3b3",
}

BASE_LAYOUT = dict(
    template="plotly_white", height=380, margin=dict(l=55, r=20, t=30, b=40),
    legend=dict(orientation="h", yanchor="bottom", y=1.0, x=0),
)


def empty_figure(message):
    fig = go.Figure()
    fig.update_layout(**BASE_LAYOUT, xaxis=dict(visible=False), yaxis=dict(visible=False),
                      annotations=[dict(text=message, showarrow=False, xref="paper", yref="paper", x=0.5, y=0.5)])
    return fig


def _bar_width(positions, extra=()):
    """
    Bar thickness on a numeric axis: 80% of the smallest gap between bars,
    but never less than 2.5% of the visible span, so a single wall far from
    the price line is still visible.
    """
    values = sorted(set(positions))
    span_values = values + [v for v in extra if v is not None]
    span = max(span_values) - min(span_values)
    gaps = [b - a for a, b in zip(values, values[1:])]
    width = 0.8 * min(gaps) if gaps else max(span * 0.05, 0.8)
    return max(width, span * 0.025)


def net_figure(buckets, axis, price=None):
    """
    Diverging bars: bull premium up, bear premium down, a marker with the net
    on each bar and another with the undetermined single-leg premium.
    """
    if axis not in AXES:
        raise ValueError(f"unknown axis: {axis!r}")
    if not buckets:
        return empty_figure("No net directional or undetermined operations in this range.")
    keys = [b.key for b in buckets]
    by_strike = axis != EXPIRATION
    width = _bar_width(keys, [price]) if by_strike else None

    fig = go.Figure()
    fig.add_bar(name="Bull", x=keys, y=[b.bull / M for b in buckets], width=width,
                marker_color=COLORS["bull"], customdata=[b.n_bull for b in buckets],
                hovertemplate="Bull: %{y:.3f}M (%{customdata} ops)<extra></extra>")
    fig.add_bar(name="Bear", x=keys, y=[-b.bear / M for b in buckets], width=width,
                marker_color=COLORS["bear"], customdata=[b.n_bear for b in buckets],
                hovertemplate="Bear: %{y:.3f}M (%{customdata} ops)<extra></extra>")
    directional = [b for b in buckets if b.n_bull or b.n_bear]     # no net marker on undetermined-only bars
    fig.add_scatter(name="Net", x=[b.key for b in directional], y=[b.net / M for b in directional], mode="markers",
                    marker=dict(symbol="line-ew", size=22, line=dict(width=3, color=COLORS["net"])),
                    hovertemplate="Net: %{y:+.3f}M<extra></extra>")
    undetermined = [b for b in buckets if b.n_undetermined]
    if undetermined:
        fig.add_scatter(name="Undetermined", x=[b.key for b in undetermined],
                        y=[b.undetermined / M for b in undetermined], mode="markers",
                        marker=dict(symbol="diamond", size=11, color=COLORS["undetermined"]),
                        customdata=[b.n_undetermined for b in undetermined],
                        hovertemplate="Undetermined: %{y:.3f}M (%{customdata} ops)<extra></extra>")

    fig.update_layout(**BASE_LAYOUT, barmode="relative", hovermode="x unified")
    fig.update_yaxes(title_text="Premium (M)", zeroline=True, zerolinecolor="#9aa5b1")
    if by_strike:
        fig.update_xaxes(title_text="Strike", type="linear")
        if price is not None:
            fig.add_vline(x=price, line_dash="dot", line_color=COLORS["price"],
                          annotation_text=f"Price {price:g}", annotation_position="top")
    else:
        fig.update_xaxes(title_text="Expiration", type="category", categoryorder="array", categoryarray=keys)
    return fig


def walls_figure(levels, price=None, price_date=None, show_itm=True):
    """
    Horizontal bars by sold strike, with the strike on the vertical axis so
    supports sit below the price line and resistances above it. ITM walls
    (decision 0028) have lighter colours and can be hidden.
    """
    shown = [level for level in levels if show_itm or not level.itm]
    if not shown:
        hidden = " (ITM walls are hidden)" if levels else ""
        return empty_figure(f"No walls in this range{hidden}.")
    width = _bar_width([level.strike for level in shown], [price])

    fig = go.Figure()
    for wall in (SUPPORT, RESISTANCE):
        for itm in (False, True):
            rows = [level for level in shown if level.wall == wall and level.itm == itm]
            if not rows:
                continue
            name = wall.capitalize() + (" ITM" if itm else "")
            fig.add_bar(name=name, orientation="h", y=[level.strike for level in rows],
                        x=[level.premium / M for level in rows], width=width,
                        marker_color=COLORS[(wall, itm)], customdata=[level.count for level in rows],
                        hovertemplate=f"{name} at %{{y:g}}: %{{x:.3f}}M (%{{customdata}} ops)<extra></extra>")

    fig.update_layout(**BASE_LAYOUT, barmode="stack")
    fig.update_xaxes(title_text="Premium (M)")
    fig.update_yaxes(title_text="Strike", type="linear")
    if price is not None:
        when = f" ({price_date})" if price_date else ""
        fig.add_hline(y=price, line_dash="dot", line_color=COLORS["price"],
                      annotation_text=f"Price {price:g}{when}", annotation_position="top right")
    return fig
