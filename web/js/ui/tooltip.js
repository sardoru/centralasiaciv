import { LABEL_YEARS } from "../app/text.js";
import { esc, int, popShort, compact } from "../format.js";
import { formatLensValue } from "./lenses.js";
import { glyph } from "./icon.js";
import { FOREIGN } from "../world.js";

const el = () => document.getElementById("tooltip");

const nameOf = (table, id) => table.find((t) => t.id === id)?.name;

// Cache the last shown content and measured box so pointermove inside the same cell/mark only updates
// left/top (avoiding innerHTML rewrites, MutationObserver churn and forced synchronous layout at 60-120 Hz).
let lastKind = null;
let lastCell = null; // {w, i, lens, showResources}
let lastCity = null;
let lastHtml = null;
let boxW = 0, boxH = 0, boxChildren = -1, boxTextLen = -1;
if (typeof window !== "undefined") {
  window.addEventListener("resize", () => { boxW = 0; boxH = 0; });
}

function position(t, mx, my) {
  // Re-measure if unmeasured or if an observer (e.g. City View) mutated the tooltip's DOM after show().
  if (!boxW || t.childNodes.length !== boxChildren || t.textContent.length !== boxTextLen) {
    // Measure at the corner, where the box has its full width: at its last position near the right edge it would wrap,
    // and that squeezed size would then be reused for every move inside the hex.
    t.style.left = "0px";
    t.style.top = "0px";
    const r = t.getBoundingClientRect();
    boxW = r.width;
    boxH = r.height;
    boxChildren = t.childNodes.length;
    boxTextLen = t.textContent.length;
  }
  t.style.left = Math.max(4, Math.min(window.innerWidth - boxW - 8, mx + 16)) + "px";
  t.style.top = Math.max(4, Math.min(window.innerHeight - boxH - 8, my + 16)) + "px";
}

export function showCellTooltip(mx, my, w, i, lens, showResources = true) {
  const t = el();
  if (!t.hidden && lastKind === "cell" && lastCell && lastCell.w === w && lastCell.i === i && lastCell.lens === lens && lastCell.showResources === showResources && lastCell.resources === w.resources) {
    position(t, mx, my);
    return;
  }
  const raw = w.raw;
  const lines = [];
  const city = w.cityByCell.get(i);
  // An edition that labels years names the population's: the year that ends growth_years (a July 1 estimate).
  if (city) lines.push(`<b>${esc(city.name)}</b> <span class="muted">· ${popShort(city.population)} people${LABEL_YEARS && city.growth_years ? ` (${esc(city.growth_years[1])})` : ""}</span>`);

  const wt = w.water[i];
  if (wt) {
    const depth = raw.elev[i] < 0 ? ` <span class="muted">· ${int(-raw.elev[i])} m deep</span>` : "";
    lines.push(`<b>${esc(nameOf(w.tables.water, wt) || "Water")}</b>${depth}`);
  } else {
    const cover = w.cover[i] > 0 ? nameOf(w.tables.cover, w.cover[i]) : null;
    const relief = w.relief[i] > 0 ? nameOf(w.tables.relief, w.relief[i]) : null;
    const terrain = [cover, relief].filter(Boolean).join(" · ") || (relief ?? "Land");
    lines.push(`<b>${esc(terrain)}</b> <span class="muted">· ${int(raw.elev[i])} m</span>`);
  }
  const o = raw.owner[i];
  if (o >= 0) {
    const county = raw.county[i] >= 0 ? raw.counties[raw.county[i]].name + ", " : "";
    lines.push(`${esc(county)}${esc(raw.states[o].name)}`);
    if (lens) lines.push(`${glyph(lens, 13)} ${esc(lens.name)}: <b>${formatLensValue(lens, lens.values[i])}</b>`);
  } else if (o === FOREIGN) {
    lines.push(`<span class="muted">Beyond the borders (not mapped)</span>`);
  }
  const res = showResources && w.resources?.byCell.get(i);
  if (res) {
    for (const it of res.slice(0, 4)) {
      const ty = w.resources.typeById.get(it.type);
      const num = it.value == null ? "" : Math.abs(it.value) < 1e6 ? int(it.value) : compact(it.value);
      const val = num ? ` · ${num}${ty.unit ? " " + esc(ty.unit) : ""}` : "";
      const kind = it.name && it.name !== ty.name ? ` <span class="muted">· ${esc(ty.name)}${val}</span>` : `<span class="muted">${val}</span>`;
      lines.push(`<span style="color:${esc(ty.color || "#efe4c6")}">${glyph(ty, 13)}</span> ${esc(it.name || ty.name)}${kind}`);
    }
    if (res.length > 4) lines.push(`<span class="muted">+${res.length - 4} more</span>`);
  }
  if (city) lines.push(`<span class="muted">Click to open the city</span>`);
  else if (o >= 0) lines.push(`<span class="muted">Click to open ${esc(raw.states[o].name)}</span>`);
  lastKind = "cell";
  lastCell = { w, i, lens, showResources, resources: w.resources };
  lastCity = null;
  show(mx, my, lines.join("<br>"));
}

/**
 * A tooltip with ready-made content: a string is HTML (escape any data yourself with format.js esc), {text} is
 * plain text. Used for registered static layers' tooltip(item).
 */
export function showHtmlTooltip(mx, my, content) {
  if (content == null || content === "") return hideTooltip();
  const html = typeof content === "string" ? content : esc(content.text ?? "");
  lastKind = "html";
  lastCell = null;
  lastCity = null;
  show(mx, my, html);
}

export function showCityTooltip(mx, my, city) {
  const t = el();
  if (!t.hidden && lastKind === "city" && lastCity === city) {
    position(t, mx, my);
    return;
  }
  lastKind = "city";
  lastCity = city;
  lastCell = null;
  show(mx, my, `<b>${esc(city.full)}</b><br><span class="muted">Click to open the city</span>`);
}

function show(mx, my, html) {
  const t = el();
  if (t.hidden || html !== lastHtml) {
    t.innerHTML = html;
    t.hidden = false;
    lastHtml = html;
    boxW = 0;
  }
  position(t, mx, my);
}

export function hideTooltip() {
  const t = el();
  if (t.hidden && lastHtml === null) return;
  t.hidden = true;
  lastKind = null;
  lastCell = null;
  lastCity = null;
  lastHtml = null;
  boxW = 0;
}
