// People advisor: population, growth, density, age and immigration.
import { esc, fin, colorScale, robustDomain, RAMPS } from "../core/util.js";
import { pct, int, signedPct, count3, fmtShort, fmtValue } from "../core/fmt.js";
import { barList, histogram, rampLegend } from "../core/charts.js";
import { createScatter } from "../core/scatter.js";
import { section, tiles, segmented, mapPicker, frameBtn, sourcesHtml, editionSources, topBy } from "../core/view.js";
import { rowsHighlight } from "../core/data.js";
import { growthLens } from "../core/lenses.js";
import { NATION, TERMS, defaults, rich, textList, txt } from "../../../app/text.js";

// Words for the county level: census divisions in the Canadian edition.
const CO = { many: TERMS.division.many, one: TERMS.division.one, Many: TERMS.division.short_many ?? TERMS.division.Many };

defaults({
  "advisor.people.residents_sub": "{vintage}",
  "advisor.people.growth_sub": "Population estimates",
  "advisor.people.growth_note": "Population change {years}, on the same borders both years. Metros of {min}+ people.",
  "advisor.people.density_note": "Divisions by residents per km² (log scale). Switch to <i>people</i> to weight each division by its population. Hover a bar to see those divisions; click to keep them outlined.",
});

const METRO_MIN = 250000;

export function mount(ctx) {
  const { app, data, el, link } = ctx;
  const n = data.nat;
  const { states, metros, counties } = data.levels;
  const yrs = n.growth_years || [];

  el.insertAdjacentHTML("beforeend", tiles([
    { label: "Residents", value: count3(n.population), sub: txt("advisor.people.residents_sub", { year: data.nation.year, vintage: data.vintage }) },
    { label: `Growth ${yrs.join("–")}`, value: signedPct(n.growth, 2), sub: txt("advisor.people.growth_sub") },
    { label: TERMS.area.both ?? TERMS.area.areas, value: int(metros.rows.length), sub: counties ? `${int(counties.rows.length)} ${CO.many}` : "" },
  ]));

  // --- the map: growth by default, so the map tells the same story as the first chart ---------------------------
  let gLevel = "metros";
  const mapRow = document.createElement("div");
  mapRow.className = "adv-sec adv-mapsec";
  el.appendChild(mapRow);
  const lensOpt = (value, label, id) => ({ value, label, lens: () => id });
  const picker = mapPicker(ctx, mapRow, {
    value: "growth",
    options: [
      { value: "growth", label: "Growth", lens: () => growthLens(data, gLevel) },
      ...(counties ? [lensOpt("density", "Density", "density"), lensOpt("age", "Age", "age"), lensOpt("foreign_born", "Born abroad", "foreign_born")] : []),
      { value: "terrain", label: "Terrain", lens: () => null },
    ],
  });

  // --- growth ---------------------------------------------------------------------------------------------------
  const gBody = section(el, { title: "Who is growing, who is shrinking", note: rich("advisor.people.growth_note", { years: yrs.join("–"), min: count3(METRO_MIN) }) });
  const gHost = document.createElement("div");
  segmented(gBody, { label: "Areas", value: gLevel, options: [{ value: "metros", label: "Metros" }, { value: "states", label: TERMS.region.many }], onChange: (v) => { gLevel = v; drawGrowth(); if (picker.value === "growth") picker.refresh(); } });
  gBody.appendChild(gHost);
  function drawGrowth() {
    gHost.innerHTML = "";
    const lv = gLevel === "metros" ? metros : states;
    const min = gLevel === "metros" ? METRO_MIN : 0;
    const fast = topBy(lv.rows, (r) => r.v.growth, { n: 8, min });
    const slow = topBy(lv.rows, (r) => r.v.growth, { n: 8, min, asc: true });
    const max = Math.max(...[...fast, ...slow].map((x) => Math.abs(x.v)));
    const mk = (list) => list.map((x) => ({ key: x.r.key, label: x.r.name, sub: gLevel === "metros" ? x.r.sub : "", value: x.v, text: signedPct(x.v), tone: x.v >= 0 ? "good" : "bad", row: x.r }));
    const opts = {
      diverging: true, max,
      onHover: (r) => link.hover(r ? rowsHighlight(lv, [r.row]) : null),
      onClick: (r) => lv.focus(r.row),
    };
    gHost.insertAdjacentHTML("beforeend", `<h4 class="adv-h4">Fastest growing</h4>`);
    barList(gHost, { ...opts, rows: mk(fast), ariaLabel: "Fastest growing" });
    gHost.insertAdjacentHTML("beforeend", `<h4 class="adv-h4">${slow.every((x) => x.v < 0) ? "Shrinking" : "Slowest growing"}</h4>`);
    barList(gHost, { ...opts, rows: mk(slow), ariaLabel: "Slowest growing" });
  }
  drawGrowth();

  if (!counties) {
    el.insertAdjacentHTML("beforeend", `<p class="adv-empty pad">counties.json is not built, so the county charts are missing.</p>`);
    el.insertAdjacentHTML("beforeend", sourcesHtml(data, textList("advisor.people.sources"), []));
    return {};
  }

  // --- density --------------------------------------------------------------------------------------------------
  const dBody = section(el, { title: "How crowded", note: rich("advisor.people.density_note") });
  const dCtl = document.createElement("div");
  dCtl.className = "adv-row";
  dBody.appendChild(dCtl);
  let weighted = false, pinnedBin = null;
  segmented(dCtl, { label: "Count", value: "counties", options: [{ value: "counties", label: CO.Many }, { value: "people", label: "People" }], onChange: (v) => { weighted = v === "people"; drawHist(); } });
  const dLens = document.createElement("button");
  dLens.type = "button";
  dLens.className = "adv-mini";
  dLens.textContent = "Colour the map by density";
  dLens.addEventListener("click", () => picker.set("density"));
  dCtl.appendChild(dLens);
  const histHost = document.createElement("div");
  dBody.appendChild(histHost);
  const binInfo = document.createElement("div");
  binInfo.className = "adv-brushinfo";
  dBody.appendChild(binInfo);
  let hist = null;
  const usDensity = counties.rows.reduce((a, r) => a + (r.v.population || 0), 0) / counties.rows.reduce((a, r) => a + (r.v.land_km2 || 0), 0);
  const cByKey = counties.byKey;
  const densRamp = RAMPS.heat;
  const densColor = colorScale({ type: "seq", domain: [0, 1], ramp: densRamp });
  function drawHist() {
    histHost.innerHTML = "";
    const vals = counties.rows.map((r) => ({ key: r.key, v: r.v.density, w: r.v.population }));
    const dom = [0.3, 30000];
    hist = histogram(histHost, {
      values: vals, log: true, bins: 30, domain: dom, weighted, height: 130,
      fmt: (v) => fmtShort("float", v), unitLabel: CO.many, weightFmt: (w) => `${count3(w)} people`,
      label: `Histogram of ${CO.one} population density`,
      colorOf: (_, t) => densColor(t),
      markers: [{ v: usDensity, label: "Lower-48 average" }],
      onHover: (bin) => link.hover(bin ? rowsHighlight(counties, bin.keys.map((k) => cByKey.get(k)), { dim: true }) : null),
      onClick: (bin) => {
        pinnedBin = pinnedBin === bin.i ? null : bin.i;
        const rows = pinnedBin != null ? bin.keys.map((k) => cByKey.get(k)) : [];
        link.base(rows.length ? rowsHighlight(counties, rows, { dim: true }) : null, { frame: rows.length > 1 });
        binInfo.innerHTML = rows.length ? `<b>${int(rows.length)}</b> ${CO.many} of ${fmtShort("float", bin.x0)}–${fmtShort("float", bin.x1)} people/km² · ${count3(rows.reduce((a, r) => a + (r.v.population || 0), 0))} people ${frameBtn()}<button type="button" class="adv-mini" data-clear>Clear</button>` : "";
      },
    });
  }
  binInfo.addEventListener("click", (e) => { if (e.target.closest("[data-clear]")) { pinnedBin = null; link.base(null); binInfo.innerHTML = ""; } });
  drawHist();

  // --- age and foreign-born -------------------------------------------------------------------------------------
  const aBody = section(el, { title: "Age and immigration", note: `Each dot is a ${CO.one}: median age across, share born abroad up, size = population, colour = density. Drag a rectangle to select ${CO.many}; they light up on the map. Hover the map to find a ${CO.one} here.` });
  const aCtl = document.createElement("div");
  aCtl.className = "adv-row";
  aBody.appendChild(aCtl);
  aCtl.innerHTML = `<span class="adv-note">Colour the map by</span><button type="button" class="adv-mini" data-map="age">median age</button><button type="button" class="adv-mini" data-map="foreign_born">born abroad</button>`;
  aCtl.addEventListener("click", (e) => { const v = e.target.closest("[data-map]")?.dataset.map; if (v) picker.set(v); });
  const dDom = robustDomain(counties.rows.map((r) => r.v.density), 0.02, true) || [1, 2000];
  const dColor = colorScale({ type: "seq", domain: dDom, log: true, ramp: RAMPS.heat });
  const big = topBy(counties.rows, (r) => r.v.population, { n: 6 }).map((x) => x.r.key);
  const scatter = createScatter(aBody, {
    height: 310,
    points: counties.rows.map((r) => ({ key: r.key, x: r.v.median_age, y: r.v.foreign_born, s: r.v.population, c: r.v.density, label: r.name, sub: r.sub, row: r })),
    x: { label: "Median age", fmt: (v) => String(+v.toFixed(0)) },
    y: { label: "Born abroad", fmt: (v) => fmtShort("pct", v) },
    size: { label: "Population", fmt: count3, max: 14, min: 1.4 },
    color: (c) => dColor(c), colorLabel: "Density", colorFmt: (v) => `${fmtValue("float", v)} /km²`,
    labels: big,
    refX: fin(medianOf(counties.rows, "median_age")) ? [{ v: medianOf(counties.rows, "median_age"), label: `median ${CO.one}` }] : [],
    onHover: (p) => link.hover(p ? rowsHighlight(counties, [p.row]) : null),
    onClick: (p) => counties.focus(p.row),
    onBrush: (set) => {
      const sel = set ? counties.rows.filter((r) => set.has(r.key)) : [];
      link.base(sel.length ? rowsHighlight(counties, sel, { dim: true }) : null, { frame: sel.length > 1 });
      selInfo.innerHTML = sel.length ? selSummary(sel) : "";
    },
  });
  aBody.insertAdjacentHTML("beforeend", rampLegend({ ramp: RAMPS.heat, domain: dDom, log: true, fmt: (v) => fmtShort("float", v), label: "People per km²" }));
  const selInfo = document.createElement("div");
  selInfo.className = "adv-brushinfo";
  aBody.appendChild(selInfo);
  function selSummary(sel) {
    const pop = sel.reduce((a, r) => a + (r.v.population || 0), 0);
    const top = [...sel].sort((a, b) => (b.v.population || 0) - (a.v.population || 0)).slice(0, 5);
    return `<b>${int(sel.length)}</b> ${CO.many} · ${count3(pop)} people (${pct(pop / n.population)} of ${esc(NATION.the)})<br><span class="sub">Largest: ${top.map((r) => `${esc(r.name)}, ${esc(r.sub)}`).join(" · ")}</span> ${frameBtn()}<button type="button" class="adv-mini" data-clear>Clear</button>`;
  }
  selInfo.addEventListener("click", (e) => { if (e.target.closest("[data-clear]")) { scatter.setSelected(null); link.base(null); selInfo.innerHTML = ""; } });

  el.insertAdjacentHTML("beforeend", editionSources(data, "advisor.people", { year: data.nation.year, vintage: data.vintage, county_vintage: data.countyVintage },
    data.countiesOffMap ? [`${int(data.countiesOffMap)} of the smallest ${esc(TERMS.division.many)} are smaller than one hex, so selecting them outlines nothing on the map.`] : []));

  return {
    onMapHover(h) {
      const r = h.cell >= 0 ? counties.rowAtCell(h.cell) : null;
      scatter.setHot(r ? r.key : null);
      hist?.setHot(r ? hist.binOf(r.v.density)?.i ?? null : null);
    },
    onEscape() {
      if (scatter.selected || pinnedBin != null) {
        scatter.setSelected(null); pinnedBin = null; link.base(null); selInfo.innerHTML = ""; binInfo.innerHTML = "";
        return true;
      }
      return false;
    },
  };
}

function medianOf(rows, k) {
  const s = rows.map((r) => r.v[k]).filter(fin).sort((a, b) => a - b);
  return s.length ? s[Math.floor(s.length / 2)] : null;
}
