import { LABEL_YEARS, defaults, rich, txt } from "../app/text.js";
import { css } from "../color.js";
import { esc } from "../format.js";
import { isCapital } from "../world.js";
import { yieldGrid, amenities, censusGeography, hasGeography, industries, gdpRow, popLine, growthSpan, showPanel, hidePanel, yieldsTitle, censusTitle } from "./infoPanel.js";

defaults({
  "panel.city_industries": "Industries · where people work",
  "panel.city_foot": "Green ×N = this industry's share of jobs is N× the national share.",
  "panel.city_foot.unemployment_survey": "",
  "panel.city_foot.unemployment_census": "",
  "panel.city_foot.gdp": "",
  "panel.city_foot.no_gdp": "",
});

// The sources under a city panel: the edition's own wording (text pack), with the parts that depend on the city's data
// (a survey or a census unemployment rate; a GDP figure or none) chosen here.
function cityFoot(city, nation) {
  const vars = {
    vintage: nation.vintage ?? "", gdp_vintage: nation.gdp_vintage ?? "", population_vintage: nation.population_vintage ?? "",
    census_vintage: nation.census_vintage || nation.vintage || "", gdp_year: city.gdp_year ?? "",
    unemployment_vintage: nation.unemployment_vintage || "Labour Force Survey",
  };
  return rich("panel.city_foot", {
    ...vars,
    unemployment: txt(city.unemployment != null ? "panel.city_foot.unemployment_survey" : "panel.city_foot.unemployment_census", vars),
    gdp: txt(city.gdp != null ? "panel.city_foot.gdp" : "panel.city_foot.no_gdp", vars),
  });
}

/**
 * ctx: {w, nation, onClose, onPedia, onState(stateIndex)}
 */
export function openCityPanel(city, ctx) {
  const { w, nation } = ctx;
  const n = nation.nation;
  const owner = city.cell != null ? w.raw.owner[city.cell] : -1;
  const col = css(w.stateColor[owner] || [190, 190, 190]);

  // The city's states as links to their state panels.
  const states = (city.states || [])
    .map((abbr) => ({ abbr, i: w.raw.states.findIndex((s) => s.abbr === abbr) }))
    .map(({ abbr, i }) => (i >= 0 && ctx.onState
      ? `<button class="chip" data-state="${i}" title="Open ${esc(w.raw.states[i].name)}">${esc(abbr)}</button>`
      : `<span class="chip">${esc(abbr)}</span>`))
    .join("");

  const growth = growthSpan(city, n);

  showPanel({
    kind: "city",
    stripe: col,
    title: city.name,
    titleHtml: `${isCapital(city) ? `<span class="cap" title="National capital">★</span> ` : ""}${esc(city.name)}`,
    sub: `${esc(city.full || "")}${states ? `<div class="chips">${states}</div>` : ""}`,
    headExtra: popLine(city, growth, nation),
    sections: [
      { title: LABEL_YEARS ? yieldsTitle(city, nation) : "Yields", html: `<div class="yield-grid">${yieldGrid(nation, city.yields)}</div>` },
      { title: "Amenities &amp; Housing", html: amenities(city, n, nation) + gdpRow(city) },
      hasGeography(city) && { title: esc(txt("panel.geography")), html: censusGeography(city) },
      city.jobs && { title: esc(LABEL_YEARS ? censusTitle(txt("panel.city_industries"), nation) : txt("panel.city_industries")), html: industries(city, nation) },
    ],
    foot: cityFoot(city, nation),
    onClose: ctx.onClose,
    onPedia: ctx.onPedia,
    wire(panel) {
      panel.querySelectorAll("[data-state]").forEach((b) => (b.onclick = () => ctx.onState(+b.dataset.state)));
    },
  });
}

export const closeCityPanel = hidePanel;
