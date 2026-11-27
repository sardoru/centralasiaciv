// Phones and touch screens. The top bar on phones (css/style.css, max-width 700px) is two fixed rows instead of one
// sideways-scrolling strip: the map menu, World, the maker's account, a search button and a menu (Advisors, Share,
// Help, Almanac and any extension buttons) on top, the national yields below. This wires the parts CSS cannot:
//  * the menu button and closing the menu;
//  * the search field's close button (the field opens over the first row while it has focus);
//  * dropping the word "World" and the map count, then the maker's name, when the first row is too narrow for them;
//  * the map's Home button;
//  * on iOS, stopping Safari from zooming the page into a text field or menu whose font is under 16 px.
import { icon } from "./icon.js";
import { fitMenu } from "./mapPicker.js";

const PHONE = "(max-width: 700px)";
// The first row's classes for a narrow screen: World without its word and its map count, the maker's name cut short
// or left out (css/ports.css).
const TIGHT = ["tb-tight", "tb-tight-count", "tb-cut-maker", "tb-tight-maker"];
const MAKER_MIN = 90; // px of chip: its picture and about 7 letters of the name
const MENU_SLACK = 3; // px the map menu gives up without cutting its name (fitMenu leaves it 4)
const MENU_SVG = `<svg class="icon" width="18" height="18" viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M4 6.5h16M4 12h16M4 17.5h16" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" fill="none"/></svg>`;
const HOME_SVG = `<svg class="icon" width="18" height="18" viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" fill="none"/><circle cx="12" cy="12" r="2.6" fill="currentColor"/></svg>`;

export function initMobile({ app } = {}) {
  const phone = matchMedia(PHONE);
  preventIosInputZoom();

  const bar = document.getElementById("topbar");
  if (!bar) return;

  // --- menu ------------------------------------------------------------------------------------------------------
  const menuBtn = document.getElementById("btn-menu");
  const menu = bar.querySelector(".tb-buttons");
  const help = document.getElementById("btn-help");
  // Help is an icon on desktop; the menu lists it by name.
  if (help && !help.querySelector(".lbl")) help.insertAdjacentHTML("beforeend", `<span class="lbl lbl-menu">Help</span>`);
  if (help && matchMedia("(hover: none)").matches) help.setAttribute("aria-label", "Help: touch controls");
  if (menuBtn && menu) {
    menuBtn.innerHTML = MENU_SVG;
    const setOpen = (open) => {
      bar.classList.toggle("menu-open", open);
      menuBtn.setAttribute("aria-expanded", String(open));
    };
    menuBtn.addEventListener("click", () => setOpen(!bar.classList.contains("menu-open")));
    // Choosing an item closes the menu (the item's own handler has already run).
    menu.addEventListener("click", (e) => {
      if (e.target.closest("button")) setOpen(false);
    });
    document.addEventListener("pointerdown", (e) => {
      if (bar.classList.contains("menu-open") && !e.target.closest(".tb-buttons, #btn-menu")) setOpen(false);
    }, true);
    document.addEventListener("keydown", (e) => {
      if (e.key !== "Escape" || !bar.classList.contains("menu-open")) return;
      e.stopPropagation();
      setOpen(false);
      menuBtn.focus();
    }, true);
    phone.addEventListener?.("change", () => setOpen(false));
  }

  // --- search ----------------------------------------------------------------------------------------------------
  const input = document.getElementById("search-input");
  const closeSearch = bar.querySelector(".search-close");
  if (input && closeSearch) {
    closeSearch.innerHTML = icon("close", "✕", { size: 12 });
    closeSearch.addEventListener("click", () => {
      if (input.value) {
        input.value = "";
        input.dispatchEvent(new Event("input"));
      }
      input.blur();
      closeSearch.blur();
    });
  }

  // --- first row: make room for the map name and maker ----------------------------------------------------------
  // Start with every label visible so the result depends on the available width, even when the map name is clipped.
  const switcher = bar.querySelector(".country-switcher");
  const searchBox = bar.querySelector(".search");
  function fitFirstRow() {
    if (!switcher) return;
    if (!phone.matches) {
      bar.classList.remove(...TIGHT);
      return;
    }
    // While the search field is open it covers the row (and a phone keyboard resizes the window): measure later.
    if (searchBox?.matches(":focus-within")) return;
    bar.classList.remove(...TIGHT);
    const mapMenu = switcher.querySelector(".map-picker");
    const world = switcher.querySelector(".ports-launch");
    const makerWidth = fullWidth(switcher.querySelector(".map-maker"));
    const inner = parseFloat(getComputedStyle(switcher).columnGap) || 0;
    const menuWidth = mapMenu ? fitMenu(mapMenu) : 0;
    const cs = getComputedStyle(bar);
    const gap = parseFloat(cs.columnGap) || 0;
    const avail = bar.clientWidth - (parseFloat(cs.paddingLeft) || 0) - (parseFloat(cs.paddingRight) || 0);
    let rest = gap; // the spacer between the switcher and Search takes a gap of its own
    for (const el of [searchBox, menuBtn]) if (el) rest += el.offsetWidth + gap;
    if (!world) return;
    // World gives up its word and its map count together. Then the maker's name is cut short, and where less than
    // MAKER_MIN would be left of the chip, it shows the maker's picture alone.
    const room = avail - rest - menuWidth - inner; // for World and the maker after it
    const makerNeeds = makerWidth ? inner + makerWidth : 0;
    if (world.offsetWidth + makerNeeds > room) bar.classList.add("tb-tight", "tb-tight-count");
    const makerRoom = room - world.offsetWidth - inner; // World measured again, as it now shows
    if (!makerWidth || makerRoom >= makerWidth - MENU_SLACK) return;
    bar.classList.add(makerRoom < Math.min(makerWidth, MAKER_MIN) ? "tb-tight-maker" : "tb-cut-maker");
  }
  // The maker's chip with its whole name (up to its max-width), however much of it the row shows now.
  function fullWidth(maker) {
    if (!maker?.offsetWidth) return 0;
    const label = maker.querySelector(".map-maker-label");
    const cap = parseFloat(getComputedStyle(maker).maxWidth) || Infinity;
    return Math.min(cap, maker.offsetWidth + (label ? label.scrollWidth - label.clientWidth : 0));
  }
  if (switcher) {
    // World and the maker arrive with ext/ports, after this has run, and take their size once the stylesheet loads.
    // Each part is watched as well as the switcher, which does not resize while the row holds it to the room there is.
    const refit = typeof ResizeObserver === "function" ? new ResizeObserver(() => fitFirstRow()) : null;
    const watched = new Set();
    const watchParts = () => {
      for (const el of [switcher, ...switcher.children]) {
        if (watched.has(el)) continue;
        watched.add(el);
        refit?.observe(el);
      }
      fitFirstRow();
    };
    if (typeof MutationObserver === "function") new MutationObserver(watchParts).observe(switcher, { childList: true });
    watchParts();
  }
  addEventListener("resize", fitFirstRow);
  searchBox?.addEventListener("focusout", () => requestAnimationFrame(fitFirstRow));
  document.fonts?.ready?.then(fitFirstRow);

  // --- map controls ----------------------------------------------------------------------------------------------
  const homeBtn = document.getElementById("btn-home");
  if (homeBtn) {
    homeBtn.innerHTML = HOME_SVG;
    homeBtn.addEventListener("click", () => app?.home?.());
  }
}

// Safari on iOS zooms the page into any focused text field or <select> whose font is under 16 px, and leaves it
// zoomed. maximum-scale=1 stops that; iOS still lets people pinch-zoom the page (it has ignored the limit for user
// zoom since iOS 10), so it is only added there: elsewhere it would turn pinch-zoom off. The world view (ext/ports)
// calls this too: on the home page no edition has, and the map menu above a community map is such a <select>.
export function preventIosInputZoom() {
  const ios = /iPhone|iPad|iPod/.test(navigator.userAgent) || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
  const meta = document.querySelector('meta[name="viewport"]');
  if (!ios || !meta || /maximum-scale/.test(meta.content)) return;
  meta.content += ", maximum-scale=1";
}
