// The Almanac: what every number means and exactly where it comes from.
import { ANNOUNCEMENT_URL, ORIGINAL_URL } from "../app/project.js";
import { edition } from "../app/edition.js";
import { TERMS, defaults, rich } from "../app/text.js";

defaults({
  "almanac.about": "<p>A real country drawn like a strategy game. Every tile, city and number comes from public data, listed under <i>Sources</i>.</p><h4>How it's built</h4><p>The country is cut into {cols}×{rows} hexes, each {hex_km} km corner to corner.</p>",
  "almanac.amenities": "<p>Rent ÷ income = median rent × 12 ÷ median household income: a rough affordability signal, not a household-level burden rate.</p>",
  "almanac.regions": "<p>Click a land hex to see its region. Its numbers are the region's own totals and medians, not the sum of its cities.</p>",
  "almanac.beyond_borders": "Neighbouring land is shaded for geographic context.",
  "almanac.lenses_intro": "<p>Lenses recolour the map by one measure, built from division data.</p>",
  "almanac.resources_intro": "<p>Resources mark power plants, mines and oil &amp; gas fields on the tiles where they are. Press <b>R</b> to show or hide them.</p>",
});
import { resolveTables } from "../terrain.js";
import { esc } from "../format.js";
import { parseHex, luminance } from "../color.js";
import { icon, glyph } from "./icon.js";

const COVER_ICON = { forest_deciduous: "l-forest", forest_evergreen: "l-forest", forest_mixed: "l-forest", cropland: "l-farmland", pasture: "l-farmland", urban: "l-developed" };
// Glyph colour that reads on a resource medallion (dark on light faces such as nuclear yellow or silver).
const inkOn = (hex) => {
  try { return /^#[0-9a-f]{6}$/i.test(hex || "") && luminance(parseHex(hex)) > 0.4 ? "#1c1710" : "#f8f0d8"; } catch { return "#f8f0d8"; }
};
const CATEGORY = { energy: "Energy", mineral: "Minerals", agri: "Agriculture" };
const CREDIT = `<h4>Credits</h4>
      <p>Original project: <b>usaciv</b> by Andrej Karpathy
      (<a href="${ORIGINAL_URL}" target="_blank" rel="noopener">karpathy.ai/usaciv</a> ·
      <a href="${ANNOUNCEMENT_URL}" target="_blank" rel="noopener">announcement</a>). This copy extends it with a Canada
      edition: switch between the two with the menu at the top left.</p>`;

export function initPedia(data) {
  const modal = document.getElementById("pedia");
  const card = modal.querySelector(".modal-card");
  const nav = document.getElementById("pedia-nav");
  const body = document.getElementById("pedia-body");
  const srcName = (id) => data.sources?.find((s) => s.id === id)?.title || id || "";
  let restoreFocus = null;

  const h2 = (ic, fb, text) => `<h2>${icon(ic, fb, { size: 24 })}<span>${esc(text)}</span></h2>`;

  const pages = {
    "About this map": () => `
      ${h2("pedia", "📖", "About this map")}
      ${rich("almanac.about", { cols: data.world.grid.cols, rows: data.world.grid.rows, hex_km: data.world.grid.radius * 2, year: data.nation.year ?? "" })}
      ${CREDIT}`,
    Yields: () => `
      ${h2("y-production", "⚙️", "Yields")}
      <p>Civilization's yields mapped onto real measures. Job-based yields count <i>residents</i> employed in an industry
      (where workers live, not where they work). <b>Gold is GDP</b>: output per year, counted where the work is done.</p>
      <table>${data.nation.yields.map((y) => `<tr><td class="ic" style="color:${esc(y.color)}">${glyph(y, 26)}</td><td><b style="color:${esc(y.color)}">${esc(y.label)}${y.key === "gold" ? " (GDP)" : ""}</b><br>${esc(y.description)}</td></tr>`).join("")}</table>
      <h4>Amenities &amp; housing</h4>
      ${rich("almanac.amenities", { year: data.nation.year ?? "", gdp_year: data.nation.nation.gdp_year ?? "",
        metro_gdp_vintage: data.sources?.find((s) => s.id === edition.sources?.roles?.metro_gdp)?.vintage || "an earlier year",
        unemployment_year: data.nation.nation.unemployment_year ?? "latest" })}`,
    [TERMS.region.many]: () => `
      ${h2("terrain", "🗺️", TERMS.region.many)}
      ${rich("almanac.regions", { year: data.nation.year ?? "", gdp_year: data.nation.nation.gdp_year ?? "", vintage: data.nation.vintage ?? "",
        gdp_part: data.nation.gdp_vintage ? `; GDP from ${data.nation.gdp_vintage}` : "" })}
      ${data.states ? "" : `<p class="muted">This data build has no states.json, so state panels show names and cities only.</p>`}`,
    Terrain: () => {
      const t = data.w?.tables || resolveTables(data.world.tables);
      const hasCover = Array.isArray(data.world.cover);
      const row = (x) => `<tr><td class="nm">${x.color ? `<span class="swatch" style="background:${esc(x.color)}"></span>` : ""}${
        COVER_ICON[x.key] ? icon(COVER_ICON[x.key], "", { size: 15 }) + " " : ""}<b>${esc(x.name)}</b></td><td>${esc(x.rule || "")}</td></tr>`;
      return `
      ${h2("terrain", "🗺️", "Terrain")}
      <p>Each hex averages the ETOPO1 elevation samples inside it. Relief comes from the mean elevation and roughness
      (standard deviation) of those samples; shading comes from elevation differences with neighbouring hexes, lit from the
      north-west.</p>
      <h4>${icon("l-forest", "🌲", { size: 16 })} Land cover</h4>
      ${hasCover
        ? `<p>The base colour of each hex is its dominant land-cover group: the largest group among the land samples inside it.
           Small symbols show the mix: trees scale with the forest share, and fields, reeds, shrubs and grass tufts mark farmland,
           wetland, scrub and grassland.</p>
           <table>${t.cover.filter((x) => x.id > 0).map(row).join("")}</table>`
        : `<p class="muted">This data build has no land-cover layer yet; land is coloured by elevation.</p>`}
      <h4>Relief</h4>
      <table>${t.relief.map(row).join("")}</table>
      <h4>${icon("r-hydro", "💧", { size: 16 })} Water</h4>
      <table>${t.water.filter((x) => x.id > 0).map(row).join("")}</table>
      <h4>Beyond the borders</h4>
      <p class="muted">${rich("almanac.beyond_borders")}</p>`;
    },
    Lenses: () => `
      ${h2("layers", "▤", "Lenses")}
      ${rich("almanac.lenses_intro", { year: data.nation.year ?? "", vintage: data.lenses.vintage ?? "" })}
      <p>The legend shows how many hexes fall at each value. Hover or drag on it to show only that range on the map.</p>
      ${(data.lenses.groups || [{ id: null, name: "" }]).map((g) => {
        const ls = data.lenses.lenses.filter((l) => !g.id || l.group === g.id);
        if (!ls.length) return "";
        return `${g.name ? `<h3 class="grp">${icon(`g-${g.id}`, "", { size: 16 })} ${esc(g.name)}</h3>` : ""}${ls.map((l) => `
          <div class="lens-entry"><div class="le-ic">${glyph(l, 26)}</div><div>
          <h4>${esc(l.name)}</h4><p>${esc(l.description)}<br>
          <i class="le-ramp" style="background:linear-gradient(90deg, ${(l.ramp || []).map(esc).join(",")})"></i>
          <span class="muted">Scale: ${esc(l.scale)}, ${l.domain[0].toLocaleString()}–${l.domain[1].toLocaleString()} ${esc(l.unit)}${
            l.higher_is === "good" ? " · higher is better" : l.higher_is === "bad" ? " · higher is worse" : ""}${l.source ? " · " + esc(srcName(l.source)) : ""}</span></p></div></div>`).join("")}`;
      }).join("")}`,
    Resources: () => {
      const r = data.resources;
      if (!r?.types?.length) return `${h2("resources", "⛏️", "Resources")}<p class="muted">This data build has no resources layer.</p>`;
      const count = new Map();
      for (const it of r.items || []) count.set(it.type, (count.get(it.type) || 0) + 1);
      const cats = [...new Set(r.types.map((t) => t.category || "other"))];
      return `
      ${h2("resources", "⛏️", "Resources")}
      ${rich("almanac.resources_intro")}
      ${cats.map((c) => `<h4>${esc(CATEGORY[c] || c)}</h4><table class="res-table">
        <tr><th></th><th>Type</th><th>What counts</th><th>Sites</th></tr>
        ${r.types.filter((t) => (t.category || "other") === c).map((t) => `<tr>
          <td class="ic"><span class="res-ic" style="background:${esc(t.color || "#24384f")};color:${inkOn(t.color)}">${glyph(t, 20)}</span></td>
          <td class="nm"><b>${esc(t.name)}</b>${t.unit ? `<br><span class="muted">value in ${esc(t.unit)}</span>` : ""}</td>
          <td>${esc(t.description || "")}<br><span class="muted">Source: ${esc(srcName(t.source))}</span></td>
          <td class="num">${count.get(t.id) || 0}</td></tr>`).join("")}</table>`).join("")}`;
    },
    Sources: () => `
      ${h2("pedia", "📖", "Sources")}
      ${data.sources.map((s) => `
        <h4>${esc(s.title)}</h4>
        <p>${esc(s.description)}<br>
        <span class="muted">${esc(s.publisher)} · ${esc(s.license)}${s.vintage ? " · " + esc(s.vintage) : ""} ·
        <a href="${esc(s.homepage)}" target="_blank" rel="noopener">homepage</a></span></p>
        <table>${(s.files || []).map((f) => `<tr><td><code>${esc(f.url)}</code></td><td class="muted" style="white-space:nowrap">${esc((f.retrieved || "").slice(0, 10))}<br>${((f.bytes || 0) / 1e6).toFixed(1)} MB</td></tr>`).join("")}</table>`).join("")}`,
  };

  const show = (name) => {
    if (!pages[name]) name = "About this map";
    body.innerHTML = pages[name]();
    body.scrollTop = 0;
    nav.querySelectorAll("button").forEach((b) => {
      const on = b.dataset.page === name;
      b.classList.toggle("active", on);
      b.setAttribute("aria-current", on ? "page" : "false");
    });
  };
  nav.innerHTML = `<div class="hd">Almanac</div>` + Object.keys(pages).map((p) => `<button data-page="${esc(p)}">${esc(p)}</button>`).join("");
  nav.onclick = (e) => {
    const b = e.target.closest("button[data-page]");
    if (b) show(b.dataset.page);
  };
  const close = () => {
    if (modal.hidden) return;
    modal.hidden = true;
    if (restoreFocus && document.contains(restoreFocus)) restoreFocus.focus();
    restoreFocus = null;
  };
  modal.onclick = (e) => {
    if (e.target === modal || e.target.closest("[data-close]")) close();
  };
  // Keep Tab inside the dialog.
  modal.addEventListener("keydown", (e) => {
    if (e.key !== "Tab") return;
    const f = [...card.querySelectorAll("button, a[href], [tabindex]:not([tabindex='-1'])")].filter((x) => x.offsetParent);
    if (!f.length) return;
    const first = f[0], last = f[f.length - 1];
    if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
    else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
  });

  return {
    open(page = "About this map") {
      if (modal.hidden) restoreFocus = document.activeElement;
      show(page);
      modal.hidden = false;
      (nav.querySelector("button.active") || card.querySelector("[data-close]"))?.focus();
    },
    close,
    get isOpen() {
      return !modal.hidden;
    },
  };
}
