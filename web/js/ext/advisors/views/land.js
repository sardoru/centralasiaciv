// Land advisor: national land cover, where each cover dominates, the states' make-up and who works the land.
import { esc, fin, ratio } from "../core/util.js";
import { pct, int, count3 } from "../core/fmt.js";
import { shareBar, barList, donut, smallMultiples } from "../core/charts.js";
import { createTable } from "../core/table.js";
import { section, tiles, segmented, lensButton, editionSources, topBy, frameBtn } from "../core/view.js";
import { LAND_KEYS, LAND_LABEL, LAND_COLOR, rowsHighlight } from "../core/data.js";
import { NATION, TERMS, defaults, hasText, rich, txt } from "../../../app/text.js";

defaults({
  "advisor.land.farmland_sub": "crops + pasture",
  "advisor.land.cover_note": "Share of the land in each cover type, averaged over every hex. Hover a type to light up the hexes where it is the largest cover; click to keep them lit.",
  "advisor.land.regions_title": "The regions' make-up",
  "advisor.land.regions_note": "Each region's land by cover type. Sort by any cover; hover one to outline it, click to open it.",
});

// NRCan's land cover has no pasture class (its cropland includes hay and pasture), so the Canadian edition drops it.
// The cover types the map has (Canada's land cover has no pasture class): set when the view mounts.
let KEYS = LAND_KEYS;

const LENS_OF = { forest: "forest", crop: "farmland", pasture: "farmland", developed: "developed" };

export function mount(ctx) {
  KEYS = (ctx.app.w.raw.tables?.cover || []).some((c) => c.key === "pasture") ? LAND_KEYS : LAND_KEYS.filter((k) => k !== "pasture");
  const { app, data, el, link } = ctx;
  const w = app.w;
  const P = w.raw.pct;
  const owner = w.raw.owner;
  const { states } = data.levels;
  if (!P) {
    el.innerHTML = `<p class="adv-empty pad">world.json has no land-cover shares.</p>`;
    return {};
  }

  // --- national shares and dominant cover per hex ---------------------------------------------------------------
  const sums = Object.fromEntries(KEYS.map((k) => [k, 0]));
  const dominant = new Map(KEYS.map((k) => [k, []]));
  let cells = 0;
  for (let i = 0; i < w.grid.size; i++) {
    if (!(owner[i] >= 0)) continue;
    let tot = 0, best = null, bv = 0;
    for (const k of KEYS) {
      const v = P[k]?.[i] || 0;
      tot += v;
      if (v > bv) { bv = v; best = k; }
    }
    if (tot <= 0) continue; // no land-cover samples
    cells++;
    for (const k of KEYS) sums[k] += P[k]?.[i] || 0;
    dominant.get(best).push(i);
  }
  const share = Object.fromEntries(KEYS.map((k) => [k, cells ? sums[k] / (cells * 100) : 0]));
  const other = Math.max(0, 1 - KEYS.reduce((a, k) => a + share[k], 0));

  el.insertAdjacentHTML("beforeend", tiles([
    { label: "Forest", value: pct(share.forest, 0), sub: "of the land", color: LAND_COLOR.forest },
    { label: "Farmland", value: pct(share.crop + (share.pasture || 0), 0), sub: txt("advisor.land.farmland_sub"), color: LAND_COLOR.crop },
    { label: "Built-up", value: pct(share.developed, 1), sub: "developed land", color: LAND_COLOR.developed },
  ]));

  // --- composition ----------------------------------------------------------------------------------------------
  const cBody = section(el, { title: "What covers the country", kicker: hasText("advisor.land.kicker") ? txt("advisor.land.kicker") : NATION.name, note: rich("advisor.land.cover_note") });
  let pinned = null;
  const parts = [...KEYS.map((k) => ({ key: k, label: LAND_LABEL[k], value: share[k], color: LAND_COLOR[k], text: pct(share[k]) })), { key: "other", label: "Other (barren rock, sand, ice)", value: other, color: "#6c6358", text: pct(other) }].sort((a, b) => (a.key === "other") - (b.key === "other") || b.value - a.value);
  const domHighlight = (k, dim = true) => (dominant.has(k) ? { cells: new Set(dominant.get(k)), dimOthers: dim, color: LAND_COLOR[k] } : null);
  const sb = shareBar(cBody, {
    parts,
    onHover: (p) => link.hover(p && p.key !== "other" ? { ...domHighlight(p.key), color: "#fff3c4" } : null),
    onClick: (p) => pin(p.key === "other" || pinned === p.key ? null : p.key),
  });
  const pinInfo = document.createElement("div");
  pinInfo.className = "adv-brushinfo";
  cBody.appendChild(pinInfo);
  const lensRow = document.createElement("div");
  lensRow.className = "adv-row";
  for (const [id, label] of [["forest", "Forest lens"], ["farmland", "Farmland lens"], ["developed", "Built-up lens"]]) {
    const b = lensButton(app, id, label);
    if (b) lensRow.appendChild(b);
  }
  cBody.appendChild(lensRow);
  function pin(k) {
    pinned = k;
    sb.setSelected(k);
    link.base(k ? domHighlight(k) : null, { frame: true });
    if (!k) { pinInfo.innerHTML = ""; return; }
    const n = dominant.get(k).length;
    const lens = LENS_OF[k] && app.lensById.get(LENS_OF[k]);
    pinInfo.innerHTML = `<b>${esc(LAND_LABEL[k])}</b> is the largest cover on <b>${int(n)}</b> hexes (${pct(n / cells, 0)} of the land hexes) and covers ${pct(share[k])} of all land.
      ${lens ? `<button type="button" class="adv-mini" data-lens="${lens.id}">Show the ${esc(lens.name)} lens</button>` : ""}${frameBtn()}<button type="button" class="adv-mini" data-clear>Clear</button>`;
  }
  pinInfo.addEventListener("click", (e) => {
    if (e.target.closest("[data-clear]")) pin(null);
    const l = e.target.closest("[data-lens]")?.dataset.lens;
    if (l) app.setLens(l);
  });

  // --- per state ------------------------------------------------------------------------------------------------
  const sBody = section(el, { title: txt("advisor.land.regions_title"), note: rich("advisor.land.regions_note") });
  const stRows = states.rows.filter((r) => KEYS.some((k) => fin(r.v[`land_${k}`])));
  const comp = (r) => `<span class="adv-minibar">${KEYS.map((k) => {
    const v = r.v[`land_${k}`];
    return fin(v) && v > 0 ? `<i style="width:${(v * 100).toFixed(2)}%;background:${LAND_COLOR[k]}" title="${esc(`${LAND_LABEL[k]} ${pct(v)}`)}"></i>` : "";
  }).join("")}</span>`;
  const domOf = (r) => KEYS.reduce((b, k) => ((r.v[`land_${k}`] ?? -1) > (r.v[`land_${b}`] ?? -1) ? k : b), KEYS[0]);
  let sortKey = "forest";
  const colsFor = (k) => [
    { key: "name", label: TERMS.region.short, align: "l", width: "minmax(0,1.1fr)", value: (r) => r.name, text: (r) => r.name },
    { key: "comp", label: "Land", align: "l", width: "minmax(0,1.6fr)", value: (r) => r.v[`land_${k}`], html: comp, title: `Sort by ${LAND_LABEL[k].toLowerCase()}` },
    { key: "share", label: LAND_LABEL[k], value: (r) => r.v[`land_${k}`], html: (r) => `<span class="dot" style="background:${LAND_COLOR[k]}"></span>${pct(r.v[`land_${k}`], 0)}` },
    { key: "dom", label: "Largest", align: "l", width: "minmax(0,.9fr)", value: (r) => LAND_LABEL[domOf(r)], text: (r) => LAND_LABEL[domOf(r)] },
  ];
  const sortSeg = document.createElement("div");
  sortSeg.className = "adv-row";
  sBody.appendChild(sortSeg);
  segmented(sortSeg, {
    label: "Sort by", value: sortKey,
    options: KEYS.map((k) => ({ value: k, label: LAND_LABEL[k].replace(" & hay", "").replace(" & desert", "") })),
    onChange: (k) => { sortKey = k; table.setColumns(colsFor(k), { key: "share", dir: "desc" }); drawShape(); },
  });
  let shape = "table";
  segmented(sortSeg, { label: "Show as", value: shape, options: [{ value: "table", label: "Table" }, { value: "grid", label: "Grid" }], onChange: (v) => { shape = v; drawShape(); } });
  const tableHost = document.createElement("div");
  const gridHost = document.createElement("div");
  sBody.append(tableHost, gridHost);
  const table = createTable(tableHost, {
    caption: `Land cover by ${TERMS.region.one.toLowerCase()}`, rank: true, maxHeight: 320, rows: stRows, columns: colsFor(sortKey), sort: { key: "share", dir: "desc" },
    onHover: (r) => link.hover(r ? rowsHighlight(states, [r]) : null),
    onClick: (r) => states.focus(r),
  });
  // Small multiples: one donut per state, sorted by the chosen cover.
  let grid = null;
  function drawShape() {
    tableHost.hidden = shape !== "table";
    gridHost.hidden = shape !== "grid";
    if (shape !== "grid") return;
    gridHost.innerHTML = "";
    const sorted = [...stRows].sort((a, b) => (b.v[`land_${sortKey}`] ?? -1) - (a.v[`land_${sortKey}`] ?? -1));
    grid = smallMultiples(gridHost, {
      min: 92,
      items: sorted.map((r) => ({ key: r.key, label: r.v.abbr || r.key, sub: pct(r.v[`land_${sortKey}`], 0), row: r })),
      render: (cell, it) => donut(cell, {
        interactive: false, size: 62, thickness: 12,
        parts: KEYS.map((k) => ({ key: k, label: LAND_LABEL[k], value: it.row.v[`land_${k}`], color: LAND_COLOR[k] })),
        center: { big: pct(it.row.v[`land_${sortKey}`], 0), small: "" },
        ariaLabel: `${it.row.name}: ${KEYS.map((k) => `${LAND_LABEL[k]} ${pct(it.row.v[`land_${k}`], 0)}`).join(", ")}`,
      }),
      onHover: (it) => link.hover(it ? rowsHighlight(states, [it.row]) : null),
      onClick: (it) => states.focus(it.row),
    });
  }
  drawShape();

  // --- who works the land ---------------------------------------------------------------------------------------
  const food = app.data.nation.yields?.find((y) => y.key === "food");
  const fBody = section(el, { title: "Who works the land", note: `${esc(food?.description || "Workers in agriculture, forestry, fishing & hunting.")} Ranked by share of the employed.` });
  const fHost = document.createElement("div");
  let fLevel = "states";
  segmented(fBody, { label: "Areas", value: fLevel, options: [{ value: "states", label: TERMS.region.many }, { value: "metros", label: "Metros" }], onChange: (v) => { fLevel = v; drawFood(); } });
  fBody.appendChild(fHost);
  function drawFood() {
    fHost.innerHTML = "";
    const lv = data.levels[fLevel];
    const list = topBy(lv.rows, (r) => ratio(r.v.y_food, r.v.employed), { n: 10, min: fLevel === "metros" ? 100000 : 0 });
    barList(fHost, {
      rank: true, ariaLabel: "Farm, forestry and fishing workers",
      rows: list.map((x) => ({ key: x.r.key, label: x.r.name, sub: `${count3(x.r.v.y_food)} workers`, value: x.v, text: pct(x.v), color: food?.color, row: x.r })),
      onHover: (r) => link.hover(r ? rowsHighlight(lv, [r.row]) : null),
      onClick: (r) => lv.focus(r.row),
    });
    if (fLevel === "metros") fHost.insertAdjacentHTML("beforeend", `<p class="adv-note">Metros of 100K+ people.</p>`);
  }
  drawFood();

  el.insertAdjacentHTML("beforeend", editionSources(data, "advisor.land"));

  return {
    onMapHover(h) {
      const r = h.cell >= 0 ? states.rowAtCell(h.cell) : null;
      table.setHot(r ? r.key : null);
      if (shape === "grid") grid?.setHot(r ? r.key : null);
      if (h.cell >= 0 && owner[h.cell] >= 0) {
        let best = null, bv = 0;
        for (const k of KEYS) { const v = P[k]?.[h.cell] || 0; if (v > bv) { bv = v; best = k; } }
        sb.setHot(best);
      } else sb.setHot(null);
    },
    onEscape() {
      if (pinned) { pin(null); return true; }
      return false;
    },
  };
}
