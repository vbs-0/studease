// Money is integer paise everywhere; it is only formatted here, at the edge.

/** Indian digit grouping: 12345678 -> "1,23,456.78". */
export function inr(paise: number | null | undefined, opts: { signed?: boolean } = {}): string {
  if (paise === null || paise === undefined) return "-";
  const negative = paise < 0;
  const abs = Math.abs(paise);
  const rupees = Math.floor(abs / 100);
  const frac = String(abs % 100).padStart(2, "0");
  const digits = String(rupees);
  const head = digits.slice(0, -3);
  const grouped = (head ? head.replace(/\B(?=(\d{2})+(?!\d))/g, ",") + "," : "") + digits.slice(-3);
  const sign = negative ? "-" : opts.signed && paise > 0 ? "+" : "";
  return `${sign}₹${grouped}.${frac}`;
}

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

/** "2026-09-05" -> "05 Sep 2026". Built by hand so the text never depends on the browser's locale data. */
export function shortDate(iso: string | null | undefined): string {
  if (!iso) return "-";
  const [y, m, d] = iso.slice(0, 10).split("-");
  return `${d} ${MONTHS[Number(m) - 1]} ${y}`;
}

export function label(code: string): string {
  return code.toLowerCase().replace(/_/g, " ").replace(/^./, (c) => c.toUpperCase());
}

/** Status -> stamp tone. */
export function tone(status: string): "ok" | "warn" | "bad" | "mute" {
  if (["PAID", "ALLOCATED", "RESOLVED", "ELIGIBLE", "APPLIED", "COMPLETED", "ENROLLED"].includes(status)) return "ok";
  if (["OVERDUE", "OPEN", "REVOKED", "INELIGIBLE"].includes(status)) return "bad";
  if (["PARTIALLY_PAID", "PARTIALLY_ALLOCATED", "APPROVED", "RECEIVED", "AWARDED", "ISSUED"].includes(status)) return "warn";
  return "mute";
}
