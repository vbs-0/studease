import { useQuery } from "@tanstack/react-query";
import { Donut, ErrorBox, ExportMenu, Header, Metric, PageLoading, PillBar, TrendBars } from "../components/ui";
import { get } from "../lib/api";
import { useAuth } from "../lib/auth";
import { LineChart } from "../components/charts";
import { downloadCsv, downloadJson } from "../lib/export";
import { inr, label } from "../lib/format";
import { usePage } from "../lib/page";

export default function Overview() {
  usePage("Overview", "Headline tuition, collection and balance figures by term and program, with the open exceptions queue.");
  const { me } = useAuth();
  const q = useQuery({ queryKey: ["overview"], queryFn: () => get("/metrics/overview") });
  if (q.isPending) return <PageLoading labels={["Net billed", "Collected", "Owed by students", "Open exceptions"]} />;
  if (q.isError) return <ErrorBox error={q.error} retry={() => q.refetch()} />;
  const d = q.data;
  const billed = d.charged_paise + d.credits_paise;
  const collection = billed > 0 ? Math.round((d.paid_paise / billed) * 1000) / 10 : 0;
  const maxProg = Math.max(...d.by_program.map((p: any) => Math.abs(p.balance_paise)), 1);
  const slices = Object.entries(d.invoice_status).sort((a: any, b: any) => b[1] - a[1]).map(([s, n]: any) => ({ label: s, value: n }));
  const csv = () => downloadCsv("studease-overview-by-program", d.by_program, [
    { header: "Program", value: (r: any) => r.program_id }, { header: "Name", value: (r: any) => r.name },
    { header: "Students", value: (r: any) => r.students }, { header: "Balance (paise)", value: (r: any) => r.balance_paise }]);
  return (
    <>
      <Header title="Overview" lead={`The books as of ${d.as_of}. Money is held in integer paise and shown in rupees.`}>
        <ExportMenu onCsv={csv} onJson={() => downloadJson("studease-overview", d)} />
      </Header>
      <div className="grid-cards">
        <Metric kind="hero" title="Net billed" value={inr(billed)} note={`${inr(d.charged_paise)} charged, ${inr(-d.credits_paise)} credits`} />
        <Metric kind="sand" title="Collected" value={inr(d.paid_paise - d.refunded_paise)} note={`${collection}% of net billed, after ${inr(d.refunded_paise)} refunds`} />
        <Metric kind="ink" title="Owed by students" value={inr(d.owed_paise)} note={`${inr(d.credit_held_paise)} held as credit`} />
        <Metric kind="mint" title="Open exceptions" value={d.open_exceptions} note={me?.role === "ACADEMIC_ADMIN" ? "Awaiting support review" : "Awaiting review"} to={me?.role === "ACADEMIC_ADMIN" ? undefined : "/exceptions"} />
      </div>
      <section className="panel mt-6"><h2>Charged and collected by month</h2>
        <LineChart curve name="Monthly billing and collection" labels={d.by_month.map((m: any) => m.month)} format={(n) => `${(n / 1e7).toFixed(1)} Cr`}
          series={[{ name: "Charged", color: "#f75708", values: d.by_month.map((m: any) => m.charged_paise) }, { name: "Collected", color: "#1f9d6b", values: d.by_month.map((m: any) => m.paid_paise) },
            { name: "Refunded", color: "#d63a12", values: d.by_month.map((m: any) => m.refunded_paise) }]} />
      </section>
      <div className="two-col mt-6">
        <section className="panel"><h2>Invoices by status</h2>
          <Donut slices={slices} centre={d.invoices.toLocaleString("en-IN")} sub="invoices" />
        </section>
        <section className="panel"><h2>Net billed by term</h2>
          <TrendBars bars={d.by_term.map((t: any) => ({ label: label(t.term_name), value: t.net_billed_paise }))} format={(n) => `${(n / 1e7).toFixed(1)} Cr`} />
        </section>
        <section className="panel" style={{ gridColumn: "1 / -1" }}><h2>Open exceptions by type</h2>
          {Object.keys(d.open_by_type).length === 0 ? <p className="note">None open.</p> : (
            <div className="mt-3 grid gap-3">
              {Object.entries(d.open_by_type).map(([t, n]: any) => <PillBar key={t} text={label(t)} value={n} max={d.open_exceptions} display={n} red />)}
            </div>)}
        </section>
        <section className="panel" style={{ gridColumn: "1 / -1" }}><h2>Balance by program</h2>
          <div className="mt-3 grid gap-x-12 gap-y-3 md:grid-cols-2">
            {d.by_program.map((p: any) => <PillBar key={p.program_id} text={p.name} value={p.balance_paise} max={maxProg} display={inr(p.balance_paise)} red={p.balance_paise < 0} />)}
          </div>
        </section>
      </div>
    </>
  );
}
