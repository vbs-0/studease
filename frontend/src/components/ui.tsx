import type { ReactNode } from "react";
import { Link } from "react-router";
import { ApiError } from "../lib/api";
import { inr, label, tone } from "../lib/format";

export function Stamp({ status }: { status: string }) {
  return <span className={`stamp stamp-${tone(status)}`}>{label(status)}</span>;
}

export function Money({ paise, signed, className = "" }: { paise: number | null | undefined; signed?: boolean; className?: string }) {
  return <span className={`num ${className}`}>{inr(paise, { signed })}</span>;
}

export function Header({ title, lead, children }: { title: string; lead?: string; children?: ReactNode }) {
  return (
    <header className="mb-6 flex flex-wrap items-end justify-between gap-3">
      <div className="margin-rule">
        <h1 className="display">{title}</h1>
        {lead && <p className="max-w-2xl text-muted m-0">{lead}</p>}
      </div>
      {children}
    </header>
  );
}

export function Loading({ rows = 4 }: { rows?: number }) {
  return (
    <div role="status" aria-label="Loading" className="grid gap-2">
      {Array.from({ length: rows }, (_, i) => <div key={i} className="skeleton h-9" />)}
    </div>
  );
}

export function ErrorBox({ error, retry }: { error: unknown; retry?: () => void }) {
  const e = error instanceof ApiError ? error : null;
  return (
    <div role="alert" className="panel border-red">
      <p className="m-0 font-semibold text-red">{e?.message ?? "Something went wrong."}</p>
      {e?.requestId && <p className="m-0 mt-1 text-sm text-muted">Request id {e.requestId}</p>}
      {retry && <button className="btn mt-3" onClick={retry}>Try again</button>}
    </div>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return <p className="panel m-0 text-muted">{children}</p>;
}

export function Spinner() { return <span className="spinner" aria-hidden="true" />; }

export function Card({ title, value, note, to }: { title: string; value: ReactNode; note?: ReactNode; to?: string }) {
  const body = (
    <div className="panel h-full">
      <div className="eyebrow">{title}</div>
      <div className="big mt-1">{value}</div>
      {note && <div className="mt-1 text-sm text-muted">{note}</div>}
    </div>
  );
  return to ? <Link to={to} className="no-underline text-inherit">{body}</Link> : body;
}

export function Bar({ value, max, tone = "ink" }: { value: number; max: number; tone?: "ink" | "red" }) {
  const pct = max > 0 ? Math.max(2, Math.round((Math.abs(value) / max) * 100)) : 0;
  return (
    <div className="h-2 w-full" style={{ background: "var(--track)" }} aria-hidden="true">
      <div className="bar-grow h-2" style={{ width: `${pct}%`, background: tone === "red" ? "var(--red)" : "var(--ink)" }} />
    </div>
  );
}

export function More({ next, onMore, busy }: { next: string | null | undefined; onMore: () => void; busy?: boolean }) {
  return next ? <div className="mt-3 text-center"><button className="btn" onClick={onMore} disabled={busy}>{busy ? <Spinner /> : null}Load more</button></div> : null;
}
