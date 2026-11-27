// index.html's entry point: the world map (when app/home.js says this page load opens on it) or an edition
// (main.js). The world map needs none of an edition's code or data, so it loads only its own.
import { OPENS_ON_WORLD, declareCanonical } from "./app/home.js";

if (OPENS_ON_WORLD) {
  declareCanonical(); // main.js declares an edition's
  import("./ext/ports/home.js")
    .then((m) => m.openWorldHome())
    .catch((err) => {
      // Without the world map, fall back to the default edition rather than a blank page.
      console.error("could not open the world map", err);
      import("./main.js");
    });
} else {
  import("./main.js");
}
