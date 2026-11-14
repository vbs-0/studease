import { useInfiniteQuery, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router";
import { Empty, ErrorBox, ExportMenu, Header, Loading, Money, More, Stamp, toast } from "../components/ui";
import { downloadCsv, fetchAll } from "../lib/export";
import { get } from "../lib/api";
import { label, shortDate } from "../lib/format";
import { useAuth } from "../lib/auth";
import { NewFeeForm } from "./Admin";
import { Donut } from "../components/ui";
import { inr } from "../lib/format";
import { usePage } from "../lib/page";

export function Fees() {
  usePage("Fee schedules", "Fee schedules by program and term: tuition, lab, hostel and other fees, with versions and dates.");
  const programs = useQuery({ queryKey: ["programs"], queryFn: () => get("/programs") });
  const terms = useQuery({ queryKey: ["terms"], queryFn: () => get("/terms") });
  const { me } = useAuth();
  const [program, setProgram] = useState("PRG-01");
  const [term, setTerm] = useState("TERM-2026-FALL");
  const fees = useQuery({ queryKey: ["fees", program, term], queryFn: () => get("/fee-schedules", { program_id: program, term_id: term }) });
  return (
    <>
      <Header title="Fee schedules" lead="Every price carries a version and an effective date. Only the version in force on the issue date is billed.">
        <ExportMenu onCsv={() => downloadCsv(`fee-schedule-${program}-${term}`, fees.data?.items ?? [], [
          { header: "Fee schedule", value: (f: any) => f.fee_schedule_id }, { header: "Fee", value: (f: any) => f.fee_type }, { header: "Applies to", value: (f: any) => f.applies_to },
          { header: "Amount (paise)", value: (f: any) => f.amount_paise }, { header: "Version", value: (f: any) => f.version }, { header: "From", value: (f: any) => f.effective_from },
          { header: "To", value: (f: any) => f.effective_to }, { header: "Scholarship eligible", value: (f: any) => f.scholarship_eligible }])} />
      </Header>
      <div className="mb-4 flex flex-wrap gap-3">
        <select className="field max-w-xs" aria-label="Program" value={program} onChange={(e) => setProgram(e.target.value)}>
          {programs.data?.items.map((p: any) => <option key={p.program_id} value={p.program_id}>{p.program_id} {p.name}</option>)}</select>
        <select className="field max-w-[12rem]" aria-label="Term" value={term} onChange={(e) => setTerm(e.target.value)}>
          {terms.data?.items.map((t: any) => <option key={t.term_id} value={t.term_id}>{label(t.term_name)} {t.year}</option>)}</select>
      </div>
      {me && ["ACADEMIC_ADMIN", "PLATFORM_ADMIN"].includes(me.role) && <NewFeeForm program={program} term={term} />}
      {fees.isPending ? <Loading /> : fees.isError ? <ErrorBox error={fees.error} /> : fees.data.items.length === 0 ? <Empty>No fees for this program and term.</Empty> : (
        <div className="panel scroll-x"><table className="register"><thead><tr><th>Fee</th><th>Applies to</th><th className="num">Amount</th><th className="num">Version</th><th>From</th><th>To</th><th>Scholarship</th></tr></thead><tbody>
          {fees.data.items.map((f: any) => <tr key={f.fee_schedule_id}><td>{label(f.fee_type)}</td><td>{label(f.applies_to)}</td><td><Money paise={f.amount_paise} /></td><td className="num">{f.version}</td><td>{shortDate(f.effective_from)}</td><td>{shortDate(f.effective_to)}</td><td>{f.scholarship_eligible ? "Eligible" : "No"}</td></tr>)}
        </tbody></table></div>)}
    </>
  );
}

export function Scholarships() {
  usePage("Scholarships", "Scholarship schemes, awards and eligibility decisions with their reasons.");
  const schemes = useQuery({ queryKey: ["schemes"], queryFn: () => get("/scholarship-schemes") });
  const summary = useQuery({ queryKey: ["scholarship-summary"], queryFn: () => get("/scholarships/summary") });
  const [scheme, setScheme] = useState("");
  const [exporting, setExporting] = useState(false);
  const awards = useInfiniteQuery({
    queryKey: ["awards", scheme], initialPageParam: "" as string,
    queryFn: ({ pageParam }) => get("/scholarships", { after: pageParam, limit: 50, scheme_code: scheme }),
    getNextPageParam: (l: any) => l.next ?? undefined,
  });
  const rows = awards.data?.pages.flatMap((p: any) => p.items) ?? [];
  return (
    <>
      <Header title="Scholarships" lead="An award never exceeds the eligible fees. Ties between schemes go to the lowest priority number.">
        <ExportMenu busy={exporting} onCsv={async () => {
          setExporting(true);
          try {
            const all = await fetchAll("/scholarships", { scheme_code: scheme });
            downloadCsv("scholarship-awards", all, [
              { header: "Award", value: (a: any) => a.scholarship_id }, { header: "Student", value: (a: any) => a.student_id }, { header: "Scheme", value: (a: any) => a.scheme_code },
              { header: "Eligible fees (paise)", value: (a: any) => a.eligible_fees_paise }, { header: "Awarded (paise)", value: (a: any) => a.amount_paise }, { header: "Status", value: (a: any) => a.status }]);
            toast(`Exported ${all.length.toLocaleString("en-IN")} awards`);
          } finally { setExporting(false); }
        }} />
      </Header>
      <div className="two-col mb-6">
        <section className="panel"><h2>Awards by scheme</h2>
          {summary.isPending ? <Loading rows={3} /> : summary.isError ? <ErrorBox error={summary.error} /> : (
            <Donut slices={summary.data.items.filter((i: any) => i.awards > 0).map((i: any) => ({ label: i.name, value: i.awards }))} centre={summary.data.items.reduce((n: number, i: any) => n + i.awards, 0).toLocaleString("en-IN")} sub="awards" />)}
        </section>
        <section className="panel"><h2>Money awarded by scheme</h2>
          {summary.isPending ? <Loading rows={3} /> : summary.isError ? <ErrorBox error={summary.error} /> : (
            <Donut format={(n) => inr(n)} slices={summary.data.items.filter((i: any) => i.awarded_paise > 0).map((i: any) => ({ label: i.name, value: i.awarded_paise }))} centre={`${(summary.data.items.reduce((n: number, i: any) => n + i.awarded_paise, 0) / 1e7).toFixed(1)}Cr`} sub="awarded" />)}
        </section>
      </div>
      <section className="panel mb-6"><h2>Schemes</h2>
        {schemes.isPending ? <Loading /> : schemes.isError ? <ErrorBox error={schemes.error} /> : (
          <div className="scroll-x"><table className="register mt-2"><thead><tr><th>Priority</th><th>Scheme</th><th className="num">Min GPA</th><th>Income band</th><th>Award</th></tr></thead><tbody>
            {schemes.data.items.map((s: any) => <tr key={s.scheme_code}><td className="num">{s.priority}</td><td>{s.name}</td><td className="num">{s.min_gpa}</td><td>{s.required_income_band ?? "Any"}{s.requires_sports_quota ? ", sports quota" : ""}{s.requires_international ? ", international" : ""}</td><td>{s.award_type === "PERCENT" ? `${s.award_bp / 100}% of eligible fees` : <Money paise={s.award_fixed_paise} />}</td></tr>)}
          </tbody></table></div>)}
      </section>
      <div className="mb-3 flex flex-wrap items-center gap-3"><h2 className="serif m-0 text-3xl">Awards</h2>
        <select className="field max-w-xs" aria-label="Scheme" value={scheme} onChange={(e) => setScheme(e.target.value)}>
          <option value="">All schemes</option>{schemes.data?.items.map((s: any) => <option key={s.scheme_code} value={s.scheme_code}>{s.name}</option>)}</select></div>
      {awards.isPending ? <Loading rows={6} /> : awards.isError ? <ErrorBox error={awards.error} /> : (
        <div className="panel scroll-x"><table className="register"><thead><tr><th>Award</th><th>Student</th><th>Scheme</th><th className="num">Eligible fees</th><th className="num">Awarded</th><th>Status</th></tr></thead><tbody>
          {rows.map((a: any) => <tr key={a.scholarship_id}><td>{a.scholarship_id}</td><td><Link to={`/students/${a.student_id}`}>{a.student_id}</Link></td><td>{label(a.scheme_code)}</td><td><Money paise={a.eligible_fees_paise} /></td><td>{a.amount_paise > a.eligible_fees_paise ? <span className="strike-draw num">{(a.amount_paise / 100).toLocaleString("en-IN")}</span> : <Money paise={a.amount_paise} />}</td><td><Stamp status={a.status} /></td></tr>)}
        </tbody></table></div>)}
      <More next={awards.data?.pages.at(-1)?.next} onMore={() => awards.fetchNextPage()} busy={awards.isFetchingNextPage} />
    </>
  );
}
