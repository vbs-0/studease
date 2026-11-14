// Line chart: SVG only, no library. Lines draw themselves in, areas fade in, points grow on hover and carry a tooltip title.
import { useId } from "react";

export interface Series { name: string; color: string; values: number[] }

/** Monotone cubic (Fritsch-Carlson): smooth, and never dips or peaks beyond the data points. */
function smooth(pts: [number, number][]): string {
  const n = pts.length;
  if (n < 3) return pts.map((p, i) => `${i ? "L" : "M"}${p[0]},${p[1]}`).join(" ");
  const dx = pts.slice(1).map((p, i) => p[0] - pts[i][0]);
  const m = pts.slice(1).map((p, i) => (p[1] - pts[i][1]) / dx[i]);
  const t = [m[0], ...m.slice(1).map((v, i) => (m[i] * v <= 0 ? 0 : (m[i] + v) / 2)), m[n - 2]];
  for (let i = 0; i < n - 1; i++) {
    if (m[i] === 0) { t[i] = 0; t[i + 1] = 0; continue; }
    const a = t[i] / m[i], b = t[i + 1] / m[i], h = Math.hypot(a, b);
    if (h > 3) { t[i] = (3 * a * m[i]) / h; t[i + 1] = (3 * b * m[i]) / h; }
  }
  let d = `M${pts[0][0]},${pts[0][1]}`;
  for (let i = 0; i < n - 1; i++) d += ` C${pts[i][0] + dx[i] / 3},${pts[i][1] + (t[i] * dx[i]) / 3} ${pts[i + 1][0] - dx[i] / 3},${pts[i + 1][1] - (t[i + 1] * dx[i]) / 3} ${pts[i + 1][0]},${pts[i + 1][1]}`;
  return d;
}

export function LineChart({ labels, series, format, height = 280, name, tips, dotColor, curve = false, width = 1200 }: { labels: string[]; series: Series[]; format: (n: number) => string; height?: number; name: string; tips?: string[]; dotColor?: (i: number) => string; curve?: boolean; width?: number }) {
  const uid = useId().replace(/:/g, "");
  const W = width, L = 8, R = 8, T = 14, B = 30;
  const all = series.flatMap((s) => s.values);
  const lo = Math.min(0, ...all), hi = Math.max(1, ...all);
  const n = labels.length;
  const x = (i: number) => L + (n <= 1 ? (W - L - R) / 2 : (i * (W - L - R)) / (n - 1));
  const y = (v: number) => T + (1 - (v - lo) / (hi - lo || 1)) * (height - T - B);
  const step = Math.max(1, Math.ceil(n / 7));
  return (
    <div>
      <svg viewBox={`0 0 ${W} ${height}`} className="w-full" role="img" aria-label={`${name}: ${series.map((s) => s.name).join(" and ")} over ${n} points`}>
        <defs>{series.map((s, k) => (
          <linearGradient key={s.name} id={`${uid}${k}`} x1="0" x2="0" y1="0" y2="1"><stop offset="0" stopColor={s.color} stopOpacity=".32" /><stop offset="1" stopColor={s.color} stopOpacity="0" /></linearGradient>))}</defs>
        {[0, 1, 2, 3].map((g) => { const gy = T + (g * (height - T - B)) / 3; return <line key={g} x1={L} x2={W - R} y1={gy} y2={gy} stroke="var(--rule)" strokeDasharray="3 5" />; })}
        {lo < 0 && <line x1={L} x2={W - R} y1={y(0)} y2={y(0)} stroke="var(--rule-strong)" />}
        {series.map((s, k) => {
          const pts = s.values.map((v, i) => [x(i), y(v)] as [number, number]);
          const d = curve ? smooth(pts) : pts.map((p, i) => `${i ? "L" : "M"}${p[0]},${p[1]}`).join(" ");
          return (
            <g key={s.name}>
              {pts.length > 1 && <path className="line-area" d={`${d} L${pts.at(-1)![0]},${y(Math.max(lo, 0))} L${pts[0][0]},${y(Math.max(lo, 0))} Z`} fill={`url(#${uid}${k})`} style={{ animationDelay: `${k * 200 + 500}ms` }} />}
              <path className="line-path" d={d} pathLength={1} fill="none" stroke={s.color} strokeWidth="2.25" strokeLinecap="round" strokeLinejoin="round" style={{ animationDelay: `${k * 200}ms` }} />
              {n <= 24 && pts.map((p, i) => (
                <circle key={i} className="line-dot" cx={p[0]} cy={p[1]} r="3.5" fill={dotColor ? dotColor(i) : "var(--sheet)"} stroke={dotColor ? "var(--sheet)" : s.color} strokeWidth="2" style={{ animationDelay: `${600 + i * 40}ms` }}>
                  <title>{tips?.[i] ?? `${s.name}, ${labels[i]}: ${format(s.values[i])}`}</title></circle>))}
            </g>);
        })}
        {labels.map((t, i) => i % step === 0 || i === n - 1 ? <text key={i} x={x(i)} y={height - 8} textAnchor={i === 0 ? "start" : i === n - 1 ? "end" : "middle"} fontSize="13" fill="var(--muted)">{t}</text> : null)}
        <text x={L} y={T - 3} fontSize="12" fill="var(--muted)">{format(hi)}</text>
        {lo < 0 && <text x={W - R} y={y(0) - 4} textAnchor="end" fontSize="12" fill="var(--muted)">{format(0)} (settled)</text>}
        {lo < 0 && <text x={L} y={height - B - 4} fontSize="12" fill="var(--muted)">{format(lo)}</text>}
      </svg>
      <div className="legend mt-1">{series.map((s) => <span key={s.name}><i style={{ background: s.color }} />{s.name}</span>)}</div>
    </div>
  );
}
