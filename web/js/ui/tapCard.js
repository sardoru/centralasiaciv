// Touch screens have no hover, so a tap on the map shows what the hover tooltip would (a tile's terrain, county, lens
// value and resources, or a map site) in a card just above whatever covers the bottom of the map (the lens dock and
// legend, or a bottom sheet), out from under the finger. main.js decides when a tap reads a tile instead of opening
// a state; the card can still open the state or city in one more tap.
import { esc } from "../format.js";
import { icon } from "./icon.js";

export function createTapCard({ onHide } = {}) {
  const el = document.createElement("div");
  el.id = "tap-card";
  el.className = "panel tap-card";
  el.hidden = true;
  el.setAttribute("role", "status");
  el.setAttribute("aria-live", "polite");
  document.body.appendChild(el);
  let action = null;

  el.addEventListener("click", (e) => {
    if (e.target.closest(".tc-close")) hide();
    else if (e.target.closest(".tc-open")) {
      const run = action;
      hide();
      run?.();
    }
  });

  // The card sits just above whatever covers the bottom of the map: the lens area's stack (dock, legend, map
  // controls) or a bottom sheet.
  function place() {
    const H = window.innerHeight;
    let edge = H;
    const consider = (c, anchored) => {
      if (c.hidden) return;
      const r = c.getBoundingClientRect();
      if (r.height > 0 && (!anchored || r.bottom >= H - 14) && r.top < edge) edge = r.top;
    };
    for (const c of document.querySelectorAll("#lens-area > *")) consider(c, false);
    for (const c of document.querySelectorAll("#city-panel, .app-dock")) consider(c, true);
    el.style.bottom = `${Math.round(H - edge + 8)}px`;
  }

  /**
   * html: the hover tooltip's content (built by ui/tooltip.js or a map layer's tooltip()), lines separated by <br>.
   * open: {label, run} for the button that opens the state or city, or null. key: the start of the line to put
   * first and larger (the lens value, "Born abroad:"), or null.
   */
  function show(html, { open = null, key = null } = {}) {
    action = open?.run || null;
    el.innerHTML = `<div class="tc-body">${html}</div>
      <button type="button" class="icon-btn tc-close" aria-label="Close">${icon("close", "✕", { size: 12 })}</button>
      ${open ? `<button type="button" class="tc-open">${esc(open.label)}<span aria-hidden="true">›</span></button>` : ""}`;
    const body = el.querySelector(".tc-body");
    // One element per line, so lines can be dropped or moved.
    const lines = [[]];
    for (const n of [...body.childNodes]) {
      if (n.nodeName === "BR") lines.push([]);
      else lines.at(-1).push(n);
    }
    body.textContent = "";
    for (const nodes of lines) {
      const text = nodes.map((n) => n.textContent).join("").trim();
      // The tooltip ends with a mouse hint ("Click to open …"); the button replaces it here.
      if (!nodes.length || /^Click to open\b/.test(text)) continue;
      const line = document.createElement("div");
      line.className = "tc-line";
      line.append(...nodes);
      if (key && text.includes(key)) { // after the lens icon, which may be an emoji
        line.classList.add("tc-key");
        body.prepend(line);
      } else body.append(line);
    }
    el.hidden = false;
    place();
  }

  function hide() {
    if (el.hidden) return;
    el.hidden = true;
    el.innerHTML = "";
    action = null;
    onHide?.();
  }

  addEventListener("resize", hide);
  return { show, hide, get shown() { return !el.hidden; } };
}
