import { useQuery } from "@tanstack/react-query";
import { Bar, Card, ErrorBox, Header, Loading, Money } from "../components/ui";
import { get } from "../lib/api";
import { inr, label } from "../lib/format";
import { usePage } from "../lib/page";

export default function Overview() {
  usePage("Overview", "Headline tuition, collection and balance figures by term and program, with the open exceptions queue.");
  const q = useQuery({ queryKey: ["overview"], queryFn: () => get("/metrics/overview") });
  if (q.isPending) return <Loading rows={6} />;
  if (q.isError) return <ErrorBox error={q.error} retry={() => q.refetch()} />;
  const d = q.data;
  const billed = d.charged_paise + d.credits_paise;
  const collection = billed > 0 ? Math.round((d.paid_paise / billed) * 1000) / 10 : 0;
  const maxTerm = Math.max(...d.by_term.map((t: any) => t.net_billed_paise), 1);
  const maxProg = Math.max(...d.by_program.map((p: any) => Math.abs(p.balance_paise)), 1);
  return (
    <>
      <Header title="Overview" lead={`Figures as of ${d.as_of}. Money is held in integer paise and shown in rupees.`} />
      <div className="grid-cards reveal">
        <Card title="Students" value={d.students.toLocaleString("en-IN")} note={`${d.invoices.toLocaleString("en-IN")} invoices, ${d.payments.toLocaleString("en-IN")} payments`} to="/students" />
        <Card title="Net billed" value={inr(billed)} note={`${inr(d.charged_paise)} charged, ${inr(-d.credits_paise)} credits`} />
        <Card title="Collected" value={inr(d.paid_paise - d.refunded_paise)} note={`${collection}% of net billed, after ${inr(d.refunded_paise)} refunds`} />
        <Card title="Owed by students" value={inr(d.owed_paise)} note={`${inr(d.credit_held_paise)} held as credit`} />
        <Card title="Open exceptions" value={d.open_exceptions} note="Awaiting review" to="/exceptions" />
        <Card title="Scholarships" value={d.scholarships.toLocaleString("en-IN")} note="Awards this year" to="/scholarships" />
      </div>
      <div className="mt-8 grid gap-6 lg:grid-cols-2">
        <section className="panel"><h2 className="serif m-0 text-3xl">Invoices by status</h2>
          <div className="mt-3 grid gap-2">
            {Object.entries(d.invoice_status).sort((a: any, b: any) => b[1] - a[1]).map(([s, n]: any) => (
              <div key={s} className="grid grid-cols-[9rem_1fr_3.5rem] items-center gap-3 text-sm"><span>{label(s)}</span><Bar value={n} max={d.invoices} tone={s === "OVERDUE" ? "red" : "ink"} /><span className="num">{n}</span></div>
            ))}
          </div>
        </section>
        <section className="panel"><h2 className="serif m-0 text-3xl">Net billed by term</h2>
          <div className="mt-3 grid gap-2">
            {d.by_term.map((t: any) => (
              <div key={t.term_id} className="grid grid-cols-[6rem_1fr_8rem] items-center gap-3 text-sm"><span>{label(t.term_name)}</span><Bar value={t.net_billed_paise} max={maxTerm} /><Money paise={t.net_billed_paise} /></div>
            ))}
          </div>
        </section>
        <section className="panel"><h2 className="serif m-0 text-3xl">Open exceptions by type</h2>
          {Object.keys(d.open_by_type).length === 0 ? <p className="text-muted">None open.</p> : (
            <table className="register mt-2"><tbody>
              {Object.entries(d.open_by_type).map(([t, n]: any) => <tr key={t}><td>{label(t)}</td><td className="num">{n}</td></tr>)}
            </tbody></table>)}
        </section>
        <section className="panel"><h2 className="serif m-0 text-3xl">Balance by program</h2>
          <div className="mt-3 grid max-h-96 gap-2 overflow-y-auto">
            {d.by_program.map((p: any) => (
              <div key={p.program_id} className="grid grid-cols-[1fr_7rem] items-center gap-3 text-sm"><div><div className="truncate">{p.name}</div><Bar value={p.balance_paise} max={maxProg} tone={p.balance_paise < 0 ? "red" : "ink"} /></div><Money paise={p.balance_paise} /></div>
            ))}
          </div>
        </section>
      </div>
    </>
  );
}
