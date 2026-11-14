import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Download } from "lucide-react";
import { useState, type FormEvent } from "react";
import { Link, Navigate, useParams } from "react-router";
import { LineChart } from "../components/charts";
import { AssignScholarship, ProfileForm } from "./Admin";
import { Donut, Empty, ErrorBox, ExportMenu, Header, Loading, Metric, Money, PageLoading, Spinner, Stamp, toast } from "../components/ui";
import { get, post } from "../lib/api";
import { useAuth } from "../lib/auth";
import { downloadCsv, downloadInvoice, downloadJson } from "../lib/export";
import { inr, label, shortDate } from "../lib/format";
import { usePage } from "../lib/page";

const KINDS: [string, string[]][] = [["Charged", ["CHARGE", "LATE_FEE"]], ["Paid", ["PAYMENT"]], ["Awards and waivers", ["SCHOLARSHIP", "WAIVER"]], ["Refunded", ["REFUND"]], ["Adjustments", ["ADJUSTMENT"]]];

export function MyAccount() {
  const { me } = useAuth();
  return me?.student_id ? <StudentPage id={me.student_id} /> : <Navigate to="/" replace />;
}

export default function StudentRoute() {
  const { id = "" } = useParams();
  return <StudentPage id={id} />;
}

function Balance({ b }: { b: any }) {
  const ok = b.reconciled;
  return (
    <section className="panel">
      <div className="flex flex-wrap items-center justify-between gap-2"><h2>Three routes to one number</h2>
        <span className={`stamp ${ok ? "stamp-ok" : "stamp-bad"}`}>{ok ? "Reconciled" : "Does not reconcile"}</span></div>
      <table className="register mt-2"><tbody>
        <tr><td>Stated balance</td><td><Money paise={b.stated} /></td></tr>
        <tr><td>Sum of ledger entries</td><td>{b.ledger === b.stated ? <Money paise={b.ledger} /> : <span className="strike-draw num">{inr(b.ledger)}</span>}</td></tr>
        <tr><td>Invoices minus payments plus refunds</td><td>{b.from_documents === b.stated ? <Money paise={b.from_documents} /> : <span className="strike-draw num">{inr(b.from_documents)}</span>}</td></tr>
      </tbody></table>
      <p className="note">When the routes differ, the exception queue raises the case for review.</p>
    </section>
  );
}

function PaymentForm({ studentId, own, done }: { studentId: string; own: boolean; done: () => void }) {
  const [amount, setAmount] = useState("");
  const [method, setMethod] = useState("UPI");
  const [reference, setReference] = useState("");
  const methods = own ? ["UPI", "CARD", "NETBANKING"] : ["UPI", "CARD", "NETBANKING", "BANK_TRANSFER", "CASH", "CHEQUE"];
  const m = useMutation({
    mutationFn: () => post(own ? "/me/payments" : "/payments",
      { ...(own ? {} : { student_id: studentId }), amount_paise: Math.round(parseFloat(amount) * 100), method, reference },
      { "Idempotency-Key": crypto.randomUUID() }),
    onSuccess: (r: any) => { setAmount(""); setReference(""); done(); toast(`Recorded ${r.payment.payment_id}`); },
  });
  const submit = (e: FormEvent) => { e.preventDefault(); m.mutate(); };
  return (
    <form onSubmit={submit} className="panel grid gap-3 no-print" aria-label={own ? "Pay now" : "Record payment"}>
      <h2>{own ? "Pay now" : "Record a payment"}</h2>
      <div className="grid gap-3 sm:grid-cols-3">
        <label className="grid gap-1 text-sm font-semibold">Amount (rupees)<input className="field" inputMode="decimal" required pattern="\d+(\.\d{1,2})?" value={amount} onChange={(e) => setAmount(e.target.value)} /></label>
        <label className="grid gap-1 text-sm font-semibold">Method
          <select className="field" value={method} onChange={(e) => setMethod(e.target.value)}>{methods.map((x) => <option key={x} value={x}>{x === "UPI" ? "UPI" : label(x)}</option>)}</select></label>
        <label className="grid gap-1 text-sm font-semibold">Reference<input className="field" required maxLength={40} value={reference} onChange={(e) => setReference(e.target.value)} /></label>
      </div>
      {m.isError && <p role="alert" className="m-0 text-red">{(m.error as Error).message}</p>}
      {m.isSuccess && <p role="status" className="m-0 text-green">Allocated to your oldest due lines; {inr((m.data as any).unapplied_paise)} left as credit.</p>}
      <div><button className="btn btn-solid" disabled={m.isPending}>{m.isPending && <Spinner />}{own ? "Pay" : "Record and allocate"}</button></div>
    </form>
  );
}

function Enrollments({ rows, canWithdraw, own, done }: { rows: any[]; canWithdraw: boolean; own: boolean; done: () => void }) {
  const [busy, setBusy] = useState<string | null>(null);
  const m = useMutation({
    mutationFn: (id: string) => post(own ? `/me/enrollments/${id}/withdraw` : `/enrollments/${id}/withdraw`, {}),
    onSettled: () => setBusy(null), onSuccess: () => { done(); toast("Withdrawal recorded; fees adjusted"); },
  });
  return (
    <section className="panel"><h2>Enrollments</h2>
      {rows.length === 0 ? <p className="note">No enrollments yet.{own && <> <Link to="/me/enroll">Enrol in a term</Link>.</>}</p> : (
        <div className="scroll-x"><table className="register mt-2"><thead><tr><th>Enrollment</th><th>Term</th><th>Status</th><th>Left</th>{canWithdraw && <th />}</tr></thead><tbody>
          {rows.map((e) => (
            <tr key={e.enrollment_id}><td>{e.enrollment_id}</td><td>{label(e.term_name)}</td><td><Stamp status={e.status} /></td><td>{shortDate(e.left_on)}</td>
              {canWithdraw && <td className="text-right no-print">{e.status === "ENROLLED" && <button className="btn btn-danger" disabled={busy === e.enrollment_id} onClick={() => { if (confirm(`Withdraw ${e.enrollment_id}? Fees are adjusted and any overpayment is refunded.`)) { setBusy(e.enrollment_id); m.mutate(e.enrollment_id); } }}>{busy === e.enrollment_id && <Spinner />}Withdraw</button>}</td>}</tr>))}
        </tbody></table></div>)}
      {m.isError && <p role="alert" className="note text-red">{(m.error as Error).message}</p>}
    </section>
  );
}

function Password() {
  const [cur, setCur] = useState("");
  const [next, setNext] = useState("");
  const m = useMutation({ mutationFn: () => post("/auth/change-password", { current_password: cur, new_password: next }), onSuccess: () => { setCur(""); setNext(""); toast("Password changed"); } });
  return (
    <form onSubmit={(e) => { e.preventDefault(); m.mutate(); }} className="panel grid gap-3 no-print" aria-label="Change password">
      <h2>Change password</h2>
      <div className="grid gap-3 sm:grid-cols-2">
        <label className="grid gap-1 text-sm font-semibold">Current password<input className="field" type="password" autoComplete="current-password" required value={cur} onChange={(e) => setCur(e.target.value)} /></label>
        <label className="grid gap-1 text-sm font-semibold">New password (12+ characters)<input className="field" type="password" autoComplete="new-password" required minLength={12} maxLength={128} value={next} onChange={(e) => setNext(e.target.value)} /></label>
      </div>
      {m.isError && <p role="alert" className="m-0 text-red">{(m.error as Error).message}</p>}
      <div><button className="btn" disabled={m.isPending}>{m.isPending && <Spinner />}Change password</button></div>
    </form>
  );
}

export function StudentPage({ id }: { id: string }) {
  const { me } = useAuth();
  const qc = useQueryClient();
  const role = me!.role;
  const own = role === "LEARNER";
  const money = role !== "INSTRUCTOR";
  const detail = useQuery({ queryKey: ["student", id], queryFn: () => get(`/students/${id}`) });
  const ledger = useQuery({ queryKey: ["ledger", id], queryFn: () => get(`/students/${id}/ledger`), enabled: money });
  const events = useQuery({ queryKey: ["events", id], queryFn: () => get(`/students/${id}/events`), enabled: money });
  usePage(detail.data ? detail.data.student.full_name : "Student", "A student account: balance reconciliation, invoices, enrollments, ledger and state history.");
  const refresh = () => { for (const k of ["student", "ledger", "events", "overview"]) qc.invalidateQueries({ queryKey: [k] }); };
  if (detail.isPending) return <PageLoading labels={["Balance", "Charged", "Paid", "Status"]} rows={3} />;
  if (detail.isError) return <ErrorBox error={detail.error} retry={() => detail.refetch()} />;
  const d = detail.data, s = d.student, b = d.balance;
  const csv = () => downloadCsv(`statement-${id}`, ledger.data?.items ?? [], [
    { header: "Date", value: (e: any) => e.posted_on }, { header: "Type", value: (e: any) => e.entry_type }, { header: "Source", value: (e: any) => e.source_id },
    { header: "Amount (paise)", value: (e: any) => e.amount_paise }, { header: "Running balance (paise)", value: (e: any) => e.running_balance_paise }]);
  return (
    <>
      <Header title={own ? "My account" : s.full_name} lead={`${s.full_name} · ${s.student_id} · ${s.program_name} · ${label(s.residency)} · GPA ${s.gpa}`}>
        {money && <ExportMenu onCsv={ledger.data ? csv : undefined} onJson={() => downloadJson(`student-${id}`, { ...d, ledger: ledger.data?.items, events: events.data?.items })} />}
      </Header>
      <div className="stack">
        {b && (
          <div className="grid-cards">
            <Metric kind="hero" title={b.stated > 0 ? "You owe" : b.stated < 0 ? "Credit held" : "Settled"} value={inr(Math.abs(b.stated))} note={`as of ${shortDate(b.as_of)}`} />
            <Metric kind="sand" title="Charged" value={inr(b.charged_paise)} note={`${inr(-b.credits_paise)} in waivers, awards and adjustments`} />
            <Metric kind="ink" title="Paid" value={inr(-b.paid_paise)} note={`${inr(b.refunded_paise)} refunded`} />
            <Metric kind="mint" title="Invoices" value={d.invoices.length} note={`${d.invoices.filter((i: any) => i.status === "OVERDUE").length} overdue`} />
          </div>)}
        {b && (
          <div className="two-col">
            <section className="panel"><h2>Money by kind</h2>
              {ledger.isPending ? <Loading rows={3} /> : (
                <Donut format={(n) => inr(n)} centre={String(ledger.data?.items.length ?? 0)} sub="entries"
                  slices={KINDS.map(([name, types]) => ({ label: name, value: Math.abs((ledger.data?.items ?? []).filter((e: any) => types.includes(e.entry_type)).reduce((n: number, e: any) => n + e.amount_paise, 0)) })).filter((x) => x.value > 0)} />)}
              <p className="note">Each slice adds up the ledger entries of one kind: fees charged to you, payments you made, awards and waivers that reduced the bill, and refunds paid back.</p>
            </section>
            <section className="panel"><h2>Balance over time</h2>
              <p className="note m-0">Each dot is one ledger entry. The line climbs when a fee is charged (red dot) and drops when you pay or receive an award (green dot). Above the faint zero line you owe money; below it you hold credit. Hover a dot for the entry.</p>
              {ledger.isPending ? <Loading rows={3} /> : ledger.data && ledger.data.items.length > 1 ? (
                <LineChart name="Running balance" labels={ledger.data.items.map((e: any) => shortDate(e.posted_on))} format={(n) => inr(n).replace(/\.00$/, "")}
                  series={[{ name: "Balance you owe", color: "#f75708", values: ledger.data.items.map((e: any) => e.running_balance_paise) }]}
                  dotColor={(i) => (ledger.data.items[i].amount_paise > 0 ? "#d63a12" : "#1f9d6b")}
                  tips={ledger.data.items.map((e: any) => `${shortDate(e.posted_on)}: ${label(e.entry_type)} ${inr(e.amount_paise, { signed: true })}, balance ${inr(e.running_balance_paise)}`)} />) : <p className="note">The chart appears after the first few ledger entries.</p>}
            </section>
          </div>)}
        {b && <Balance b={b} />}
        {role !== "INSTRUCTOR" && <ProfileForm key={s.full_name + s.gpa + s.income_band + String(s.hostel_resident)} student={s} own={own} done={refresh} />}
        {(role === "ACADEMIC_ADMIN" || role === "PLATFORM_ADMIN") && <AssignScholarship studentId={id} done={refresh}
          terms={d.enrollments.filter((e: any) => e.status === "ENROLLED").map((e: any) => ({ term_id: e.term_id, label: label(e.term_name) }))} />}
        {own && <div className="no-print flex flex-wrap gap-3"><Link className="btn btn-solid" to="/me/enroll">Enrol in a term</Link><Link className="btn" to="/me/scholarships">My scholarships</Link><Link className="btn" to="/me/fees">Fee schedule</Link></div>}
        {(own || role === "SUPPORT" || role === "PLATFORM_ADMIN") && <PaymentForm studentId={id} own={own} done={refresh} />}
        <Enrollments rows={d.enrollments} canWithdraw={own || role === "ACADEMIC_ADMIN" || role === "PLATFORM_ADMIN"} own={own} done={refresh} />
        {d.invoices && (
          <section className="panel"><h2>Invoices</h2>
            {d.invoices.length === 0 ? <p className="note">No invoices yet.</p> : (
              <div className="scroll-x"><table className="register mt-2"><thead><tr><th>Invoice</th><th>Issued</th><th>Due</th><th>Status</th><th className="num">Total</th><th /></tr></thead><tbody>
                {d.invoices.map((i: any) => <tr key={i.invoice_id}><td><Link to={`/invoices/${i.invoice_id}`}>{i.invoice_id}</Link></td><td>{shortDate(i.issue_date)}</td><td>{shortDate(i.due_date)}</td><td><Stamp status={i.status} /></td><td><Money paise={i.total_paise} /></td><td className="text-right no-print"><button className="btn" aria-label={`Download ${i.invoice_id}`} onClick={() => downloadInvoice(i.invoice_id).catch((e) => toast(e.message))}><Download size={15} aria-hidden />Download</button></td></tr>)}
              </tbody></table></div>)}
          </section>)}
        {money && (
          <section className="panel"><h2>Ledger</h2>
            {ledger.isPending ? <Loading /> : ledger.isError ? <ErrorBox error={ledger.error} /> : ledger.data.items.length === 0 ? <Empty>No entries yet.</Empty> : (
              <div className="scroll-x"><table className="register mt-2"><thead><tr><th>Date</th><th>Type</th><th>Source</th><th className="num">Amount</th><th className="num">Running</th></tr></thead><tbody>
                {ledger.data.items.map((e: any) => <tr key={e.entry_id}><td>{shortDate(e.posted_on)}</td><td>{label(e.entry_type)}</td><td className="text-muted">{e.source_id}</td><td><Money paise={e.amount_paise} signed /></td><td><Money paise={e.running_balance_paise} /></td></tr>)}
              </tbody></table></div>)}
          </section>)}
        {money && events.data && events.data.items.length > 0 && (
          <section className="panel"><h2>State history</h2>
            <div className="scroll-x"><table className="register mt-2"><thead><tr><th>Date</th><th>Entity</th><th>From</th><th>To</th><th>By</th></tr></thead><tbody>
              {events.data.items.map((e: any) => <tr key={e.event_id}><td>{shortDate(e.occurred_on)}</td><td className="text-muted">{e.entity_id}</td><td>{e.from_status ? label(e.from_status) : "-"}</td><td>{label(e.to_status)}</td><td>{e.actor}</td></tr>)}
            </tbody></table></div></section>)}
        {own && <Password />}
      </div>
    </>
  );
}
