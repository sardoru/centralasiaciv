// Keyboard & mouse cheat-sheet.
import { ANNOUNCEMENT_URL, ORIGINAL_URL } from "./project.js";
import { TERMS } from "./text.js";
import { icon } from "../ui/icon.js";

const isMac = /Mac|iPhone|iPad/.test(navigator.platform || navigator.userAgent || "");
const MOD = isMac ? "⌘" : "Ctrl";

const ROWS = [
  ["Move", [
    [["Drag", "←↑→↓", "WASD"], "Pan the map"],
    [["Scroll", "+", "–"], "Zoom in and out"],
    [["Double-click"], "Zoom in on a spot"],
    [["Two fingers"], "Pinch to zoom, drag to pan (touch)"],
    [["Minimap"], "Click or drag to jump"],
  ]],
  ["Explore", [
    [["Click city"], "Open the city screen"],
    [["Click land"], `Open that ${TERMS.region.one.toLowerCase()}`],
    [["/", `${MOD} K`], `Search cities and ${TERMS.region.many.toLowerCase()}`],
    [["L", "Shift L"], "Next / previous lens"],
    [["Legend"], "Hover or drag the scale to show only that range"],
    [["R"], "Show or hide resources"],
  ]],
  ["Panels", [
    [["?"], "This help"],
    [["Esc"], "Close help, search, Almanac, then the panel"],
  ]],
];

// Touch screens: the same sheet in finger terms. Mouse words become touch words, keyboard-only rows go, and the
// gestures a mouse does not have are added.
const TOUCH_KEYS = { "Click city": "Tap a city", "Click land": "Tap land", "Double-click": "Double-tap", Scroll: "Pinch",
  Drag: "Drag", Minimap: "Minimap", Legend: "Legend" };
const TOUCH_TEXT = { "Hover or drag the scale to show only that range": "Drag along the scale to show only that range",
  "Click or drag to jump": "Tap or drag to jump" };
const TOUCH_EXTRA = {
  Move: [[["Flick"], "Let the map glide on"]],
  Explore: [[["Tap a hex"], "With a lens on: show that hex's value"]],
  Panels: [[["Drag the handle"], "Pull a bottom sheet down to close it"]],
};
function touchRows(rows) {
  return rows.map(([title, list]) => {
    const out = [];
    for (const [keys, what] of list) {
      const k = keys.filter((key) => key in TOUCH_KEYS).map((key) => TOUCH_KEYS[key]);
      if (k.length) out.push([k, TOUCH_TEXT[what] || what]);
    }
    return [title, [...out, ...(TOUCH_EXTRA[title] || [])]];
  }).filter(([, list]) => list.length);
}

export function initHelp() {
  const modal = document.getElementById("help");
  if (!modal) return { open() {}, close() {}, get isOpen() { return false; } };
  const card = modal.querySelector(".help-card");
  let restore = null;
  card.innerHTML = `
    <button class="icon-btn help-close" data-close aria-label="Close help">${icon("close", "✕", { size: 13 })}</button>
    <h2 id="help-title">${icon("help", "?", { size: 22 })}<span>Controls</span></h2>
    <div class="help-cols">${(matchMedia("(hover: none)").matches ? touchRows(ROWS) : ROWS).map(([title, rows]) => `
      <section><h3>${title}</h3>${rows.map(([keys, what]) => `
        <div class="help-row"><span class="keys">${keys.map((k) => `<kbd>${k}</kbd>`).join("")}</span><span>${what}</span></div>`).join("")}
      </section>`).join("")}</div>
    <p class="help-foot">Every number traces back to public data: open the <b>Almanac</b> for sources.
      The link in the address bar always reopens this exact view.
      Source code: <a href="usaciv-source.zip" download>usaciv-source.zip</a> (MIT; run it with uv, see its README).
      Original project by Andrej Karpathy: <a href="${ORIGINAL_URL}" target="_blank" rel="noopener">karpathy.ai/usaciv</a>
      (<a href="${ANNOUNCEMENT_URL}" target="_blank" rel="noopener">announcement</a>); this copy adds the Canada edition.</p>`;

  const close = () => {
    if (modal.hidden) return;
    modal.hidden = true;
    if (restore && document.contains(restore)) restore.focus();
    restore = null;
  };
  modal.addEventListener("click", (e) => {
    if (e.target === modal || e.target.closest("[data-close]")) close();
  });
  modal.addEventListener("keydown", (e) => {
    if (e.key !== "Tab") return;
    e.preventDefault(); // the only focusable control is the close button
    card.querySelector("[data-close]").focus();
  });

  return {
    open() {
      if (!modal.hidden) return;
      restore = document.activeElement;
      modal.hidden = false;
      card.querySelector("[data-close]").focus();
    },
    close,
    toggle() { modal.hidden ? this.open() : close(); },
    get isOpen() { return !modal.hidden; },
  };
}
