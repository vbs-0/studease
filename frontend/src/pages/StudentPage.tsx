import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Link, Navigate, useParams } from "react-router";
import { Empty, ErrorBox, Header, Loading, Money, Spinner, Stamp } from "../components/ui";
import { get, post } from "../lib/api";
import { useAuth } from "../lib/auth";
import { inr, label, shortDate } from "../lib/format";
import { usePage } from "../lib/page";

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
    <section className="panel reveal">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div><div className="eyebrow">Balance</div>
          <div className="big"><Money paise={b.stated} signed /></div>
          <div className="text-sm text-muted">{b.stated > 0 ? "Owed by the student" : b.stated < 0 ? "Credit held for the student" : "Settled"}</div></div>
        <span className={`stamp ${ok ? "stamp-ok" : "stamp-bad"}`}>{ok ? "Reconciled" : "Does not reconcile"}</span>
      </div>
      <table className="register mt-3"><tbody>
        <tr><td>Stated balance</td><td><Money paise={b.stated} /></td></tr>
        <tr><td>Sum of ledger entries</td><td>{b.ledger === b.stated ? <Money paise={b.ledger} /> : <span className="strike-draw num">{inr(b.ledger)}</span>}</td></tr>
        <tr><td>Invoices minus payments plus refunds</td><td>{b.from_documents === b.stated ? <Money paise={b.from_documents} /> : <span className="strike-draw num">{inr(b.from_documents)}</span>}</td></tr>
      </tbody></table>
      <p className="mb-0 mt-2 text-sm text-muted">Three independent routes to one number. When they differ, the exception is raised for review.</p>
    </section>
  );
}

function PaymentForm({ studentId, done }: { studentId: string; done: () => void }) {
  const [amount, setAmount] = useState("");
  const [method, setMethod] = useState("UPI");
  const [reference, setReference] = useState("");
  const m = useMutation({
    mutationFn: () => post("/payments", { student_id: studentId, amount_paise: Math.round(parseFloat(amount) * 100), method, reference }, { "Idempotency-Key": crypto.randomUUID() }),
    onSuccess: () => { setAmount(""); setReference(""); done(); },
  });
  const submit = (e: FormEvent) => { e.preventDefault(); m.mutate(); };
  return (
    <form onSubmit={submit} className="panel reveal grid gap-3" aria-label="Record payment">
      <h2 className="serif m-0 text-3xl">Record a payment</h2>
      <div className="grid gap-3 sm:grid-cols-3">
        <label className="grid gap-1 text-sm font-semibold">Amount (rupees)<input className="field" inputMode="decimal" required pattern="\d+(\.\d{1,2})?" value={amount} onChange={(e) => setAmount(e.target.value)} /></label>
        <label className="grid gap-1 text-sm font-semibold">Method
          <select className="field" value={method} onChange={(e) => setMethod(e.target.value)}>{["UPI", "CARD", "NETBANKING", "BANK_TRANSFER", "CASH", "CHEQUE"].map((x) => <option key={x} value={x}>{x === "UPI" ? "UPI" : label(x)}</option>)}</select></label>
        <label className="grid gap-1 text-sm font-semibold">Reference<input className="field" required maxLength={40} value={reference} onChange={(e) => setReference(e.target.value)} /></label>
      </div>
      {m.isError && <p role="alert" className="m-0 text-red">{(m.error as Error).message}</p>}
      {m.isSuccess && <p role="status" className="m-0 text-green">Recorded {(m.data as any).payment.payment_id}; {inr((m.data as any).unapplied_paise)} left as credit.</p>}
      <div><button className="btn btn-solid" disabled={m.isPending}>{m.isPending && <Spinner />}Record and allocate</button></div>
    </form>
  );
}

function Enrollments({ rows, canWithdraw, done }: { rows: any[]; canWithdraw: boolean; done: () => void }) {
  const [busy, setBusy] = useState<string | null>(null);
  const m = useMutation({ mutationFn: (id: string) => post(`/enrollments/${id}/withdraw`, {}), onSettled: () => setBusy(null), onSuccess: done });
  return (
    <section className="panel reveal"><h2 className="serif m-0 text-3xl">Enrollments</h2>
      <div className="scroll-x"><table className="register mt-2"><thead><tr><th>Enrollment</th><th>Term</th><th>Status</th><th>Left</th>{canWithdraw && <th />}</tr></thead><tbody>
        {rows.map((e) => (
          <tr key={e.enrollment_id}><td>{e.enrollment_id}</td><td>{label(e.term_name)}</td><td><Stamp status={e.status} /></td><td>{shortDate(e.left_on)}</td>
            {canWithdraw && <td className="text-right">{e.status === "ENROLLED" && <button className="btn btn-danger" disabled={busy === e.enrollment_id} onClick={() => { if (confirm(`Withdraw ${e.enrollment_id}? Fees are adjusted and any overpayment is refunded.`)) { setBusy(e.enrollment_id); m.mutate(e.enrollment_id); } }}>Withdraw</button>}</td>}</tr>))}
      </tbody></table></div>
      {m.isError && <p role="alert" className="m-0 mt-2 text-red">{(m.error as Error).message}</p>}
    </section>
  );
}

export function StudentPage({ id }: { id: string }) {
  const { me } = useAuth();
  const qc = useQueryClient();
  const money = me!.role !== "INSTRUCTOR";
  const detail = useQuery({ queryKey: ["student", id], queryFn: () => get(`/students/${id}`) });
  const ledger = useQuery({ queryKey: ["ledger", id], queryFn: () => get(`/students/${id}/ledger`), enabled: money });
  const events = useQuery({ queryKey: ["events", id], queryFn: () => get(`/students/${id}/events`), enabled: money });
  usePage(detail.data ? detail.data.student.full_name : "Student", "A student account: balance reconciliation, invoices, enrollments, ledger and state history.");
  const refresh = () => { qc.invalidateQueries({ queryKey: ["student", id] }); qc.invalidateQueries({ queryKey: ["ledger", id] }); qc.invalidateQueries({ queryKey: ["events", id] }); };
  if (detail.isPending) return <Loading rows={6} />;
  if (detail.isError) return <ErrorBox error={detail.error} retry={() => detail.refetch()} />;
  const d = detail.data, s = d.student;
  return (
    <>
      <Header title={s.full_name} lead={`${s.student_id} · ${s.program_name} · ${label(s.residency)} · GPA ${s.gpa}`} />
      <div className="grid gap-6">
        {d.balance && <Balance b={d.balance} />}
        {(me!.role === "SUPPORT" || me!.role === "PLATFORM_ADMIN") && <PaymentForm studentId={id} done={refresh} />}
        <Enrollments rows={d.enrollments} canWithdraw={me!.role === "ACADEMIC_ADMIN" || me!.role === "PLATFORM_ADMIN"} done={refresh} />
        {d.invoices && (
          <section className="panel reveal"><h2 className="serif m-0 text-3xl">Invoices</h2>
            <div className="scroll-x"><table className="register mt-2"><thead><tr><th>Invoice</th><th>Issued</th><th>Due</th><th>Status</th><th className="num">Total</th></tr></thead><tbody>
              {d.invoices.map((i: any) => <tr key={i.invoice_id}><td><Link to={`/invoices/${i.invoice_id}`}>{i.invoice_id}</Link></td><td>{shortDate(i.issue_date)}</td><td>{shortDate(i.due_date)}</td><td><Stamp status={i.status} /></td><td><Money paise={i.total_paise} /></td></tr>)}
            </tbody></table></div></section>)}
        {money && (
          <section className="panel reveal"><h2 className="serif m-0 text-3xl">Ledger</h2>
            {ledger.isPending ? <Loading /> : ledger.isError ? <ErrorBox error={ledger.error} /> : ledger.data.items.length === 0 ? <Empty>No entries yet.</Empty> : (
              <div className="scroll-x"><table className="register mt-2"><thead><tr><th>Date</th><th>Type</th><th>Source</th><th className="num">Amount</th><th className="num">Running</th></tr></thead><tbody>
                {ledger.data.items.map((e: any) => <tr key={e.entry_id}><td>{shortDate(e.posted_on)}</td><td>{label(e.entry_type)}</td><td className="text-muted">{e.source_id}</td><td><Money paise={e.amount_paise} signed /></td><td><Money paise={e.running_balance_paise} /></td></tr>)}
              </tbody></table></div>)}
          </section>)}
        {money && events.data && events.data.items.length > 0 && (
          <section className="panel reveal"><h2 className="serif m-0 text-3xl">State history</h2>
            <div className="scroll-x"><table className="register mt-2"><thead><tr><th>Date</th><th>Entity</th><th>From</th><th>To</th><th>By</th></tr></thead><tbody>
              {events.data.items.map((e: any) => <tr key={e.event_id}><td>{shortDate(e.occurred_on)}</td><td className="text-muted">{e.entity_id}</td><td>{e.from_status ? label(e.from_status) : "-"}</td><td>{label(e.to_status)}</td><td>{e.actor}</td></tr>)}
            </tbody></table></div></section>)}
      </div>
    </>
  );
}
