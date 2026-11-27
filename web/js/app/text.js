// The words that differ between editions (docs/EDITIONS.md). Each comes from the edition's manifest or its text pack
// (text.json), else from the neutral wording here, so an edition that supplies none still reads correctly.
//
// Text from an edition is data, never code: `txt()` returns plain text, to be escaped like any other data before it
// goes into HTML, and `rich()` returns HTML reduced to a few safe tags, with its {placeholders} filled by escaped
// values.
import { edition, EDITION_ID, TEXT } from "./edition.js";
import { esc } from "./escape.js";

// --- the nation's name in the forms sentences need ---------------------------------------------------------------
const name = edition.name;
/**
 * name: "United States"   code: "US" (tight labels: "×US")   short: "U.S." ("U.S. 6.8%")   vs: "US" ("▲ US 5.0%")
 * the: "the U.S." ("of the U.S.")   in: "in the U.S."   poss: "U.S." ("U.S. GDP", "U.S. mix")
 * the_poss: "the U.S." ("the U.S. share")   adj: "U.S." ("the U.S. share" as an adjective)
 */
export const NATION = {
  name, code: EDITION_ID.toUpperCase(), short: name, vs: name, the: name, in: `in ${name}`, poss: `${name}'s`,
  the_poss: `${name}'s`, adj: name, ...(edition.nation || {}),
};

// --- terms for the edition's places ----------------------------------------------------------------------------------
const DEFAULT_TERMS = {
  region: { one: "Region", many: "Regions", short: "Region", column: "Region" },
  division: { one: "division", many: "divisions", One: "Division", Many: "Divisions" },
  area: { one: "metro", many: "metros", areas: "metro areas", metro: "Metro", micro: "Micro" },
};
export const TERMS = Object.fromEntries(Object.entries(DEFAULT_TERMS).map(([k, v]) => [k, { ...v, ...(edition.terms?.[k] || {}) }]));

/** The edition's currency symbol ("$", "CA$") and its code in lower case ("usd", "cad"), the unit of money figures. */
export const CURRENCY = edition.currency?.symbol ?? "$";
export const CURRENCY_CODE = (edition.currency?.code ?? "USD").toLowerCase();

/** True when the edition labels each figure with its year (its figures come from different years). */
export const LABEL_YEARS = !!edition.label_years;
/** Display hints for the edition's map (manifest `view`). */
export const VIEW = edition.view || {};

// --- sentences --------------------------------------------------------------------------------------------------------
// Neutral wording for every key an edition may override in its text pack. Keep these free of any one country's
// agencies, tables and spellings.
const DEFAULTS = {};

const fill = (s, vars, enc) => (vars ? s.replace(/\{(\w+)\}/g, (m, k) => (k in vars ? enc(String(vars[k] ?? "")) : m)) : s);

/** True when the edition's text pack has its own wording for `key`. */
export const hasText = (key) => Object.prototype.hasOwnProperty.call(TEXT, key);

/** Plain text for `key`, its {placeholders} filled from `vars` (escape the result before putting it in HTML). */
export function txt(key, vars) {
  const s = hasText(key) ? TEXT[key] : DEFAULTS[key];
  if (s == null) {
    console.warn(`text: no wording for "${key}"`);
    return key;
  }
  return fill(String(s), vars, (v) => v);
}

// --- rich text: a few safe tags ----------------------------------------------------------------------------------------
const TAGS = new Set(["a", "abbr", "b", "br", "code", "em", "h3", "h4", "i", "kbd", "li", "ol", "p", "small", "span", "strong",
  "sub", "sup", "table", "tbody", "td", "th", "thead", "tr", "ul"]);
const ATTRS = new Set(["class", "title", "href", "target", "colspan", "rowspan"]);
const SAFE_HREF = /^(https:\/\/|http:\/\/|#|[a-z0-9_./-]+$)/i;
const richCache = new Map();

function clean(node, doc) {
  for (const child of [...node.childNodes]) {
    if (child.nodeType === 3) continue; // text
    if (child.nodeType !== 1) { child.remove(); continue; }
    const tag = child.tagName.toLowerCase();
    if (!TAGS.has(tag)) {
      if (tag === "script" || tag === "style" || tag === "template") { child.remove(); continue; }
      clean(child, doc);
      child.replaceWith(...child.childNodes); // keep the text of an unknown tag, drop the tag
      continue;
    }
    for (const a of [...child.attributes]) {
      const n = a.name.toLowerCase();
      if (!ATTRS.has(n) || (n === "href" && !SAFE_HREF.test(a.value.trim())) || (n === "target" && a.value !== "_blank")) child.removeAttribute(a.name);
    }
    if (tag === "a" && child.getAttribute("target") === "_blank") child.setAttribute("rel", "noopener");
    clean(child, doc);
  }
}

/** HTML for `key`, reduced to safe tags; {placeholders} are filled with escaped values from `vars`. */
export function rich(key, vars) {
  const tpl = hasText(key) ? TEXT[key] : DEFAULTS[key];
  if (tpl == null) {
    console.warn(`text: no wording for "${key}"`);
    return esc(key);
  }
  return richText(String(tpl), vars);
}

/** The same for a template string taken from the pack (a list entry, say). */
export function richText(tpl, vars) {
  if (!richCache.has(tpl)) {
    const doc = new DOMParser().parseFromString(`<body>${tpl}</body>`, "text/html");
    clean(doc.body, doc);
    richCache.set(tpl, doc.body.innerHTML);
  }
  return fill(richCache.get(tpl), vars, esc);
}

/** A list from the edition's text pack (`key` holding an array), else `fallback`. */
export const textList = (key, fallback = []) => (Array.isArray(TEXT[key]) ? TEXT[key] : fallback);

/** Registers neutral wording (used by modules for the keys they read; an edition's text pack overrides it). */
export function defaults(map) {
  for (const [k, v] of Object.entries(map)) if (!(k in DEFAULTS)) DEFAULTS[k] = v;
}
