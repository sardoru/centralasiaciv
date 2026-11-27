// The world map as the home page. index.html opts in with <html data-home="world">: the bare address then opens the
// world map (ext/ports), where any country can be picked, and each built-in edition lives at ?country=<id>
// (?country=us, ?country=ca). Pages without the attribute (the dev pages, a copy that hosts one edition) open on
// their default edition as before.
//
// With the opt-in, the page opens on the world map unless the address names a built-in edition or its hash carries
// an edition's state, so an old shared link such as /#city=35620&lens=income still opens the default edition. A
// ?country= that is not a built-in edition (?country=fr) opens the world map with that country picked.

import { EDITIONS } from "./edition-index.js";

const html = typeof document !== "undefined" ? document.documentElement : null;
export const WORLD_HOME = html?.dataset?.home === "world";

// Hash keys the world view owns (ext/ports): the open map ("all" or a map's id), the picked country, and the list of
// makers.
export const WORLD_HASH_KEYS = ["ports", "country", "makers"];

function decide() {
  if (!WORLD_HOME || typeof location === "undefined") return { world: false, pick: null };
  const requested = new URLSearchParams(location.search).get("country");
  if (requested && EDITIONS.some((edition) => edition.id === requested)) return { world: false, pick: null };
  const keys = [...new URLSearchParams(location.hash.replace(/^#/, "")).keys()];
  if (keys.some((k) => !WORLD_HASH_KEYS.includes(k))) return { world: false, pick: null };
  const pick = requested && /^[a-z]{2}$/i.test(requested) ? requested.toUpperCase() : null;
  return { world: true, pick };
}

const decision = decide();
/** True when this page load opens on the world map rather than an edition. */
export const OPENS_ON_WORLD = decision.world;
/** An ISO 3166 code from ?country= to pick on the world map (?country=fr), or null. */
export const REQUESTED_PICK = decision.pick;

/** The address of a built-in edition: ?country=<id>. Without WORLD_HOME the default edition needs no parameter. */
export function editionUrl(id, defaultId = null) {
  const target = new URL(location.href);
  if (!WORLD_HOME && id === defaultId) target.searchParams.delete("country");
  else target.searchParams.set("country", id);
  target.hash = "";
  return target.href;
}

/**
 * An edition opened from an old link without ?country= (/#city=…) writes its ?country= into the address, so that
 * reloading or sharing it stays on that edition once its hash empties out (the bare address is the world map).
 */
export function pinEditionInUrl(id) {
  if (!WORLD_HOME || typeof location === "undefined") return;
  const params = new URLSearchParams(location.search);
  if (params.get("country") === id) return;
  params.set("country", id);
  try {
    history.replaceState(history.state, "", `${location.pathname}?${params}${location.hash}`);
  } catch {
    /* some sandboxes forbid history writes */
  }
}

/**
 * Give search engines this view's own address: the site's address (index.html's og:url) for the world map, plus
 * ?country=<id> for an edition, as in editionUrl(). One HTML file serves every view, so it has no canonical link of
 * its own: a fixed one would call each edition a copy of the world map, and search engines may ignore a canonical
 * link that a script changes. Packaging lists the same addresses in sitemap.xml (pipeline/sitemap.py).
 */
export function declareCanonical(editionId = null, defaultId = null) {
  if (!html) return;
  let url;
  try {
    url = new URL(document.querySelector('meta[property="og:url"]')?.content);
  } catch {
    return; // no address declared (a copy of the site without social tags)
  }
  url.search = "";
  url.hash = "";
  if (editionId && (WORLD_HOME || editionId !== defaultId)) url.searchParams.set("country", editionId);
  let link = document.head.querySelector('link[rel="canonical"]');
  if (!link) {
    link = document.createElement("link");
    link.rel = "canonical";
    document.head.append(link);
  }
  link.href = url.href;
}
