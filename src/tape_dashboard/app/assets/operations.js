/*
 * Operations tab: switching between its two layouts (decision 0038).
 *
 * The switch runs in the browser, inside a view transition, so the panels
 * glide to their new place instead of jumping. Browsers without view
 * transitions, or with reduced motion requested, switch at once. Dash gets
 * the new layout only after the page has changed, so it does not redraw it
 * before the transition has captured the old one.
 */

window.dash_clientside = Object.assign({}, window.dash_clientside, {
  operations: {
    toggle_view: function (clicks, current) {
      var next = current === "horizontal" ? "vertical" : "horizontal";
      var className = "ops-tab view-" + next;
      var tab = document.getElementById("ops-tab");
      var apply = function () {
        if (tab) {
          tab.className = className;
          fitOperationsTab();
        }
      };
      var still = !tab || !document.startViewTransition ||
        window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      if (still) {
        apply();
        return [next, className];
      }
      return new Promise(function (resolve) {
        var done = function () { resolve([next, className]); };
        document.startViewTransition(apply).updateCallbackDone.then(done, done);
      });
    },
  },
});

/*
 * In the horizontal layout the tab fills the window below its top edge, so
 * the page does not scroll. The top edge moves when the warnings banner opens
 * or the header wraps, so it is measured again whenever the page changes size.
 */
function fitOperationsTab() {
  var tab = document.getElementById("ops-tab");
  if (!tab) {
    return;
  }
  var top = tab.getBoundingClientRect().top + window.scrollY;
  tab.style.setProperty("--ops-height", Math.max(520, window.innerHeight - top - 12) + "px");
}

window.addEventListener("resize", fitOperationsTab);
if (window.ResizeObserver) {
  new ResizeObserver(fitOperationsTab).observe(document.documentElement);
}
