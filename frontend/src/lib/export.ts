// Client-side exports: CSV and JSON files from rows already in memory, and the browser's print dialog (Save as PDF).
import { get } from "./api";

export interface Column<T = any> { header: string; value: (row: T) => string | number | null | undefined }

function cell(v: string | number | null | undefined): string {
  const s = v === null || v === undefined ? "" : String(v);
  // a leading = + - @ would be run as a formula by spreadsheet programs; prefix it so it stays text
  const safe = /^[=+\-@\t\r]/.test(s) && Number.isNaN(Number(s)) ? `'${s}` : s;
  return /[",\n\r]/.test(safe) ? `"${safe.replace(/"/g, '""')}"` : safe;
}

export function toCsv<T>(rows: T[], columns: Column<T>[]): string {
  const lines = [columns.map((c) => cell(c.header)).join(",")];
  for (const r of rows) lines.push(columns.map((c) => cell(c.value(r))).join(","));
  return lines.join("\r\n") + "\r\n";
}

function save(name: string, text: string, type: string): void {
  const url = URL.createObjectURL(new Blob([text], { type }));
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export const downloadCsv = <T,>(name: string, rows: T[], columns: Column<T>[]) =>
  save(`${name}.csv`, "﻿" + toCsv(rows, columns), "text/csv;charset=utf-8");
export const downloadJson = (name: string, data: unknown) => save(`${name}.json`, JSON.stringify(data, null, 2), "application/json");
export const printPage = () => window.print();

/** Follow the keyset cursor until the list ends (200 rows per request), so an export is the whole list, not one page. */
export async function fetchAll<T = any>(path: string, query: Record<string, string | number | boolean | null | undefined> = {}, cap = 20000): Promise<T[]> {
  const out: T[] = [];
  let after: string | null = null;
  do {
    const page: { items: T[]; next: string | null } = await get(path, { ...query, limit: 200, after });
    out.push(...page.items);
    after = page.next;
  } while (after && out.length < cap);
  return out;
}

/** One invoice as a CSV file: a header block (who, when, status) then the lines and the total. */
export async function downloadInvoice(id: string): Promise<void> {
  const { invoice: inv, lines } = await get(`/invoices/${id}`);
  const head = [["Invoice", inv.invoice_id], ["Student", inv.student_id], ["Issued", inv.issue_date], ["Due", inv.due_date], ["Status", inv.status]].map((r) => r.map(cell).join(","));
  const body = toCsv(lines, [{ header: "Line", value: (l: any) => l.line_no }, { header: "Type", value: (l: any) => l.line_type }, { header: "Description", value: (l: any) => l.description },
    { header: "Amount (rupees)", value: (l: any) => (l.amount_paise / 100).toFixed(2) }]);
  const nl = "\r\n";
  save(`${id}.csv`, "\ufeff" + head.join(nl) + nl + nl + body + ["", "", "Total", (inv.total_paise / 100).toFixed(2)].map(cell).join(",") + nl, "text/csv;charset=utf-8");
}
