import { LABEL_YEARS, TERMS, defaults, rich, txt } from "../app/text.js";
import { css } from "../color.js";
import { esc, popShort } from "../format.js";
import { isCapital } from "../world.js";
import { yieldGrid, amenities, censusGeography, hasGeography, industries, gdpRow, popLine, growthSpan, showPanel, yieldsTitle, censusTitle } from "./infoPanel.js";

defaults({
  "panel.no_cities": "No cities in this region's data.",
  "panel.region_foot": "Ranks are among the {count} mapped regions (1 = largest).",
});

/**
 * Opens the panel for state `idx` (index into world.json states / states.json).
 * ctx: {w, nation, states (states.json or null), cities, onClose, onPedia, onCity(city)}
 */
export function openStatePanel(idx, ctx) {
  const { w, nation } = ctx;
  const n = nation.nation;
  const geo = w.raw.states[idx] || {};
  // states.json is in the same order as world.json states; fall back to matching by fips.
  let st = ctx.states?.[idx];
  if (st && geo.fips && st.fips && st.fips !== geo.fips) st = ctx.states.find((s) => s.fips === geo.fips);
  st = st || { ...geo };
  const name = st.name || geo.name || TERMS.region.one;
  const abbr = st.abbr || geo.abbr || "";
  const count = ctx.states?.length || w.raw.states.length;

  const cities = (ctx.cities || []).filter((c) => (c.states || []).includes(abbr)).slice(0, 8);
  const cityRows = cities.length
    ? `<div class="city-list">${cities
        .map((c) => {
          const multi = (c.states || []).length > 1 ? `<span class="muted"> · ${esc(c.states.join("–"))}</span>` : "";
          return `<button class="city-row" data-city="${esc(c.id)}" title="${esc(c.full || c.name)}">
            <span class="cr-name">${isCapital(c) ? "★ " : ""}${esc(c.name)}${multi}</span>
            <span class="cr-pop">${popShort(c.population)}</span><span class="cr-go" aria-hidden="true">›</span></button>`;
        })
        .join("")}</div>`
    : `<p class="muted">${esc(txt("panel.no_cities"))}</p>`;

  const hasEcon = st.population != null || st.yields;
  showPanel({
    kind: "state",
    stripe: css(w.stateColor[idx] || [190, 190, 190]),
    title: name,
    sub: `${esc(abbr)}${geo.fips ? ` · FIPS ${esc(geo.fips)}` : ""}`,
    headExtra: hasEcon ? popLine(st, growthSpan(st, n), nation) : "",
    sections: [
      // With labelled years the title gives the figures' years; each tile still says "#3 of 13".
      st.yields && { title: LABEL_YEARS ? yieldsTitle(st, nation) : `Yields · rank among ${esc(TERMS.region.many.toLowerCase())}`, html: `<div class="yield-grid">${yieldGrid(nation, st.yields, st.ranks, count)}</div>` },
      hasEcon && { title: "Amenities &amp; Housing", html: amenities(st, n, nation) + gdpRow(st) },
      hasEcon && hasGeography(st) && { title: esc(txt("panel.geography")), html: censusGeography(st) },
      st.jobs && { title: LABEL_YEARS ? censusTitle("Top industries · where people work", nation) : "Top industries · where people work", html: industries(st, nation, 8) },
      { title: LABEL_YEARS ? `Biggest cities · ${esc(nation.year ?? "")}` : "Biggest cities", html: cityRows },
      !hasEcon && { title: "Data", html: `<p class="muted">${esc(TERMS.region.one)} statistics are not in this data build (states.json is missing).</p>` },
    ],
    foot: rich("panel.region_foot", { count, vintage: nation.vintage ?? "", gdp_vintage: nation.gdp_vintage ?? "",
      population_vintage: nation.population_vintage ?? "", census_vintage: nation.census_vintage || nation.vintage || "",
      unemployment_vintage: nation.unemployment_vintage ?? "" }),
    onClose: ctx.onClose,
    onPedia: ctx.onPedia,
    wire(panel) {
      panel.querySelectorAll("[data-city]").forEach((b) => {
        b.onclick = () => {
          const c = ctx.cities.find((x) => x.id === b.dataset.city);
          if (c) ctx.onCity(c);
        };
      });
    },
  });
}
