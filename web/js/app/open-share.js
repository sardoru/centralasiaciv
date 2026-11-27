// A share page is a static document for crawlers. Open its map in the browser,
// restoring the city or lens from the page and the rest of the view from the link.
const target = new URL(document.getElementById("open-map").href);
for (const [key, value] of new URLSearchParams(location.search)) {
  if (key !== "country") target.searchParams.append(key, value);
}
const state = new URLSearchParams(location.hash.slice(1));
for (const [key, value] of new URLSearchParams(target.hash.slice(1))) state.set(key, value);
target.hash = state.toString();
location.replace(target.href);
