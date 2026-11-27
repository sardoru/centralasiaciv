// The map menu: the <select> at the top left that names the map on screen and lists every other one. An edition's top
// bar (main.js) and the bar above a community map (ext/ports) show the same menu, with the same entries in the same
// order. main.js fills it with the editions; ext/ports adds the world map and the community maps.

/** 🇩🇪 from "DE" (regional indicator letters; some systems show the two letters instead of a flag). */
export function flagEmoji(iso) {
  if (!/^[A-Z]{2}$/.test(iso || "")) return "🏳️";
  return String.fromCodePoint(...[...iso].map((ch) => 0x1f1e6 + ch.charCodeAt(0) - 65));
}

// A character that is drawn as an emoji by default, or one made into an emoji by a variation selector (☀️).
const EMOJI = /\p{Emoji_Presentation}|️/u;

// Whether this system draws flags. Windows has no flag emoji, so its browsers draw the two letters instead (Firefox
// brings its own flags). A flag has colours; the letters come out in the text colour alone.
let flagsDrawn = null;
function drawsFlags() {
  if (flagsDrawn !== null) return flagsDrawn;
  flagsDrawn = true; // where it cannot be tested (no canvas), a flag is assumed
  try {
    const canvas = document.createElement("canvas");
    canvas.width = canvas.height = 24;
    const ctx = canvas.getContext("2d", { willReadFrequently: true });
    ctx.font = "18px sans-serif";
    ctx.textBaseline = "top";
    ctx.fillStyle = "#000";
    ctx.fillText(flagEmoji("US"), 0, 2);
    const px = ctx.getImageData(0, 0, 24, 24).data;
    let coloured = false;
    for (let i = 0; i < px.length && !coloured; i += 4) {
      coloured = px[i + 3] > 32 && (Math.abs(px[i] - px[i + 1]) > 24 || Math.abs(px[i + 1] - px[i + 2]) > 24);
    }
    flagsDrawn = coloured;
  } catch {
    /* no canvas here */
  }
  return flagsDrawn;
}

/**
 * The icon that stands for a map beside its name, in a menu or a list: its emblem when that is an emoji, and its
 * country's flag when it is not. The U.S. edition's emblem is a plain star (★). On the round badge of its card and
 * its share images that is an emblem; at the start of a line of text it reads as no icon at all. Where flags are not
 * drawn the star stays, rather than the letters "US" before "United States".
 */
export function mapIcon(emblem, iso = null) {
  if (emblem && EMOJI.test(emblem)) return emblem;
  return /^[A-Z]{2}$/.test(iso || "") && drawsFlags() ? flagEmoji(iso) : emblem || "";
}

/** The icon of an edition as editions.json lists it ({id, name, emblem}): its id is its country's code. */
export const editionIcon = (edition) => mapIcon(edition.emblem, /^[a-z]{2}$/i.test(edition.id) ? edition.id.toUpperCase() : null);

/** What a map's entry in the menu says: its icon, then its name. */
export const menuLabel = (icon, name) => (icon ? `${icon} ${name}` : name);

/**
 * Give a menu the width of the entry it shows (a <select> is otherwise as wide as its longest entry) and return that
 * width in css px. The menu has to be on screen to be measured.
 */
export function fitMenu(select) {
  const sizer = document.createElement("span");
  sizer.className = "brand-sizer";
  sizer.textContent = select.selectedOptions[0]?.textContent || "";
  select.after(sizer);
  const cs = getComputedStyle(select);
  const extra = (parseFloat(cs.paddingLeft) || 0) + (parseFloat(cs.paddingRight) || 0)
    + (parseFloat(cs.borderLeftWidth) || 0) + (parseFloat(cs.borderRightWidth) || 0) + 4;
  const width = Math.ceil(sizer.getBoundingClientRect().width + extra);
  sizer.remove();
  select.style.width = `${width}px`;
  return width;
}
