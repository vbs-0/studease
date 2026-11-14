import { useInfiniteQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router";
import { Empty, ErrorBox, ExportMenu, Header, Loading, Money, More, Spinner, Stamp, toast } from "../components/ui";
import { downloadCsv, fetchAll } from "../lib/export";
import { get, post } from "../lib/api";
import { useAuth } from "../lib/auth";
import { label } from "../lib/format";
import { usePage } from "../lib/page";

const TYPES = ["ALLOC_EXCEEDS_PAYMENT", "SCHOLARSHIP_EXCEEDS_ELIGIBLE", "DUPLICATE_INVOICE", "REFUND_EXCEEDS_NET_PAID", "BALANCE_LEDGER_MISMATCH"];

export default function Exceptions() {
  usePage("Exceptions", "The queue of detected billing and reconciliation exceptions, with recommended decisions.");
  const { me } = useAuth();
  const qc = useQueryClient();
  const [status, setStatus] = useState("OPEN");
  const [type, setType] = useState("");
  const [open, setOpen] = useState<string | null>(null);
  const [note, setNote] = useState("");
  const [exporting, setExporting] = useState(false);
  const q = useInfiniteQuery({
    queryKey: ["exceptions", status, type], initialPageParam: "" as string,
    queryFn: ({ pageParam }) => get("/exceptions", { status, exception_type: type, after: pageParam, limit: 50 }),
    getNextPageParam: (l: any) => l.next ?? undefined,
  });
  const close = useMutation({
    mutationFn: (v: { id: string; status: "RESOLVED" | "DISMISSED" }) => post(`/exceptions/${v.id}/resolve`, { status: v.status, note }),
    onSuccess: () => { setOpen(null); setNote(""); qc.invalidateQueries({ queryKey: ["exceptions"] }); qc.invalidateQueries({ queryKey: ["overview"] }); },
  });
  const rows = q.data?.pages.flatMap((p: any) => p.items) ?? [];
  const counts = q.data?.pages[0]?.counts ?? {};
  return (
    <>
      <Header title="Exceptions" lead="Found by the detectors from the books alone. Each case names what the rules expect and what the data holds.">
        <ExportMenu busy={exporting} onCsv={async () => {
          setExporting(true);
          try {
            const all = await fetchAll("/exceptions", { status, exception_type: type });
            downloadCsv("exceptions", all, [
              { header: "Case", value: (e: any) => e.exception_id }, { header: "Type", value: (e: any) => e.exception_type }, { header: "Student", value: (e: any) => e.student_id },
              { header: "Entity", value: (e: any) => e.entity_id }, { header: "Expected (paise)", value: (e: any) => e.expected_paise }, { header: "Found (paise)", value: (e: any) => e.found_paise },
              { header: "Suggested decision", value: (e: any) => e.recommended_decision }, { header: "Status", value: (e: any) => e.status }, { header: "Note", value: (e: any) => e.note }]);
            toast(`Exported ${all.length} exceptions`);
          } finally { setExporting(false); }
        }} />
      </Header>
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <select className="field max-w-[12rem]" aria-label="Status" value={status} onChange={(e) => setStatus(e.target.value)}>
          {["OPEN", "RESOLVED", "DISMISSED"].map((s) => <option key={s} value={s}>{label(s)} ({counts[s] ?? 0})</option>)}</select>
        <select className="field max-w-xs" aria-label="Type" value={type} onChange={(e) => setType(e.target.value)}>
          <option value="">All types</option>{TYPES.map((t) => <option key={t} value={t}>{label(t)}</option>)}</select>
      </div>
      {q.isPending ? <Loading rows={6} /> : q.isError ? <ErrorBox error={q.error} retry={() => q.refetch()} /> : rows.length === 0 ? <Empty>Nothing here.</Empty> : (
        <div className="panel scroll-x"><table className="register"><thead><tr><th>Case</th><th>Type</th><th>Student</th><th className="num">Expected</th><th className="num">Found</th><th>Suggested</th><th>Status</th><th /></tr></thead><tbody>
          {rows.map((e: any) => (
            <>
              <tr key={e.exception_id}><td>{e.exception_id}</td><td>{label(e.exception_type)}</td><td><Link to={`/students/${e.student_id}`}>{e.student_id}</Link></td>
                <td><Money paise={e.expected_paise} /></td><td><span className={e.found_paise !== e.expected_paise ? "strike-draw" : ""}><Money paise={e.found_paise} /></span></td>
                <td>{label(e.recommended_decision)}</td><td><Stamp status={e.status} /></td>
                <td className="text-right">{e.status === "OPEN" && me?.role === "SUPPORT" && <button className="btn" onClick={() => { setOpen(open === e.exception_id ? null : e.exception_id); setNote(""); }}>Review</button>}</td></tr>
              {open === e.exception_id && (
                <tr key={e.exception_id + "-form"}><td colSpan={8}>
                  <div className="grid gap-2 sm:grid-cols-[1fr_auto_auto]">
                    <input className="field" aria-label="Note" placeholder="Note (required)" maxLength={400} value={note} onChange={(ev) => setNote(ev.target.value)} />
                    <button className="btn btn-solid" disabled={!note.trim() || close.isPending} onClick={() => close.mutate({ id: e.exception_id, status: "RESOLVED" })}>{close.isPending && <Spinner />}Resolve</button>
                    <button className="btn" disabled={!note.trim() || close.isPending} onClick={() => close.mutate({ id: e.exception_id, status: "DISMISSED" })}>Dismiss</button>
                  </div>
                  {close.isError && <p role="alert" className="m-0 mt-2 text-red">{(close.error as Error).message}</p>}
                </td></tr>)}
            </>))}
        </tbody></table></div>)}
      <More next={q.data?.pages.at(-1)?.next} onMore={() => q.fetchNextPage()} busy={q.isFetchingNextPage} />
    </>
  );
}
