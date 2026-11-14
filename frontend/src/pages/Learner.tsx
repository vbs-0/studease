import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useNavigate } from "react-router";
import { Empty, ErrorBox, ExportMenu, Header, Metric, Money, PageLoading, Spinner, Stamp, toast } from "../components/ui";
import { get, post } from "../lib/api";
import { downloadCsv } from "../lib/export";
import { inr, label, shortDate } from "../lib/format";
import { usePage } from "../lib/page";

export function Enroll() {
  usePage("Enrol", "Enrol in a term: see the fees you will be billed, which scholarships you meet, and apply.");
  const qc = useQueryClient();
  const nav = useNavigate();
  const q = useQuery({ queryKey: ["enrollable"], queryFn: () => get("/me/enrollable") });
  const [pick, setPick] = useState<Record<string, string[]>>({});
  const m = useMutation({
    mutationFn: (termId: string) => post("/me/enroll", { term_id: termId, applications: pick[termId] ?? [] }),
    onSuccess: (r: any) => {
      for (const k of ["student", "ledger", "events", "enrollable", "overview"]) qc.invalidateQueries({ queryKey: [k] });
      toast(r.scholarship ? `Enrolled. ${label(r.scholarship.scheme_code)} awarded: ${inr(r.scholarship.amount_paise)}` : "Enrolled. Your invoice is ready.");
      nav("/me");
    },
  });
  if (q.isPending) return <PageLoading labels={["Term", "Fees", "Awards", "Total"]} rows={3} />;
  if (q.isError) return <ErrorBox error={q.error} retry={() => q.refetch()} />;
  const items = q.data.items;
  return (
    <>
      <Header title="Enrol" lead="Choose a term. You are billed the fees for your program, and each scheme you apply for is judged against its published criteria." />
      {items.length === 0 ? <Empty>There is no open term to enrol in: you are already enrolled in every term that is still running.</Empty> : items.map((o: any) => {
        const t = o.term, chosen = pick[t.term_id] ?? [];
        const toggle = (code: string) => setPick((p) => ({ ...p, [t.term_id]: chosen.includes(code) ? chosen.filter((c) => c !== code) : [...chosen, code] }));
        return (
          <div key={t.term_id} className="stack">
            <div className="grid-cards">
              <Metric kind="hero" title="Term" value={label(t.term_name)} note={`${shortDate(t.start_date)} to ${shortDate(t.end_date)}`} />
              <Metric kind="sand" title="Fees" value={inr(o.total_paise)} note={`${o.lines.length} lines, due ${shortDate(t.due_date)}`} />
              <Metric kind="ink" title="Scholarship-eligible fees" value={inr(o.eligible_fees_paise)} note="The base awards are calculated on" />
            </div>
            <section className="panel"><h2>What you will be billed</h2>
              <table className="register mt-2"><tbody>
                {o.lines.map((l: any) => <tr key={l.description}><td>{l.description}</td><td><Money paise={l.amount_paise} signed={l.amount_paise < 0} /></td></tr>)}
                <tr><td className="font-bold">Total</td><td><Money paise={o.total_paise} className="font-bold" /></td></tr>
              </tbody></table>
            </section>
            <section className="panel"><h2>Apply for scholarships</h2>
              <p className="note">Only the single largest award you qualify for is granted. Schemes you do not meet are shown with the reason.</p>
              <div className="mt-3 grid gap-2">
                {o.schemes.map((s: any) => (
                  <label key={s.scheme_code} className={`flex flex-wrap items-center gap-3 rounded-2xl border border-rule px-4 py-3 ${s.meets_criteria ? "cursor-pointer" : "opacity-60"}`}>
                    <input type="checkbox" checked={chosen.includes(s.scheme_code)} onChange={() => toggle(s.scheme_code)} disabled={!s.meets_criteria} />
                    <span className="font-semibold">{s.name}</span>
                    {s.meets_criteria ? <><span className="stamp stamp-ok">Meets criteria</span><span className="note m-0 ml-auto">worth up to {inr(s.would_award_paise)}</span></>
                      : <><span className="stamp stamp-mute">Not eligible</span><span className="note m-0 ml-auto">{label(s.reason)}</span></>}
                  </label>))}
              </div>
            </section>
            {m.isError && <ErrorBox error={m.error} />}
            <div><button className="btn btn-solid" disabled={m.isPending} onClick={() => m.mutate(t.term_id)}>{m.isPending && <Spinner />}Enrol in {label(t.term_name)} and generate my invoice</button></div>
          </div>);
      })}
    </>
  );
}

export function MyScholarships() {
  usePage("My scholarships", "Your scholarship awards and every eligibility decision with its reason.");
  const q = useQuery({ queryKey: ["my-scholarships"], queryFn: () => get("/me/scholarships") });
  if (q.isPending) return <PageLoading labels={["Awards", "Awarded", "Decisions", "Eligible"]} rows={3} />;
  if (q.isError) return <ErrorBox error={q.error} retry={() => q.refetch()} />;
  const { awards, decisions } = q.data;
  const total = awards.reduce((n: number, a: any) => n + a.amount_paise, 0);
  const csv = () => downloadCsv("my-scholarship-decisions", decisions, [
    { header: "Decided on", value: (d: any) => d.decided_on }, { header: "Scheme", value: (d: any) => d.scheme_name }, { header: "Decision", value: (d: any) => d.decision },
    { header: "Reason", value: (d: any) => d.reason_code }, { header: "GPA at decision", value: (d: any) => d.gpa_at_decision }]);
  return (
    <>
      <Header title="My scholarships" lead="Awards are capped at the scholarship-eligible fees. Each decision records the GPA and income band it was based on."><ExportMenu onCsv={csv} /></Header>
      <div className="grid-cards">
        <Metric kind="hero" title="Awards" value={awards.length} note="Currently held or applied" />
        <Metric kind="sand" title="Total awarded" value={inr(total)} />
        <Metric kind="ink" title="Decisions" value={decisions.length} note={`${decisions.filter((d: any) => d.decision === "ELIGIBLE").length} eligible`} />
      </div>
      <section className="panel mt-6"><h2>Awards</h2>
        {awards.length === 0 ? <p className="note">No awards yet. <Link to="/me/enroll">Enrol and apply</Link> to be considered.</p> : (
          <div className="scroll-x"><table className="register mt-2"><thead><tr><th>Award</th><th>Scheme</th><th>Invoice</th><th className="num">Eligible fees</th><th className="num">Awarded</th><th>Status</th></tr></thead><tbody>
            {awards.map((a: any) => <tr key={a.scholarship_id}><td>{a.scholarship_id}</td><td>{a.scheme_name}</td><td><Link to={`/invoices/${a.invoice_id}`}>{a.invoice_id}</Link></td><td><Money paise={a.eligible_fees_paise} /></td><td><Money paise={a.amount_paise} /></td><td><Stamp status={a.status} /></td></tr>)}
          </tbody></table></div>)}
      </section>
      <section className="panel mt-6"><h2>Every decision</h2>
        {decisions.length === 0 ? <p className="note">No applications yet.</p> : (
          <div className="scroll-x"><table className="register mt-2"><thead><tr><th>Date</th><th>Scheme</th><th>Decision</th><th>Reason</th><th className="num">GPA</th></tr></thead><tbody>
            {decisions.map((d: any) => <tr key={d.eligibility_id}><td>{shortDate(d.decided_on)}</td><td>{d.scheme_name}</td><td><Stamp status={d.decision} /></td><td>{label(d.reason_code)}</td><td className="num">{d.gpa_at_decision}</td></tr>)}
          </tbody></table></div>)}
      </section>
    </>
  );
}

export function MyFees() {
  usePage("Fee schedule", "The fees for your program in every term, with versions, dates and scholarship eligibility.");
  const q = useQuery({ queryKey: ["my-fees"], queryFn: () => get("/me/fees") });
  if (q.isPending) return <PageLoading labels={["Program", "Fees", "Terms", "Versions"]} rows={4} />;
  if (q.isError) return <ErrorBox error={q.error} retry={() => q.refetch()} />;
  const items = q.data.items;
  const terms = [...new Set(items.map((f: any) => f.term_name))] as string[];
  const csv = () => downloadCsv("my-fee-schedule", items, [
    { header: "Term", value: (f: any) => f.term_id }, { header: "Fee", value: (f: any) => f.fee_type }, { header: "Applies to", value: (f: any) => f.applies_to },
    { header: "Amount (paise)", value: (f: any) => f.amount_paise }, { header: "Version", value: (f: any) => f.version }, { header: "Effective from", value: (f: any) => f.effective_from }]);
  return (
    <>
      <Header title="Fee schedule" lead={`Fees for ${q.data.program_id}. Only the version in force on the invoice date is billed.`}><ExportMenu onCsv={csv} /></Header>
      <div className="stack">
        {terms.map((t) => (
          <section key={t} className="panel"><h2>{label(t)}</h2>
            <div className="scroll-x"><table className="register mt-2"><thead><tr><th>Fee</th><th>Applies to</th><th className="num">Amount</th><th className="num">Version</th><th>From</th><th>To</th><th>Scholarship</th></tr></thead><tbody>
              {items.filter((f: any) => f.term_name === t).map((f: any) => <tr key={f.fee_schedule_id}><td>{label(f.fee_type)}</td><td>{label(f.applies_to)}</td><td><Money paise={f.amount_paise} /></td><td className="num">{f.version}</td><td>{shortDate(f.effective_from)}</td><td>{shortDate(f.effective_to)}</td><td>{f.scholarship_eligible ? "Eligible" : "No"}</td></tr>)}
            </tbody></table></div>
          </section>))}
      </div>
    </>
  );
}
