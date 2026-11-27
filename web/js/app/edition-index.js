// The world map and edition pages share the index. Only an edition page loads its manifest and text.
export const DATA_URL = new URL("../../data/", import.meta.url);

export async function loadJSON(url) {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${url.pathname}: HTTP ${r.status}`);
  return r.json();
}

const index = await loadJSON(new URL("editions.json", DATA_URL));
/** The editions this site offers, in menu order: [{id, name, emblem}]. */
export const EDITIONS = index.editions;
const ids = EDITIONS.map((e) => e.id);
const html = typeof document !== "undefined" ? document.documentElement : null;
const declared = html?.dataset?.defaultEdition || html?.dataset?.defaultCountry;
export const DEFAULT_EDITION = ids.includes(declared) ? declared : ids.includes(index.default) ? index.default : ids[0];
