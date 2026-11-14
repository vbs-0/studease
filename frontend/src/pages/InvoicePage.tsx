import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router";
import { ErrorBox, Header, Loading, Money, Stamp } from "../components/ui";
import { get } from "../lib/api";
import { label, shortDate } from "../lib/format";
import { usePage } from "../lib/page";

export default function InvoicePage() {
  const { id = "" } = useParams();
  usePage("Invoice", "Invoice lines with credits, allocations per line and the status history.");
  const q = useQuery({ queryKey: ["invoice", id], queryFn: () => get(`/invoices/${id}`) });
  if (q.isPending) return <Loading rows={6} />;
  if (q.isError) return <ErrorBox error={q.error} retry={() => q.refetch()} />;
  const { invoice: inv, lines, history } = q.data;
  return (
    <>
      <Header title="Invoice" lead={inv.invoice_id}><Stamp status={inv.status} /></Header>
      <p className="text-muted">Student <Link to={`/students/${inv.student_id}`}>{inv.student_id}</Link> · issued {shortDate(inv.issue_date)} · due {shortDate(inv.due_date)}</p>
      <section className="panel"><div className="scroll-x"><table className="register"><thead><tr><th>#</th><th>Type</th><th>Description</th><th className="num">Amount</th><th className="num">Paid</th><th className="num">Outstanding</th></tr></thead><tbody>
        {lines.map((l: any) => (
          <tr key={l.invoice_line_id}><td>{l.line_no}</td><td>{label(l.line_type)}</td><td>{l.description}</td><td><Money paise={l.amount_paise} signed={l.amount_paise < 0} /></td>
            <td>{l.outstanding_paise === null ? "" : <Money paise={l.allocated_paise} />}</td><td>{l.outstanding_paise === null ? "" : <Money paise={l.outstanding_paise} />}</td></tr>))}
        <tr><td colSpan={3} className="font-bold">Total</td><td><Money paise={inv.total_paise} className="font-bold" /></td><td /><td /></tr>
      </tbody></table></div></section>
      <section className="panel mt-6"><h2 className="serif m-0 text-3xl">Status history</h2>
        <table className="register mt-2"><thead><tr><th>Date</th><th>From</th><th>To</th></tr></thead><tbody>
          {history.map((h: any) => <tr key={h.event_id}><td>{shortDate(h.occurred_on)}</td><td>{h.from_status ? label(h.from_status) : "-"}</td><td>{label(h.to_status)}</td></tr>)}
        </tbody></table></section>
    </>
  );
}
