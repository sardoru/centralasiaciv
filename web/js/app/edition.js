// The edition this page shows (docs/EDITIONS.md): its manifest, loaded before any module that imports this one runs
// (top-level await), so modules may read it while they load.
//
// `?country=<id>` picks an edition. Without it the page's own default applies (<html data-default-edition="…">, or
// the older data-default-country), then the index's default. All data addresses resolve from this module's own
// address, so the dev pages under web/dev/ load the same files as the site.

import { DATA_URL, DEFAULT_EDITION, EDITIONS, loadJSON } from "./edition-index.js";

export { DATA_URL, DEFAULT_EDITION, EDITIONS };
const ids = EDITIONS.map((e) => e.id);
const requested = typeof location !== "undefined" ? new URLSearchParams(location.search).get("country") : null;
/** The id of the edition on this page. */
export const EDITION_ID = ids.includes(requested) ? requested : DEFAULT_EDITION;
/** Where this edition's data files live. */
export const EDITION_URL = new URL(`${EDITION_ID}/`, DATA_URL);
/** The edition's manifest (web/data/<id>/edition.json). */
export const edition = await loadJSON(new URL("edition.json", EDITION_URL));
/** The edition's text pack (its manifest's `text` file): {key: text}. Read through app/text.js. */
export const TEXT = edition.text ? await loadJSON(new URL(edition.text, EDITION_URL)) : {};

const files = new Set(edition.files || []);
/** True when the manifest declares the data file `name` (without .json). Undeclared files are never requested. */
export const declares = (name) => files.has(name);
/** The address of one of this edition's data files. */
export const dataURL = (name) => new URL(`${name}.json`, EDITION_URL);
