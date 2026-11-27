import { esc } from "../format.js";
import { icon, glyph } from "./icon.js";
import { statDefs, fmtStat } from "./yieldReport.js";

// The national stats are buttons: each opens its report (ui/yieldReport.js, wired in main.js).
export function renderTopbar(nation) {
  const items = statDefs(nation).map((d) => {
    const ic = d.yield ? glyph(d.yield, 17) : icon(d.iconId, d.emoji, { size: 17 });
    const value = fmtStat(d, d.value);
    // Canadian stats come from different years (ui/yieldReport.js statDefs): each shows its year, as '21.
    const when = d.period ? ` (${d.period})` : "";
    const year = d.year ? `<span class="stat-yr" aria-hidden="true">’${esc(String(d.year).slice(-2))}</span>` : "";
    const tip = `${d.name}${when}: ${d.description} Click for the report.`;
    return `<button type="button" class="yield" data-report="${esc(d.key)}" aria-expanded="false" aria-haspopup="dialog" aria-controls="yield-report"
      title="${esc(tip)}" aria-label="${esc(d.name)}${esc(when)}: ${esc(value)}. Open the report">
      <span class="ico" style="color:${esc(d.color)}">${ic}</span><span style="color:${esc(d.color)}">${esc(value)}</span>${year}<span class="caret" aria-hidden="true"></span></button>`;
  });
  const el = document.getElementById("yields");
  el.innerHTML = items.join("");
  // When the bar is too narrow for every yield, the row scrolls on its own (search and buttons always fit);
  // a fade on the right edge shows there is more.
  const check = () => el.classList.toggle("clipped", el.scrollWidth > el.clientWidth + 1);
  if (typeof ResizeObserver === "function") new ResizeObserver(check).observe(el);
  check();
  watchBarOverflow(document.getElementById("topbar"));
  watchBarOverflow(el); // phones give the yields a row of their own that scrolls sideways
  document.getElementById("turn").innerHTML = `Turn <b>${esc(nation.year ?? "")}</b> · ${esc(nation.vintage || "")}`;
}

// A strip that scrolls sideways (the yields row on phones): mark which ends have more to show (.more-l / .more-r)
// so CSS can fade them. Without a cue the yields look cut off after the fourth or fifth value.
function watchBarOverflow(bar) {
  if (!bar || bar.dataset.overflowWatch) return;
  bar.dataset.overflowWatch = "1";
  let raf = 0;
  const update = () => {
    raf = 0;
    const max = bar.scrollWidth - bar.clientWidth;
    bar.classList.toggle("more-l", max > 1 && bar.scrollLeft > 1);
    bar.classList.toggle("more-r", max > 1 && bar.scrollLeft < max - 1);
  };
  const queue = () => { if (!raf) raf = requestAnimationFrame(update); };
  bar.addEventListener("scroll", queue, { passive: true });
  addEventListener("resize", queue);
  if (typeof ResizeObserver === "function") {
    const ro = new ResizeObserver(queue);
    ro.observe(bar);
    for (const child of bar.children) ro.observe(child);
  }
  // Extensions add top-bar buttons later.
  if (typeof MutationObserver === "function") new MutationObserver(queue).observe(bar, { childList: true, subtree: true });
  queue();
}
