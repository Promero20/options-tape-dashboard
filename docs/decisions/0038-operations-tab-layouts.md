# 0038. Two layouts for the operations tab, switched with an animated transition

- **Date:** 2026-11-19
- **Status:** accepted

## Context

The operations tab put the list on the left and, on the right, the underlying charts with the selected operation below them. On a normal screen, seeing the selected operation means scrolling. The user wants a second layout that shows everything at once, and a smooth change between the two.

## Decision

- **A "⇅ Layout" button**, next to "✎ Columns" above the list, switches between:
  - **Vertical**, as before: the list on the left; the charts and the selected operation on the right.
  - **Horizontal**: the list across the top half; the charts at the bottom left and the selected operation at the bottom right. The tab fills the window below its top edge; the list and the selected operation scroll inside their panels, and the charts shrink to fit.
- **The change is animated**: the panels glide to their new place and size in about half a second, with the browser's view transitions. Where the browser does not support them, or the system asks for reduced motion, the layout changes at once. The switch runs in the browser (`assets/operations.js`); Dash only receives the layout chosen.
- **The layout chosen is remembered** in `preferences.json` in the user-data folder (`operations_view`), and the tab opens with it next time.
- **The GEX SPX button moves to the header of the charts panel**, next to the underlying picker, in both layouts.
- The charts follow the size of their panel.
- **Minimum sizes**: the list never shows fewer than about six rows and the chart is never shorter than about 280 px. On a window too short for both (below about 870 px of usable height), the page scrolls instead of squashing the panels. A first version split the window in halves without minimums, and on a 1080p screen with 125 % scaling it showed two rows and a flattened chart.
- **A more compact interface**, so that the horizontal layout fits common screens, which also gives the vertical one more rows:
  - the header, the data folder, Reload and the warnings share one line; the warnings are a badge that opens below it;
  - lower tab bars;
  - denser list rows (30 px), and a list that fills the window height in both layouts;
  - the date range of a range selector only appears with Custom, the only choice that uses it;
  - the chart controls on a single line in the horizontal layout.

## Rejected alternatives

- **Animating the CSS grid**: the list changes from one column to the whole width, which a grid cannot interpolate.
- **An animation library**: an extra dependency for a single transition ([0027](0027-editing-pop-up-without-extra-dependencies.md)).
- **A "Save as default" button, as for the columns** ([0035](0035-configurable-columns.md)): with only two layouts, the last one chosen is the natural default.
- **Browser storage**: lost with another browser or when its data is cleared.
- **A divider to drag between the two halves**: left for later, if the fixed split with minimums is not enough.

## Consequences

- Below 900 px wide, both layouts stack the three panels.
- The rest of the visual polish is still left to phase 8.
