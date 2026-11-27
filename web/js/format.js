import { CURRENCY, CURRENCY_CODE } from "./app/text.js";

export function compact(n) {
  if (n == null || Number.isNaN(n)) return "–";
  const a = Math.abs(n);
  if (a >= 1e12) return (n / 1e12).toFixed(a >= 1e13 ? 1 : 2) + "T";
  if (a >= 1e9) return (n / 1e9).toFixed(a >= 1e11 ? 0 : 1) + "B";
  if (a >= 1e6) return (n / 1e6).toFixed(a >= 1e8 ? 0 : 1) + "M";
  if (a >= 1e3) return (n / 1e3).toFixed(a >= 1e5 ? 0 : 1).replace(/\.0$/, "") + "K";
  return String(Math.round(n));
}

// Money is in the edition's currency (its manifest's `currency`). A money figure's unit is the currency code in lower
// case ("usd", "cad") or "money".
export { CURRENCY };
export const isMoney = (unit) => unit === "money" || unit === "usd" || unit === CURRENCY_CODE;
export const money = (n) => (n == null ? "–" : CURRENCY + compact(n));
export const dollars = (n) => (n == null ? "–" : CURRENCY + Math.round(n).toLocaleString("en-US"));
export const int = (n) => (n == null ? "–" : Math.round(n).toLocaleString("en-US"));
export const pct = (x, d = 1) => (x == null ? "–" : (x * 100).toFixed(d) + "%");

export function yieldValue(y, v) {
  return isMoney(y.unit) ? money(v) : compact(v);
}

export function popShort(n) {
  if (n >= 1e7) return Math.round(n / 1e6) + "M";
  if (n >= 1e6) return (n / 1e6).toFixed(1) + "M";
  return Math.round(n / 1e3) + "K";
}

export { esc } from "./app/escape.js";
