import { useInfiniteQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router";
import { Empty, ErrorBox, ExportMenu, Header, Loading, Money, More, toast } from "../components/ui";
import { get } from "../lib/api";
import { seesMoney, useAuth } from "../lib/auth";
import { downloadCsv, fetchAll } from "../lib/export";
import { usePage } from "../lib/page";

export default function Students() {
  usePage("Students", "Search students and see balances, open exceptions and reconciliation status.");
  const { me } = useAuth();
  const nav = useNavigate();
  const money = me ? seesMoney(me.role) : false;
  const [q, setQ] = useState("");
  const [term, setTerm] = useState("");
  const [filter, setFilter] = useState("");
  const [exporting, setExporting] = useState(false);
  useEffect(() => { const t = setTimeout(() => setTerm(q.trim()), 250); return () => clearTimeout(t); }, [q]);
  const query = { q: term, owing: filter === "owing" ? true : undefined, flagged: filter === "flagged" ? true : undefined };
  const list = useInfiniteQuery({
    queryKey: ["students", term, filter],
    initialPageParam: "" as string,
    queryFn: ({ pageParam }) => get("/students", { ...query, after: pageParam, limit: 50 }),
    getNextPageParam: (last: any) => last.next ?? undefined,
  });
  const rows = list.data?.pages.flatMap((p: any) => p.items) ?? [];
  const exportCsv = async () => {
    setExporting(true);
    try {
      const all = await fetchAll("/students", query);
      downloadCsv("studease-students", all, [
        { header: "Student", value: (r: any) => r.student_id }, { header: "Name", value: (r: any) => r.full_name },
        { header: "Email", value: (r: any) => r.email }, { header: "Program", value: (r: any) => r.program_id },
        ...(money ? [{ header: "Balance (paise)", value: (r: any) => r.balance_paise }, { header: "Charged (paise)", value: (r: any) => r.charged_paise },
          { header: "Paid (paise)", value: (r: any) => r.paid_paise }, { header: "Open exceptions", value: (r: any) => r.open_exceptions }] : []),
      ]);
      toast(`Exported ${all.length.toLocaleString("en-IN")} students`);
    } finally { setExporting(false); }
  };
  return (
    <>
      <Header title="Students" lead={money ? "Search by id, name or email. Balance is positive when the student owes money." : "Students of your program, with enrollment status."}>
        <ExportMenu onCsv={exportCsv} busy={exporting} />
      </Header>
      <div className="no-print mb-5 flex flex-wrap gap-3">
        <input className="field max-w-sm" type="search" placeholder="Search id, name or email" aria-label="Search students" value={q} onChange={(e) => setQ(e.target.value)} />
        {money && (
          <select className="field max-w-[13rem]" aria-label="Filter" value={filter} onChange={(e) => setFilter(e.target.value)}>
            <option value="">All students</option><option value="owing">Owing money</option><option value="flagged">Has open exception</option>
          </select>)}
      </div>
      {list.isPending ? <div className="panel"><Loading rows={9} /></div> : list.isError ? <ErrorBox error={list.error} retry={() => list.refetch()} /> : rows.length === 0 ? <Empty>No student matches.</Empty> : (
        <div className="panel scroll-x"><table className="register">
          <thead><tr><th>Student</th><th>Name</th><th>Program</th>{money && <><th className="num">Balance</th><th className="num">Exceptions</th></>}</tr></thead>
          <tbody>
            {rows.map((s: any) => (
              <tr key={s.student_id} className="clickable" tabIndex={0} onClick={() => nav(`/students/${s.student_id}`)} onKeyDown={(e) => e.key === "Enter" && nav(`/students/${s.student_id}`)}>
                <td>{s.student_id}</td><td>{s.full_name}</td><td>{s.program_id}</td>
                {money && <><td><Money paise={s.balance_paise} /></td><td className="num">{s.open_exceptions > 0 ? <span className="stamp stamp-bad">{s.open_exceptions}</span> : "-"}</td></>}
              </tr>))}
          </tbody></table></div>)}
      <More next={list.data?.pages.at(-1)?.next} onMore={() => list.fetchNextPage()} busy={list.isFetchingNextPage} />
    </>
  );
}
