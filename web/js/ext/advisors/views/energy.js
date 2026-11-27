// Energy & Resources advisor: the mapped power sites, mines and oil & gas plays.
import { edition } from "../../../app/edition.js";
import { TERMS, defaults, rich, txt } from "../../../app/text.js";
import { esc, fin } from "../core/util.js";
import { fmtValue, mw, int, count3 } from "../core/fmt.js";
import { barList, shareBar, stackedBars, sizeLegend } from "../core/charts.js";
import { createTable } from "../core/table.js";
import { section, tiles, chips, editionSources } from "../core/view.js";

defaults({
  "advisor.energy.mines_sub": "above size thresholds",
  "advisor.energy.oilgas_label": "Oil & gas",
  "advisor.energy.oilgas_sub": "mapped sites",
  "advisor.energy.min_note": "Sites not measured in MW are hidden while a minimum is set.",
  "advisor.energy.regions_note": "Mapped capacity per region, by type. Click one to filter everything to it; click it again to clear.",
});
import { frameBox, focusPoint } from "../core/frame.js";
import { glyph } from "../../../ui/icon.js";

const GROUPS = [
  { id: "thermal", label: "Power plants", types: ["nuclear", "coal_plant", "gas_plant", "geothermal"] },
  { id: "water", label: "Hydro", types: ["hydro", "pumped_storage"] },
  { id: "renew", label: "Wind, solar & batteries", types: ["wind", "solar", "battery"] },
  { id: "mines", label: "Mines", types: ["coal_mine", "gold", "copper", "iron", "silver", "platinum", "molybdenum", "lead_zinc", "rare_earths", "uranium"] },
  { id: "plays", label: "Oil & gas plays", types: ["oil", "gas"] },
];

export function mount(ctx) {
  const { app, data, el, link } = ctx;
  const res = app.data.resources;
  if (!res) {
    el.innerHTML = `<p class="adv-empty pad">resources.json is not built, so there is nothing to show here.</p>`;
    return {};
  }
  const types = res.types;
  const typeById = new Map(types.map((t) => [t.id, t]));
  const items = res.items.map((it, i) => ({ ...it, idx: i, key: String(i) }));
  const itemByRaw = new Map(res.items.map((raw, i) => [raw, items[i]]));
  const nat = res.summary?.national || {};
  const isMW = (t) => typeById.get(t)?.unit === "MW";
  const vMax = Math.max(1, ...items.filter((it) => isMW(it.type) && fin(it.value)).map((it) => it.value));
  const mwTypes = types.filter((t) => t.unit === "MW");
  const states = app.data.states || [];
  const stateIdx = new Map(states.map((s, i) => [s.abbr, i]));
  // Draw groups in GROUPS order, plus any type the groups do not list.
  // An edition with other resource types gives its own groups (manifest view.resource_groups; Canada's splits its power
  // plants as the U.S. does: thermal, hydro, wind and solar, no batteries listed).
  const definitions = edition.view?.resource_groups || GROUPS;
  const listed = new Set(definitions.flatMap((g) => g.types));
  const groups = definitions.map((g) => ({ ...g, types: g.types.filter((t) => typeById.has(t)) })).filter((g) => g.types.length);
  const extra = types.filter((t) => !listed.has(t.id)).map((t) => t.id);
  if (extra.length) groups.push({ id: "other", label: "Other", types: extra });

  const st = { on: new Set(types.map((t) => t.id)), min: 0, state: null };
  ctx.setShowResources(true);

  // --- headline -------------------------------------------------------------------------------------------------
  const totalMW = mwTypes.reduce((a, t) => a + (nat[t.id]?.value || 0), 0);
  const sites = mwTypes.reduce((a, t) => a + (nat[t.id]?.count || 0), 0);
  const groupCount = (id) => groups.find((g) => g.id === id)?.types.reduce((sum, t) => sum + (nat[t]?.count || 0), 0) || 0;
  const top = el.appendChild(document.createElement("div"));
  top.innerHTML = tiles([
    { label: "Mapped power", value: mw(totalMW), sub: `${int(sites)} sites` },
    { label: "Mines", value: int(groupCount("mines")), sub: txt("advisor.energy.mines_sub") },
    { label: txt("advisor.energy.oilgas_label"), value: int(groupCount(groups.some((g) => g.id === "fields") ? "fields" : "plays")), sub: txt("advisor.energy.oilgas_sub") },
  ]) + `<p class="adv-callout">${esc(res.summary?.note || "Totals of the mapped sites only.")}</p>`;

  // --- national mix ---------------------------------------------------------------------------------------------
  const mixBody = section(el, { title: "The national power mix", kicker: "Mapped sites above thresholds", note: "Capacity of the power sites on the map, by type. Small plants are not mapped, so this is <b>not</b> the country's total generating capacity: it shows where the large sites are and what they run on." });
  const mixParts = mwTypes.map((t) => ({ key: t.id, label: t.name, value: nat[t.id]?.value || 0, color: t.color, text: mw(nat[t.id]?.value), icon: glyph(t, 14) })).sort((a, b) => b.value - a.value);
  const mixHover = (p) => {
    if (!p) { link.hover(null); bubbles.setSelected(null); return; }
    const matching = visible().filter((it) => it.type === p.key);
    link.hover({ resources: new Set(matching.map((it) => it.idx)), dimOthers: true });
    bubbles.setSelected(new Set(matching.map((it) => it.key)));
  };
  const solo = (typeId) => {
    const only = st.on.size === 1 && st.on.has(typeId);
    st.on = only ? new Set(types.map((t) => t.id)) : new Set([typeId]);
    typeChips.set(st.on);
    apply();
  };
  shareBar(mixBody, { parts: mixParts, legend: false, onHover: mixHover, onClick: (p) => solo(p.key) });
  const mixBars = barList(mixBody, {
    rows: mixParts.map((p) => ({ ...p, sub: `${int(nat[p.key]?.count || 0)} sites` })),
    onHover: mixHover, onClick: (p) => solo(p.key), ariaLabel: "Mapped capacity by type",
  });

  // --- filters --------------------------------------------------------------------------------------------------
  const fBody = section(el, { title: "Filter the map", note: "Toggle types (Alt-click to show only one). The map dims the terrain and draws each power site as a circle sized by its capacity." });
  const typeChips = chips(fBody, {
    label: "Resource types",
    items: groups.flatMap((g) => g.types.map((t) => {
      const ty = typeById.get(t);
      return { key: t, label: ty.name.replace(/ \(shale play\)/, ""), color: ty.color, icon: glyph(ty, 13), count: nat[t]?.count ?? null };
    })),
    onChange: (on) => { st.on = on; apply(); },
  });
  const quick = document.createElement("div");
  quick.className = "adv-row";
  quick.innerHTML = groups.map((g) => `<button type="button" class="adv-mini" data-g="${g.id}">${esc(g.label)}</button>`).join("") +
    `<button type="button" class="adv-mini" data-g="all">All</button><button type="button" class="adv-mini" data-g="none">None</button>`;
  fBody.appendChild(quick);
  quick.addEventListener("click", (e) => {
    const g = e.target.closest("[data-g]")?.dataset.g;
    if (!g) return;
    st.on = g === "all" ? new Set(types.map((t) => t.id)) : g === "none" ? new Set() : new Set(groups.find((x) => x.id === g).types);
    typeChips.set(st.on);
    apply();
  });
  const slider = document.createElement("div");
  slider.className = "adv-slider";
  slider.innerHTML = `<label><span>Minimum size</span><input type="range" min="0" max="3000" step="100" value="0" aria-label="Minimum power-site capacity in MW"><b>Any size</b></label>
    <p class="adv-note adv-min-note" hidden>${rich("advisor.energy.min_note")}</p>`;
  fBody.appendChild(slider);
  const range = slider.querySelector("input");
  range.addEventListener("input", () => {
    st.min = +range.value;
    slider.querySelector("b").textContent = st.min ? `≥ ${int(st.min)} MW` : "Any size";
    slider.querySelector(".adv-min-note").hidden = !st.min;
    apply();
  });
  const stateChip = document.createElement("div");
  stateChip.className = "adv-row adv-filterbar";
  fBody.appendChild(stateChip);
  stateChip.addEventListener("click", (e) => { if (e.target.closest("[data-clear-state]")) setState(null); });
  const legendBox = document.createElement("div");
  fBody.appendChild(legendBox);

  // --- top sites ------------------------------------------------------------------------------------------------
  const tBody = section(el, { title: "Sites", note: "Every mapped site that passes the filters. Hover to find it on the map; click to fly there." });
  const sizeSort = (r) => (isMW(r.type) && fin(r.value) ? r.value : null);
  const table = createTable(tBody, {
    caption: "Mapped resource sites",
    search: `Search sites, ${(TERMS.region.short_many ?? TERMS.region.many).toLowerCase()}, operators`,
    searchText: (r) => `${r.name} ${r.state || ""} ${r.detail || ""} ${typeById.get(r.type)?.name || ""}`,
    rank: true,
    columns: [
      { key: "name", label: "Site", align: "l", width: "minmax(0,1.7fr)", value: (r) => r.name, html: (r) => `<span class="ic">${glyph(typeById.get(r.type), 13)}</span>${esc(r.name)}` },
      { key: "type", label: "Type", align: "l", width: "minmax(0,1fr)", value: (r) => typeById.get(r.type)?.name, text: (r) => typeById.get(r.type)?.name.replace(/ \(shale play\)/, "") || r.type },
      { key: "state", label: TERMS.region.column, align: "l", width: "46px", value: (r) => r.state, text: (r) => r.state || "–" },
      { key: "value", label: "Size", width: "minmax(0,.95fr)", value: sizeSort, text: (r) => sizeText(r), title: "Sort by capacity (MW; other units sort last)" },
    ],
    rows: [],
    sort: { key: "value", dir: "desc" },
    maxHeight: 300,
    onHover: (r) => {
      link.hover(r ? { resources: new Set([r.idx]), dimOthers: true, label: r.name } : null);
      bubbles.setHot(r ? r.key : null);
    },
    onClick: (r) => flyTo(r),
  });
  function sizeText(r) {
    const t = typeById.get(r.type);
    if (!fin(r.value)) return "–";
    if (t?.unit === "MW") return mw(r.value);
    if (t?.unit === "employees") return `${int(r.value)} staff`;
    if (/tons/.test(t?.unit || "")) return `${count3(r.value)} t/yr`;
    if (/km/.test(t?.unit || "")) return `${count3(r.value)} km²`;
    return fmtValue("float", r.value);
  }
  function flyTo(r) {
    focusPoint(app, r.x, r.y, Math.min(app.cam.maxScale, Math.max(app.cam.scale, (app.cam.fitScale || 1) * 3.2)));
  }

  // --- per state ------------------------------------------------------------------------------------------------
  const sBody = section(el, { title: `Power by ${TERMS.region.one.toLowerCase()}`, note: rich("advisor.energy.regions_note") });
  const stateRows = states
    .map((s, i) => ({ key: s.abbr, label: s.name, idx: i, parts: s.energy?.by_type || {}, total: s.energy?.total || 0, text: mw(s.energy?.total) }))
    .filter((r) => r.total > 0)
    .sort((a, b) => b.total - a.total);
  const stacks = stackedBars(sBody, {
    rows: stateRows, keys: mwTypes.map((t) => ({ key: t.id, label: t.name, color: t.color })), fmt: (v) => mw(v),
    ariaLabel: `Mapped power capacity by ${TERMS.region.one.toLowerCase()}`,
    onHover: (x) => {
      if (!x) return link.hover(null);
      const sIdx = x.row.idx;
      const set = x.part ? new Set(items.filter((it) => it.state === x.row.key && it.type === x.part).map((it) => it.idx)) : undefined;
      link.hover({ states: new Set([sIdx]), resources: set, dimOthers: true, label: x.part ? `${x.row.label}: ${typeById.get(x.part)?.name || x.part}` : x.row.label });
    },
    onClick: (x) => setState(st.state === x.row.key ? null : x.row.key, true),
  });
  const noPower = states.filter((s) => !(s.energy?.total > 0)).map((s) => s.abbr);
  if (noPower.length) sBody.insertAdjacentHTML("beforeend", `<p class="adv-note">No mapped power site: ${esc(noPower.join(", "))}.</p>`);

  // --- explainer ------------------------------------------------------------------------------------------------
  const eBody = section(el, { title: "What the symbols mean", note: "Each resource type, the threshold a site must pass to be mapped, and where the data comes from." });
  eBody.innerHTML = groups.map((g) => `<h4 class="adv-h4">${esc(g.label)}</h4>${g.types.map((t) => {
    const ty = typeById.get(t);
    const s = nat[t] || {};
    const src = data.source(ty.source);
    const total = fin(s.value) ? (ty.unit === "MW" ? mw(s.value) : `${count3(s.value)} ${ty.unit}`) : ty.unit === "km² play area" ? "areas not additive" : "";
    return `<div class="adv-explain" style="--cc:${esc(ty.color)}"><span class="ic">${glyph(ty, 22)}</span><div>
      <b>${esc(ty.name)}</b> <span class="sub">${int(s.count || 0)} mapped${total ? ` · ${esc(total)}` : ""}${ty.unit ? ` · measured in ${esc(ty.unit)}` : ""}</span>
      <p>${esc(ty.description)}</p><span class="src">Source: ${esc(src ? `${src.title} (${src.vintage || src.publisher})` : ty.source)}</span></div></div>`;
  }).join("")}`).join("");

  el.insertAdjacentHTML("beforeend", editionSources(data, "advisor.energy"));

  // --- map ------------------------------------------------------------------------------------------------------
  const bubbles = ctx.bubbles("sites", {
    rMax: 24,
    tip: (b) => {
      const it = b.it, t = typeById.get(it.type);
      return `<b>${esc(it.name)}</b><br>${esc(t.name)} · <b>${esc(mw(it.value))}</b>${it.state ? ` · ${esc(it.state)}` : ""}${it.detail ? `<br><span class="sub">${esc(it.detail)}</span>` : ""}`;
    },
    onHover: (b) => table.setHot(b ? b.key : null),
    onClick: (b) => { table.setHot(b.key); flyTo(b.it); },
  });

  function visible() {
    return items.filter((it) => st.on.has(it.type) && (!st.min || (isMW(it.type) && fin(it.value) && it.value >= st.min)) && (!st.state || it.state === st.state));
  }

  function setState(abbr, fly = false) {
    st.state = abbr;
    stacks.setSelected(abbr);
    apply();
    if (abbr && fly) {
      const b = app.highlightBounds({ states: new Set([stateIdx.get(abbr)]) });
      if (b) frameBox(app, b, { pad: 30, maxScale: 2.6 });
    }
  }

  function apply() {
    const typesOn = st.min ? new Set([...st.on].filter(isMW)) : st.on;
    const all = typesOn.size === types.length && !st.min;
    ctx.setResourceFilter(all ? null : { types: new Set(typesOn), minValue: st.min || undefined });
    const vis = visible();
    table.setRows(vis);
    const mwVis = vis.filter((it) => isMW(it.type) && fin(it.value));
    bubbles.set(mwVis.map((it) => ({ key: it.key, x: it.x, y: it.y, value: it.value, color: typeById.get(it.type).color, it })), { vMax });
    const sIdx = st.state ? stateIdx.get(st.state) : null;
    link.base({ dimOthers: true, states: sIdx != null ? new Set([sIdx]) : undefined });
    stateChip.innerHTML = st.state
      ? `<span class="adv-fchip">${esc(TERMS.region.one)}: <b>${esc(states[sIdx]?.name || st.state)}</b> · ${int(vis.length)} sites<button type="button" data-clear-state aria-label="Clear the ${esc(TERMS.region.one.toLowerCase())} filter">✕</button></span>`
      : "";
    const r = (v) => 24 * Math.sqrt(v / vMax);
    legendBox.innerHTML = sizeLegend([250, 1000, 4000].filter((v) => v <= vMax * 1.2), r, (v) => `${int(v)} MW`, "Circle area = capacity");
    mixBars.setSelected(st.on.size === 1 ? [...st.on][0] : null);
  }
  apply();

  return {
    onMapHover(h) {
      if (h.resource) {
        const it = itemByRaw.get(h.resource);
        if (it) table.setHot(it.key);
      }
    },
    onEscape() {
      if (st.state) { setState(null); return true; }
      return false;
    },
    destroy() {},
  };
}
