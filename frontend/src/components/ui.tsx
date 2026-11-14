import { useIsFetching, useIsMutating } from "@tanstack/react-query";
import { Download, FileJson, Printer } from "lucide-react";
import { useEffect, useState, type ReactNode } from "react";
import { Link } from "react-router";
import { ApiError } from "../lib/api";
import { inr, label, tone } from "../lib/format";

export function Logo({ size = 30 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 64 64" role="img" aria-label="StudEase">
      <rect width="64" height="64" rx="14" fill="currentColor" />
      <path d="M14 20h36M14 32h36M14 44h24" stroke="var(--paper)" strokeWidth="3" strokeLinecap="round" />
      <path d="M10 14v36" stroke="#d63a12" strokeWidth="3" strokeLinecap="round" />
      <path d="M20 50 52 14" stroke="#f75708" strokeWidth="5" strokeLinecap="round" />
    </svg>
  );
}

export function Stamp({ status }: { status: string }) {
  return <span className={`stamp stamp-${tone(status)}`}>{label(status)}</span>;
}

export function Money({ paise, signed, className = "" }: { paise: number | null | undefined; signed?: boolean; className?: string }) {
  return <span className={`num ${className}`}>{inr(paise, { signed })}</span>;
}

export function Header({ title, lead, children }: { title: string; lead?: string; children?: ReactNode }) {
  return (
    <header className="vx-title">
      <div>
        <h1>{title}</h1>
        {lead && <p>{lead}</p>}
      </div>
      {children && <div className="no-print flex flex-wrap items-center gap-2">{children}</div>}
    </header>
  );
}

/* ------------------------------------------------------------------ metric cards */
type Kind = "hero" | "sand" | "ink" | "mint";
const CLASS: Record<Kind, string> = { hero: "hero-card", sand: "stat-card", ink: "stat-card ink", mint: "mint-card" };

export function Metric({ kind = "sand", title, value, note, to }: { kind?: Kind; title: string; value: ReactNode; note?: ReactNode; to?: string }) {
  const body = (
    <>
      <p className="eyebrow">{title}</p>
      <div className="big">{value}</div>
      {note && <p className="note">{note}</p>}
    </>
  );
  return to ? <Link to={to} className={`${CLASS[kind]} block no-underline text-inherit`}>{body}</Link> : <div className={CLASS[kind]}>{body}</div>;
}
export const Card = Metric;

/* ------------------------------------------------------------------ loading */
const SK: Kind[] = ["hero", "sand", "ink", "mint"];
/** Skeleton cards carry the real shapes and labels of the cards that replace them, so the swap is seamless. */
export function CardsSkeleton({ labels }: { labels: string[] }) {
  return (
    <div className="grid-cards" role="status" aria-label="Loading figures">
      {labels.map((t, i) => (
        <div key={t} className={`sk-card ${CLASS[SK[i % 4]]} sk-${SK[i % 4]}`} style={{ animationDelay: `${i * 70}ms` }}>
          <p className="eyebrow">{t}</p><div className="sk-num" /><div className="sk-line" /><div className="sk-line short" />
        </div>
      ))}
    </div>
  );
}

export function Loading({ rows = 4 }: { rows?: number }) {
  return (
    <div role="status" aria-label="Loading" className="grid gap-2">
      {Array.from({ length: rows }, (_, i) => <div key={i} className="skeleton h-10" style={{ opacity: 1 - i * 0.08 }} />)}
    </div>
  );
}

export function PageLoading({ labels = ["Students", "Billed", "Collected", "Owed"], rows = 5 }: { labels?: string[]; rows?: number }) {
  return <div className="stack"><CardsSkeleton labels={labels} /><div className="panel"><Loading rows={rows} /></div></div>;
}

export function Spinner() { return <span className="spinner" aria-hidden="true" />; }

/** A thin orange bar at the top of the window while any request is running. */
export function TopBar() {
  const busy = useIsFetching() + useIsMutating() > 0;
  const [on, setOn] = useState(false);
  useEffect(() => {
    if (busy) { const t = setTimeout(() => setOn(true), 120); return () => clearTimeout(t); }
    setOn(false);
  }, [busy]);
  return <div className={`topbar ${on ? "on" : ""}`} aria-hidden="true" />;
}

export function Splash() {
  return (
    <div className="splash" role="status" aria-label="Loading StudEase">
      <span className="splash-logo"><Logo size={72} /></span>
      <p className="m-0 text-sm font-bold tracking-[.2em]">STUDEASE</p>
      <span className="splash-bar" />
    </div>
  );
}

/* ------------------------------------------------------------------ states */
export function ErrorBox({ error, retry }: { error: unknown; retry?: () => void }) {
  const e = error instanceof ApiError ? error : null;
  return (
    <div role="alert" className="panel" style={{ borderColor: "var(--red)" }}>
      <p className="m-0 font-semibold text-red">{e?.message ?? "Something went wrong."}</p>
      {e?.requestId && <p className="note">Request id {e.requestId}</p>}
      {retry && <button className="btn mt-3" onClick={retry}>Try again</button>}
    </div>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return <p className="panel m-0 text-muted">{children}</p>;
}

export function More({ next, onMore, busy }: { next: string | null | undefined; onMore: () => void; busy?: boolean }) {
  return next ? <div className="mt-4 text-center"><button className="btn" onClick={onMore} disabled={busy}>{busy ? <Spinner /> : null}Load more</button></div> : null;
}

/* ------------------------------------------------------------------ charts */
export function PillBar({ text, value, max, display, red }: { text: string; value: number; max: number; display: ReactNode; red?: boolean }) {
  const pct = max > 0 ? Math.max(2, Math.round((Math.abs(value) / max) * 100)) : 0;
  return (
    <div className="row-bar grid grid-cols-[minmax(6rem,10rem)_1fr_auto] items-center gap-3 text-sm">
      <span className="truncate">{text}</span>
      <div className={`bar-pill ${red ? "red" : ""}`}><div style={{ width: `${pct}%` }} /></div>
      <span className="num min-w-[3.5rem]">{display}</span>
    </div>
  );
}

const PALETTE = ["var(--orange)", "var(--ink)", "#c9c0ab", "var(--green)", "var(--red)", "#7a766a"];

export function Donut({ slices, centre, sub }: { slices: { label: string; value: number }[]; centre: ReactNode; sub: string }) {
  const total = slices.reduce((n, s) => n + s.value, 0) || 1;
  const r = 70, c = 2 * Math.PI * r;
  let offset = 0;
  return (
    <div className="flex flex-wrap items-center gap-6">
      <svg viewBox="0 0 200 200" width="200" height="200" role="img" aria-label={`${sub}: ${slices.map((s) => `${label(s.label)} ${s.value}`).join(", ")}`}>
        <g transform="rotate(-90 100 100)">
          {slices.map((s, i) => {
            const len = (s.value / total) * c;
            const el = <circle key={s.label} className="donut-slice" cx="100" cy="100" r={r} strokeWidth="14" stroke={PALETTE[i % PALETTE.length]}
              strokeDasharray={`${Math.max(0, len - 2)} ${c}`} strokeDashoffset={-offset} style={{ animationDelay: `${i * 120}ms` }}><title>{label(s.label)}: {s.value}</title></circle>;
            offset += len;
            return el;
          })}
        </g>
        <text x="100" y="104" textAnchor="middle" className="donut-centre" fontSize="34" fill="currentColor">{centre}</text>
        <text x="100" y="126" textAnchor="middle" fontSize="11" fill="var(--muted)" letterSpacing="1.5">{sub.toUpperCase()}</text>
      </svg>
      <div className="legend flex-col !flex-nowrap">
        {slices.map((s, i) => <span key={s.label}><i style={{ background: PALETTE[i % PALETTE.length] }} />{label(s.label)} <b className="text-ink">{s.value}</b></span>)}
      </div>
    </div>
  );
}

export function TrendBars({ bars, format }: { bars: { label: string; value: number }[]; format: (n: number) => string }) {
  const max = Math.max(...bars.map((b) => b.value), 1);
  const w = 100 / bars.length;
  return (
    <svg viewBox="0 0 400 190" className="w-full" role="img" aria-label="Net billed by term">
      {bars.map((b, i) => {
        const h = Math.max(4, (b.value / max) * 130);
        const x = i * (400 / bars.length) + 20;
        return (
          <g key={b.label} tabIndex={0}>
            <rect className="trend-bar" x={x} y={150 - h} width={400 / bars.length - 40} height={h} rx="10" style={{ animationDelay: `${i * 120}ms` }}><title>{b.label}: {format(b.value)}</title></rect>
            <text x={x + (400 / bars.length - 40) / 2} y="172" textAnchor="middle" fontSize="12" fill="var(--muted)">{b.label}</text>
            <text x={x + (400 / bars.length - 40) / 2} y={144 - h} textAnchor="middle" fontSize="12" fontWeight="700" fill="currentColor">{format(b.value)}</text>
          </g>
        );
      })}
      <line x1="10" x2="390" y1="150" y2="150" stroke="var(--rule-strong)" />
      <desc>{w}</desc>
    </svg>
  );
}

/* ------------------------------------------------------------------ export */
export function ExportMenu({ onCsv, onJson, print = true, busy }: { onCsv?: () => void; onJson?: () => void; print?: boolean; busy?: boolean }) {
  return (
    <div className="flex flex-wrap gap-2" role="group" aria-label="Export">
      {onCsv && <button className="btn" onClick={onCsv} disabled={busy}>{busy ? <Spinner /> : <Download size={15} aria-hidden />}CSV</button>}
      {onJson && <button className="btn" onClick={onJson} disabled={busy}><FileJson size={15} aria-hidden />JSON</button>}
      {print && <button className="btn" onClick={() => window.print()}><Printer size={15} aria-hidden />Print / PDF</button>}
    </div>
  );
}

/* ------------------------------------------------------------------ toast */
export function toast(message: string): void { window.dispatchEvent(new CustomEvent("studease-toast", { detail: message })); }

export function Toaster() {
  const [msg, setMsg] = useState<string | null>(null);
  useEffect(() => {
    let timer = 0;
    const on = (e: Event) => { setMsg((e as CustomEvent<string>).detail); clearTimeout(timer); timer = window.setTimeout(() => setMsg(null), 4000); };
    window.addEventListener("studease-toast", on);
    return () => { window.removeEventListener("studease-toast", on); clearTimeout(timer); };
  }, []);
  return msg ? <div className="toast" role="status">{msg}</div> : null;
}
