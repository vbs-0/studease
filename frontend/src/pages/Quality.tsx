import { useQuery } from "@tanstack/react-query";
import { Card, ErrorBox, Header, Loading } from "../components/ui";
import { get } from "../lib/api";
import { label } from "../lib/format";
import { usePage } from "../lib/page";

export default function Quality() {
  usePage("Data quality", "Validation results, anomaly detection precision and recall, and the reproducibility proof for the synthetic data.");
  const q = useQuery({ queryKey: ["quality"], queryFn: () => get("/quality") });
  if (q.isPending) return <Loading rows={6} />;
  if (q.isError) return <ErrorBox error={q.error} retry={() => q.refetch()} />;
  const { validation: v, evaluation: e, repro: r, scale } = q.data;
  const d = e?.detection;
  return (
    <>
      <Header title="Data quality" lead={`Reports for the ${scale} dataset, produced by the generator and the evaluation run, not by this page.`} />
      <div className="grid-cards reveal">
        <Card title="Validation" value={v ? (v.ok ? "Passed" : "Failed") : "-"} note={v ? `${v.labels} labelled cases, ${v.checks.reduce((n: number, c: any) => n + c.unexpected, 0)} unexpected violations` : "No report"} />
        <Card title="Reproducible" value={r ? (r.identical ? "Yes" : "No") : "-"} note={r ? `Two runs, ${r.total_rows?.toLocaleString("en-IN")} rows, identical checksums` : "No report"} />
        <Card title="Detection F1" value={d?.macro_f1 ?? "-"} note={d ? `precision ${d.overall.precision}, recall ${d.overall.recall}` : "No report"} />
        <Card title="Reconciliation rate" value={e ? `${(e.business.reconciliation_rate * 100).toFixed(1)}%` : "-"} note="Students whose three balances agree" />
      </div>
      {v && (
        <section className="panel mt-6"><h2 className="serif m-0 text-3xl">Validation checks</h2>
          <div className="scroll-x"><table className="register mt-2"><thead><tr><th>Check</th><th className="num">Rows</th><th className="num">Violations</th><th className="num">Explained by a label</th><th className="num">Unexpected</th></tr></thead><tbody>
            {v.checks.map((c: any) => <tr key={c.id}><td>{c.id} {c.name}</td><td className="num">{c.rows_checked.toLocaleString("en-IN")}</td><td className="num">{c.violations}</td><td className="num">{c.expected}</td><td className="num">{c.unexpected ? <span className="stamp stamp-bad">{c.unexpected}</span> : 0}</td></tr>)}
          </tbody></table></div></section>)}
      {d && (
        <section className="panel mt-6"><h2 className="serif m-0 text-3xl">Detection against ground truth</h2>
          <div className="scroll-x"><table className="register mt-2"><thead><tr><th>Anomaly</th><th className="num">Labelled</th><th className="num">Reported</th><th className="num">Precision</th><th className="num">Recall</th><th className="num">F1</th></tr></thead><tbody>
            {Object.entries(d.per_type).map(([k, t]: any) => <tr key={k}><td>{label(k)}</td><td className="num">{t.labelled}</td><td className="num">{t.reported}</td><td className="num">{t.precision}</td><td className="num">{t.recall}</td><td className="num">{t.f1}</td></tr>)}
          </tbody></table></div>
          <p className="mb-0 mt-3 text-sm text-muted">The detectors never see the ground truth, but they recompute the same rules the generator used, so a perfect score is expected by construction. It proves the rules are implemented consistently, not that they would find unknown faults in real data.</p>
        </section>)}
    </>
  );
}
