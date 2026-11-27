// Military advisor for military.json with census counts and no headcount by base (the Canadian edition's; "General"):
// the Canadian Forces' main bases and the largest DND lands (Treasury
// Board's Directory of Federal Real Property), serving members and veterans by province and city (2021 Census), and
// garrison cities. Canada publishes no personnel by base or defence spending by province, so the U.S. troops-and-dollars
// section has no counterpart; the rest follows the U.S. view (views/military.js).
import { esc, fin, el as mk } from "../core/util.js";
import { int, pct, count3 } from "../core/fmt.js";
import { sizeLegend } from "../core/charts.js";
import { createTable } from "../core/table.js";
import { section, tiles, chips, segmented, mapPicker, sourcesHtml } from "../core/view.js";
import { rowsHighlight } from "../core/data.js";
import { stateLens } from "../core/lenses.js";
import { frameBox, focusPoint } from "../core/frame.js";

const COMP_COLOR = { army: "#7d9a46", navy: "#3f6fc2", air_force: "#6fb3e0", other: "#9a9aa8" };
const COMP_SHORT = { army: "Army", navy: "Navy", air_force: "Air Force", other: "Joint & other" };
const TIER_LABEL = { major: "Major", base: "Base", site: "Site" };
const AREA_CAP = 3000; // km²: circles stop growing here (the Cold Lake range is 11,700 km²)
const STEEL_RAMP = ["#141b26", "#2a3a52", "#46627f", "#6f91ad", "#a9c3d6", "#eef4f8"];

export async function mount(ctx) {
  const { app, data, el, link } = ctx;
  const mil = await app.loadData("military");
  if (!mil) {
    el.innerHTML = `<p class="adv-empty pad">military.json is not built, so the General has nothing to report.</p>`;
    return {};
  }
  const { states: stLevel, metros } = data.levels;
  const comps = (mil.components || []).map((c) => ({ ...c, color: COMP_COLOR[c.id] || "#9a9aa8", short: COMP_SHORT[c.id] || c.name }));
  const compById = new Map(comps.map((c) => [c.id, c]));
  const insts = (mil.installations || []).map((it, i) => ({ ...it, key: it.id || String(i) }));
  const instByKey = new Map(insts.map((it) => [it.key, it]));
  const nat = mil.national?.census || {};
  const vint = mil.vintage || {};
  const stateIdx = (abbr) => stLevel.byKey.get(abbr)?.ref ?? null;
  const stateName = (abbr) => stLevel.byKey.get(abbr)?.name || abbr;
  const cellRange = new Map();
  for (const r of mil.ranges || []) for (const c of r.cells || []) if (!cellRange.has(c)) cellRange.set(c, r);
  const st = { comps: new Set(comps.map((c) => c.id)), tier: "big", state: null };

  // --- headline -------------------------------------------------------------------------------------------------
  el.insertAdjacentHTML("beforeend", tiles([
    { label: "Serving members", value: count3(nat.serving), sub: `${pct(nat.serving_share, 2)} of residents 17+ (${esc(vint.census || "2021 Census")})`, color: "#a9c3d6" },
    { label: "Veterans", value: count3(nat.veterans), sub: `${pct(nat.veterans_share)} of residents 17+` },
    { label: "Bases", value: int(insts.length), sub: `+ ${int((mil.ranges || []).length)} large DND lands` },
  ]) + `<p class="adv-callout">No headcount is published for individual bases, so the map sizes them by land area. Serving members and veterans are counted where they live (2021 Census), by province and city.</p>`);

  // --- map colour -----------------------------------------------------------------------------------------------
  const mapRow = mk("div", "adv-sec adv-mapsec");
  el.appendChild(mapRow);
  const share = (key) => (abbr) => mil.states?.[abbr]?.census?.[key] ?? null;
  const servingLens = () => stateLens(data, "ca-serving", share("serving_share"), {
    name: "Serving members at home", emoji: "🎖️", format: "pct", unit: "of residents 17+", ramp: STEEL_RAMP, source: "statcan_military",
    description: "Residents 17+ currently serving in the Canadian Armed Forces (Regular Force or Primary Reserve), by province or territory, counted where they live (2021 Census, table 98-10-0142).",
  });
  const veteransLens = () => stateLens(data, "ca-veterans", share("veterans_share"), {
    name: "Veterans", emoji: "🎗️", format: "pct", unit: "of residents 17+", ramp: STEEL_RAMP, source: "statcan_military",
    description: "Veterans among residents 17+, by province or territory (2021 Census, table 98-10-0142).",
  });
  mapPicker(ctx, mapRow, {
    value: "terrain",
    options: [
      { value: "terrain", label: "Terrain", lens: () => null },
      { value: "serving", label: "Troops at home", lens: servingLens },
      { value: "veterans", label: "Veterans", lens: veteransLens },
    ],
  });

  // --- bases ----------------------------------------------------------------------------------------------------
  const iBody = section(el, {
    title: "Bases", kicker: esc(vint.installations || "Directory of Federal Real Property"),
    note: `The Canadian Forces' main bases, wings and stations: circle area follows their land (capped at ${int(AREA_CAP)} km²). ${esc(mil.rules?.tier || "")}`,
  });
  const counts = new Map();
  for (const it of insts) counts.set(it.component, (counts.get(it.component) || 0) + 1);
  const compChips = chips(iBody, {
    label: "Elements",
    items: comps.filter((c) => counts.get(c.id)).map((c) => ({ key: c.id, label: c.short, color: c.color, count: counts.get(c.id) })),
    onChange: (on) => { st.comps = on; apply(); },
  });
  void compChips;
  const tRow = mk("div", "adv-row");
  iBody.appendChild(tRow);
  segmented(tRow, {
    label: "Size", value: st.tier,
    options: [{ value: "major", label: "Major" }, { value: "big", label: "Major & bases" }, { value: "all", label: "Every site" }],
    onChange: (v) => { st.tier = v; apply(); },
  });
  const stateChip = mk("div", "adv-row adv-filterbar");
  iBody.appendChild(stateChip);
  stateChip.addEventListener("click", (e) => { if (e.target.closest("[data-clear-state]")) setState(null); });
  const legend = mk("div");
  legend.innerHTML = sizeLegend([100, 1000, AREA_CAP], (v) => 14 * Math.sqrt(v / AREA_CAP), (v) => `${int(v)} km²`, "Circle area = land area");
  iBody.appendChild(legend);
  const instTable = createTable(iBody, {
    caption: "Canadian Forces bases", search: "Search bases, provinces", rank: true, maxHeight: 280,
    searchText: (r) => `${r.name} ${r.state} ${compById.get(r.component)?.name || ""}`,
    columns: [
      { key: "name", label: "Base", align: "l", width: "minmax(0,1.9fr)", value: (r) => r.name, html: (r) => `<i class="dot" style="background:${esc(compById.get(r.component)?.color || "#999")}"></i>${esc(r.name)}${r.curated ? ` <span class="sub">flagship</span>` : ""}`, tip: (r) => `${r.name} · ${compById.get(r.component)?.name || r.component}` },
      { key: "component", label: "Element", align: "l", width: "minmax(0,.9fr)", hideBelow: 400, value: (r) => compById.get(r.component)?.short, text: (r) => compById.get(r.component)?.short || r.component },
      { key: "tier", label: "Tier", align: "l", width: "46px", value: (r) => ({ major: 0, base: 1, site: 2 })[r.tier], text: (r) => TIER_LABEL[r.tier] || r.tier },
      { key: "state", label: "Prov.", align: "l", width: "40px", value: (r) => r.state, text: (r) => r.state || "–" },
      { key: "area", label: "Area", width: "minmax(0,.8fr)", value: (r) => r.area_km2, text: (r) => (fin(r.area_km2) ? `${count3(r.area_km2)} km²` : "–"), title: "Land area of the base's properties" },
    ],
    rows: [], sort: { key: "area", dir: "desc" },
    onHover: (r) => {
      link.hover(r ? { cells: new Set(r.cell != null ? [r.cell] : []), label: r.name } : null);
      bubbles.setHot(r ? r.key : null);
    },
    onClick: (r) => flyTo(r),
  });
  function flyTo(r) {
    focusPoint(app, r.x, r.y, Math.min(app.cam.maxScale, Math.max(app.cam.scale, (app.cam.fitScale || 1) * 3)));
  }

  // --- by province ----------------------------------------------------------------------------------------------
  const pBody = section(el, {
    title: "Serving members and veterans by province",
    note: `Residents 17+ by military service status, where they live (${esc(vint.census || "2021 Census")}): serving means the Regular Force or the Primary Reserve. Canada publishes no personnel by base or defence spending by province.`,
  });
  const pRows = Object.entries(mil.states || {}).map(([abbr, s]) => ({ key: abbr, name: stateName(abbr), row: stLevel.byKey.get(abbr), ...s.census }));
  const pTable = createTable(pBody, {
    caption: "Serving members and veterans by province", rank: true, maxHeight: 260, search: "Search provinces",
    columns: [
      { key: "name", label: "Province", align: "l", width: "minmax(0,1.5fr)", value: (r) => r.name, text: (r) => r.name },
      { key: "serving", label: "Serving", value: (r) => r.serving, text: (r) => count3(r.serving) },
      { key: "serving_share", label: "Share", value: (r) => r.serving_share, text: (r) => pct(r.serving_share, 2), bar: { max: Math.max(...pRows.map((r) => r.serving_share || 0), 0.001), color: "rgba(135,150,171,.35)" }, title: "Serving members among residents 17+" },
      { key: "veterans", label: "Veterans", value: (r) => r.veterans, text: (r) => count3(r.veterans), hideBelow: 380 },
      { key: "veterans_share", label: "Share", value: (r) => r.veterans_share, text: (r) => pct(r.veterans_share), title: "Veterans among residents 17+" },
    ],
    rows: pRows, sort: { key: "serving_share", dir: "desc" },
    onHover: (r) => link.hover(r?.row ? rowsHighlight(stLevel, [r.row], { dim: true }) : null),
    onClick: (r) => setState(st.state === r.key ? null : r.key, true),
  });

  // --- garrisons ------------------------------------------------------------------------------------------------
  const gBody = section(el, { title: "Garrison cities", note: `${esc(mil.rules?.encampment || mil.rule || "")}` });
  const garrisons = Object.entries(mil.cities || {}).map(([id, c]) => ({ ...c, key: id, row: metros.byKey.get(id) })).filter((g) => g.row);
  const gTable = createTable(gBody, {
    caption: "Garrison cities", rank: true, maxHeight: 250, search: "Search cities",
    searchText: (g) => g.row.name,
    columns: [
      { key: "name", label: "City", align: "l", width: "minmax(0,1.8fr)", value: (g) => g.row.name, html: (g) => `${esc(g.row.name)} <span class="sub">${esc(g.row.sub)}</span>`, tip: (g) => `${g.row.name}: ${(g.installations || []).map((id) => instByKey.get(id)?.name || id).join(", ")}` },
      { key: "tier", label: "Tier", align: "l", width: "minmax(0,.8fr)", value: (g) => (g.tier === "fortress" ? 0 : 1), text: (g) => `${g.tier === "fortress" ? "Fortress" : "Garrison"}${g.naval ? " ⚓" : ""}` },
      { key: "af", label: "In uniform", value: (g) => g.armed_forces, text: (g) => count3(g.armed_forces), title: "Serving members among residents 17+ (2021 Census, where they live)" },
      { key: "share", label: "Share", value: (g) => g.share, text: (g) => pct(g.share), title: "Share of residents 17+ serving", bar: { max: Math.max(...garrisons.map((g) => g.share || 0), 0.01), color: "rgba(135,150,171,.35)" } },
    ],
    rows: garrisons, sort: { key: "share", dir: "desc" },
    onHover: (g) => link.hover(g ? rowsHighlight(metros, [g.row]) : null),
    onClick: (g) => metros.focus(g.row),
  });
  gBody.insertAdjacentHTML("beforeend", `<p class="adv-note">⚓ naval: the city's qualifying Navy bases outweigh its Army and Air Force ones (a major base counts 4, a base 1). A big city qualifies on headcount only when at least 2,000 residents and 0.3% of its residents 17+ serve: read the share column.</p>`);

  // --- ranges ---------------------------------------------------------------------------------------------------
  const rBody = section(el, { title: "Ranges and restricted ground", note: esc(mil.rules?.ranges || "") });
  const ranges = (mil.ranges || []).map((r) => ({ ...r, key: r.id }));
  const rTable = createTable(rBody, {
    caption: "Largest DND lands", rank: true, maxHeight: 240,
    columns: [
      { key: "name", label: "Range", align: "l", width: "minmax(0,2fr)", value: (r) => r.name, html: (r) => `<i class="dot" style="background:${esc(compById.get(r.component)?.color || "#999")}"></i>${esc(r.name)}` },
      { key: "state", label: "Prov.", align: "l", width: "40px", value: (r) => r.state, text: (r) => r.state || "–" },
      { key: "area", label: "Area", width: "minmax(0,.9fr)", value: (r) => r.area_km2, text: (r) => `${count3(r.area_km2)} km²`, bar: { max: Math.max(...ranges.map((r) => r.area_km2 || 0), 1), color: "rgba(194,74,62,.3)" } },
    ],
    rows: ranges, sort: { key: "area", dir: "desc" },
    onHover: (r) => link.hover(r ? { cells: new Set(r.cells || []), dimOthers: true, color: "#f09a7f", label: r.name } : null),
    onClick: (r) => { const b = app.highlightBounds({ cells: new Set(r.cells || []) }); if (b) frameBox(app, b, { pad: 60, maxScale: 2.6 }); },
  });

  // --- veterans and troops at home by city ------------------------------------------------------------------------
  const vBody = section(el, {
    title: "Veterans and troops at home",
    note: `Veterans and serving members among residents 17+, counted where they live (${esc(vint.census || "2021 Census")}), for every CMA and CA.`,
  });
  const vRows = Object.entries(mil.places || {}).map(([id, c]) => ({ ...c, key: id, row: metros.byKey.get(id) })).filter((r) => r.row && fin(r.veterans_share));
  const vTable = createTable(vBody, {
    caption: "Veterans and serving members by city", rank: true, maxHeight: 260, search: "Search cities",
    searchText: (r) => r.row.name,
    columns: [
      { key: "name", label: "City", align: "l", width: "minmax(0,1.7fr)", value: (r) => r.row.name, html: (r) => `${esc(r.row.name)} <span class="sub">${esc(r.row.sub)}</span>` },
      { key: "veterans", label: "Veterans", value: (r) => r.veterans, text: (r) => count3(r.veterans) },
      { key: "veterans_share", label: "Share", value: (r) => r.veterans_share, text: (r) => pct(r.veterans_share), bar: { max: Math.max(...vRows.map((r) => r.veterans_share || 0), 0.01), color: "rgba(135,150,171,.35)" }, title: "Veterans among residents 17+" },
      { key: "serving_share", label: "In uniform", value: (r) => r.serving_share, text: (r) => pct(r.serving_share), title: "Serving members among residents 17+" },
    ],
    rows: vRows, sort: { key: "veterans_share", dir: "desc" },
    onHover: (r) => link.hover(r ? rowsHighlight(metros, [r.row]) : null),
    onClick: (r) => metros.focus(r.row),
  });

  el.insertAdjacentHTML("beforeend", sourcesHtml(data, mil.sources || ["tbs_dfrp", "statcan_military"], [
    esc(mil.caveats || ""),
    "Base tiers come from land area, never headcount: a 'major' range can have few people, a small headquarters many.",
    "Bases and the census are different dates: the property directory as retrieved, the census in May 2021.",
  ]));

  // --- map ------------------------------------------------------------------------------------------------------
  const bubbles = ctx.bubbles("bases", {
    rMax: 14, minR: 2.6, alpha: 0.6,
    tip: (b) => {
      const it = b.it, c = compById.get(it.component);
      return `<b>${esc(it.name)}</b><br>${esc(c?.name || it.component)} · ${esc(TIER_LABEL[it.tier] || it.tier)}${fin(it.area_km2) ? ` · ${count3(it.area_km2)} km²` : ""}${it.state ? ` · ${esc(it.state)}` : ""}`;
    },
    onHover: (b) => instTable.setHot(b ? b.key : null),
    onClick: (b) => { instTable.setHot(b.key); flyTo(b.it); },
  });

  function visible() {
    return insts.filter((it) => st.comps.has(it.component) && (st.tier === "all" || it.tier === "major" || (st.tier === "big" && it.tier === "base")) && (!st.state || it.state === st.state));
  }
  function setState(abbr, fly = false) {
    st.state = abbr;
    pTable.setSelected(abbr ? new Set([abbr]) : null);
    apply();
    const i = abbr ? stateIdx(abbr) : null;
    if (i != null && fly) {
      const b = app.highlightBounds({ states: new Set([i]) });
      if (b) frameBox(app, b, { pad: 30, maxScale: 2.6 });
    }
  }
  function apply() {
    const vis = visible();
    instTable.setRows(vis);
    bubbles.set(vis.map((it) => ({ key: it.key, x: it.x, y: it.y, value: fin(it.area_km2) ? Math.min(AREA_CAP, it.area_km2) : 0, color: compById.get(it.component)?.color || "#999", it })), { vMax: AREA_CAP });
    const i = st.state ? stateIdx(st.state) : null;
    link.base(i != null ? { states: new Set([i]), dimOthers: true } : null);
    stateChip.innerHTML = st.state
      ? `<span class="adv-fchip">Province: <b>${esc(stateName(st.state))}</b> · ${int(vis.length)} bases<button type="button" data-clear-state aria-label="Clear the province filter">✕</button></span>`
      : "";
  }
  apply();

  return {
    onMapHover(h) {
      const owner = h.cell >= 0 ? app.w.raw.owner[h.cell] : -1;
      const abbr = owner >= 0 ? stLevel.rows[owner]?.key : null;
      pTable.setHot(abbr || null, false);
      const r = h.cell >= 0 ? cellRange.get(h.cell) : null;
      rTable.setHot(r ? r.id : null, !!r);
      if (h.item?.kind === "fort") instTable.setHot(instByKey.get(h.item.data?.id)?.key ?? null);
      if (h.item?.kind === "range") rTable.setHot(h.item.data?.id ?? null);
      const m = h.cell >= 0 ? metros.rowAtCell(h.cell) : null;
      gTable.setHot(m && mil.cities?.[m.key] ? m.key : null, false);
      vTable.setHot(m && mil.places?.[m.key] ? m.key : null, false);
    },
    onMapClick(ev) {
      const fort = ev.item?.kind === "fort" ? instByKey.get(ev.item.data?.id) : null;
      if (fort) { instTable.setHot(fort.key); flyTo(fort); return true; }
      if (ev.city || ev.state == null) return false;
      const abbr = stLevel.rows[ev.state]?.key;
      if (!abbr) return false;
      setState(st.state === abbr ? null : abbr);
      return true;
    },
    onEscape() {
      if (st.state) { setState(null); return true; }
      return false;
    },
  };
}
