// Data entry and administration screens: new fee version, add student, edit profile, assign scholarship, users.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent, type ReactNode } from "react";
import { Link, useNavigate } from "react-router";
import { Empty, ErrorBox, ExportMenu, Header, Loading, Spinner, Stamp, toast } from "../components/ui";
import { get, post } from "../lib/api";
import { downloadCsv } from "../lib/export";
import { label, shortDate } from "../lib/format";
import { usePage } from "../lib/page";

const Field = ({ text, children }: { text: string; children: ReactNode }) => <label className="grid gap-1 text-sm font-semibold">{text}{children}</label>;
const Err = ({ error }: { error: unknown }) => (error ? <p role="alert" className="m-0 text-red">{(error as Error).message}</p> : null);
const Sel = ({ value, set, options }: { value: string; set: (v: string) => void; options: [string, string][] }) =>
  <select className="field" value={value} onChange={(e) => set(e.target.value)}>{options.map(([v, t]) => <option key={v} value={v}>{t}</option>)}</select>;
const Check = ({ text, value, set }: { text: string; value: boolean; set: (v: boolean) => void }) =>
  <label className="flex min-h-10 items-center gap-2 text-sm font-semibold"><input type="checkbox" checked={value} onChange={(e) => set(e.target.checked)} />{text}</label>;

const FEE_TYPES = ["TUITION", "LAB", "LIBRARY", "TECHNOLOGY", "EXAM", "INTL_SURCHARGE", "HOSTEL"];
const BANDS: [string, string][] = [["LOW", "Low"], ["MID", "Mid"], ["HIGH", "High"], ["AFFLUENT", "Affluent"]];
const NUM = "(10(\\.0+)?|\\d(\\.\\d+)?)";

/* ------------------------------------------------------------------ new fee version (academic admin, platform admin) */
export function NewFeeForm({ program, term }: { program: string; term: string }) {
  const qc = useQueryClient();
  const [f, setF] = useState({ fee_type: "TUITION", applies_to: "ALL", amount: "", effective_from: "", scholarship_eligible: true });
  const m = useMutation({
    mutationFn: () => post("/fee-schedules", { program_id: program, term_id: term, fee_type: f.fee_type, applies_to: f.applies_to, amount_paise: Math.round(parseFloat(f.amount) * 100),
      effective_from: f.effective_from, scholarship_eligible: f.scholarship_eligible }),
    onSuccess: (r: any) => { qc.invalidateQueries({ queryKey: ["fees"] }); setF({ ...f, amount: "" }); toast(`Published ${r.fee_schedule_id}`); },
  });
  const submit = (e: FormEvent) => { e.preventDefault(); m.mutate(); };
  return (
    <form onSubmit={submit} className="panel mb-6 grid gap-3 no-print" aria-label="New fee version">
      <h2>Publish a new fee version</h2>
      <p className="note m-0">For {program} in {term}. The previous version of the same fee closes the day before. Invoices already issued keep their old price; the next enrolment is billed at the new one.</p>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Field text="Fee"><Sel value={f.fee_type} set={(v) => setF({ ...f, fee_type: v })} options={FEE_TYPES.map((t) => [t, label(t)])} /></Field>
        <Field text="Applies to"><Sel value={f.applies_to} set={(v) => setF({ ...f, applies_to: v })} options={[["ALL", "Everyone"], ["INTERNATIONAL", "International"], ["HOSTEL", "Hostel residents"]]} /></Field>
        <Field text="Amount (rupees)"><input className="field" inputMode="decimal" required pattern="\d+(\.\d{1,2})?" value={f.amount} onChange={(e) => setF({ ...f, amount: e.target.value })} /></Field>
        <Field text="Effective from"><input className="field" type="date" required value={f.effective_from} onChange={(e) => setF({ ...f, effective_from: e.target.value })} /></Field>
      </div>
      <Check text="Scholarships may apply to this fee" value={f.scholarship_eligible} set={(v) => setF({ ...f, scholarship_eligible: v })} />
      <Err error={m.error} />
      <div><button className="btn btn-solid" disabled={m.isPending}>{m.isPending && <Spinner />}Publish version</button></div>
    </form>
  );
}

/* ------------------------------------------------------------------ add a student (staff) */
export function AddStudent() {
  usePage("Add student", "Create a student record, optionally with a sign-in, entered by staff.");
  const nav = useNavigate();
  const programs = useQuery({ queryKey: ["programs"], queryFn: () => get("/programs") });
  const [f, setF] = useState({ full_name: "", program_id: "PRG-01", residency: "DOMESTIC", gpa: "", income_band: "MID", sports_quota: false, hostel_resident: false, waiver_type: "", login: false, login_email: "", login_password: "" });
  const m = useMutation({
    mutationFn: () => post("/students", { full_name: f.full_name, program_id: f.program_id, residency: f.residency, gpa: parseFloat(f.gpa), income_band: f.income_band,
      sports_quota: f.sports_quota, hostel_resident: f.hostel_resident, waiver_type: f.waiver_type || null,
      ...(f.login ? { login_email: f.login_email, login_password: f.login_password } : {}) }, { "Idempotency-Key": crypto.randomUUID() }),
    onSuccess: (r: any) => { toast(`Added ${r.student_id}`); nav(`/students/${r.student_id}`); },
  });
  return (
    <>
      <Header title="Add a student" lead="Staff data entry. The student starts with a zero balance; enrol them in a term from their page." />
      <form onSubmit={(e) => { e.preventDefault(); m.mutate(); }} className="panel grid gap-4" aria-label="Add a student">
        <div className="grid gap-3 sm:grid-cols-2">
          <Field text="Full name"><input className="field" required minLength={2} maxLength={80} value={f.full_name} onChange={(e) => setF({ ...f, full_name: e.target.value })} /></Field>
          <Field text="Program"><Sel value={f.program_id} set={(v) => setF({ ...f, program_id: v })} options={(programs.data?.items ?? [{ program_id: "PRG-01", name: "" }]).map((p: any) => [p.program_id, `${p.program_id} ${p.name}`])} /></Field>
          <Field text="Residency"><Sel value={f.residency} set={(v) => setF({ ...f, residency: v })} options={[["DOMESTIC", "Domestic"], ["INTERNATIONAL", "International"]]} /></Field>
          <Field text="GPA (0 to 10)"><input className="field" inputMode="decimal" required pattern={NUM} value={f.gpa} onChange={(e) => setF({ ...f, gpa: e.target.value })} /></Field>
          <Field text="Income band"><Sel value={f.income_band} set={(v) => setF({ ...f, income_band: v })} options={BANDS} /></Field>
          <Field text="Waiver"><Sel value={f.waiver_type} set={(v) => setF({ ...f, waiver_type: v })} options={[["", "None"], ["STAFF_WARD", "Staff ward"], ["SIBLING", "Sibling"], ["HARDSHIP", "Hardship"]]} /></Field>
        </div>
        <div className="flex flex-wrap gap-6"><Check text="Sports quota" value={f.sports_quota} set={(v) => setF({ ...f, sports_quota: v })} /><Check text="Hostel resident" value={f.hostel_resident} set={(v) => setF({ ...f, hostel_resident: v })} />
          <Check text="Also create a learner sign-in" value={f.login} set={(v) => setF({ ...f, login: v })} /></div>
        {f.login && (
          <div className="grid gap-3 sm:grid-cols-2">
            <Field text="Sign-in email"><input className="field" type="email" required value={f.login_email} onChange={(e) => setF({ ...f, login_email: e.target.value })} /></Field>
            <Field text="Initial password (12+ characters)"><input className="field" type="password" autoComplete="new-password" required minLength={12} maxLength={128} value={f.login_password} onChange={(e) => setF({ ...f, login_password: e.target.value })} /></Field>
          </div>)}
        <Err error={m.error} />
        <div className="flex gap-3"><button className="btn btn-solid" disabled={m.isPending}>{m.isPending && <Spinner />}Add student</button><Link className="btn" to="/students">Cancel</Link></div>
      </form>
    </>
  );
}

/* ------------------------------------------------------------------ edit profile (staff: everything; learner: name and housing) */
export function ProfileForm({ student, own, done }: { student: any; own: boolean; done: () => void }) {
  const [f, setF] = useState({ full_name: student.full_name, gpa: String(student.gpa), income_band: student.income_band, residency: student.residency,
    sports_quota: !!student.sports_quota, hostel_resident: !!student.hostel_resident });
  const m = useMutation({
    mutationFn: () => own ? post("/me/profile", { full_name: f.full_name, hostel_resident: f.hostel_resident })
      : post(`/students/${student.student_id}/profile`, { full_name: f.full_name, gpa: parseFloat(f.gpa), income_band: f.income_band, residency: f.residency, sports_quota: f.sports_quota, hostel_resident: f.hostel_resident }),
    onSuccess: () => { done(); toast("Profile saved"); },
  });
  return (
    <form onSubmit={(e) => { e.preventDefault(); m.mutate(); }} className="panel grid gap-3 no-print" aria-label="Edit profile">
      <h2>{own ? "My details" : "Edit details"}</h2>
      <div className="grid gap-3 sm:grid-cols-2">
        <Field text="Full name"><input className="field" required minLength={2} maxLength={80} value={f.full_name} onChange={(e) => setF({ ...f, full_name: e.target.value })} /></Field>
        {!own && <>
          <Field text="GPA"><input className="field" inputMode="decimal" required pattern={NUM} value={f.gpa} onChange={(e) => setF({ ...f, gpa: e.target.value })} /></Field>
          <Field text="Income band"><Sel value={f.income_band} set={(v) => setF({ ...f, income_band: v })} options={BANDS} /></Field>
          <Field text="Residency"><Sel value={f.residency} set={(v) => setF({ ...f, residency: v })} options={[["DOMESTIC", "Domestic"], ["INTERNATIONAL", "International"]]} /></Field></>}
      </div>
      <div className="flex flex-wrap gap-6">{!own && <Check text="Sports quota" value={f.sports_quota} set={(v) => setF({ ...f, sports_quota: v })} />}<Check text="Hostel resident" value={f.hostel_resident} set={(v) => setF({ ...f, hostel_resident: v })} /></div>
      {own && <p className="note m-0">GPA, income band and residency decide scholarships, so staff maintain them.</p>}
      <Err error={m.error} />
      <div><button className="btn" disabled={m.isPending}>{m.isPending && <Spinner />}Save details</button></div>
    </form>
  );
}

/* ------------------------------------------------------------------ assign a scholarship (academic admin, platform admin) */
const SCHEMES: [string, string][] = [["MERIT_GOLD", "Merit gold"], ["MERIT_SILVER", "Merit silver"], ["NEED_BASED", "Need based"], ["SPORTS", "Sports"], ["INTL_EXCELLENCE", "International excellence"]];
export function AssignScholarship({ studentId, terms, done }: { studentId: string; terms: { term_id: string; label: string }[]; done: () => void }) {
  const [term, setTerm] = useState(terms[0]?.term_id ?? "");
  const [scheme, setScheme] = useState("MERIT_GOLD");
  const m = useMutation({
    mutationFn: () => post(`/students/${studentId}/scholarships`, { term_id: term, scheme_code: scheme }, { "Idempotency-Key": crypto.randomUUID() }),
    onSuccess: (r: any) => { done(); toast(`Awarded ${r.scholarship.scholarship_id}`); },
  });
  if (terms.length === 0) return null;
  return (
    <form onSubmit={(e) => { e.preventDefault(); m.mutate(); }} className="panel grid gap-3 no-print" aria-label="Assign scholarship">
      <h2>Assign a scholarship</h2>
      <p className="note m-0">The scheme's criteria still apply: a student who does not qualify is refused, with the reason.</p>
      <div className="grid gap-3 sm:grid-cols-2">
        <Field text="Term"><Sel value={term} set={setTerm} options={terms.map((t) => [t.term_id, t.label])} /></Field>
        <Field text="Scheme"><Sel value={scheme} set={setScheme} options={SCHEMES} /></Field>
      </div>
      <Err error={m.error} />
      <div><button className="btn" disabled={m.isPending}>{m.isPending && <Spinner />}Assign</button></div>
    </form>
  );
}

/* ------------------------------------------------------------------ users (platform admin) */
const ROLES: [string, string][] = [["SUPPORT", "Support"], ["ACADEMIC_ADMIN", "Academic admin"], ["PLATFORM_ADMIN", "Platform admin"], ["INSTRUCTOR", "Instructor"], ["LEARNER", "Learner"]];
export function Users() {
  usePage("Users", "Sign-in accounts: create staff and learner logins, enable or disable access.");
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["users"], queryFn: () => get("/admin/users") });
  const programs = useQuery({ queryKey: ["programs"], queryFn: () => get("/programs") });
  const [f, setF] = useState({ email: "", password: "", role: "SUPPORT", student_id: "", program_id: "PRG-01" });
  const create = useMutation({
    mutationFn: () => post("/admin/users", { email: f.email, password: f.password, role: f.role,
      ...(f.role === "LEARNER" ? { student_id: f.student_id } : {}), ...(f.role === "INSTRUCTOR" ? { program_id: f.program_id } : {}) }),
    onSuccess: () => { setF({ ...f, email: "", password: "", student_id: "" }); qc.invalidateQueries({ queryKey: ["users"] }); toast("Account created"); },
  });
  const toggle = useMutation({
    mutationFn: (v: { id: string; enabled: boolean }) => post(`/admin/users/${v.id}/enabled`, { enabled: v.enabled }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["users"] }),
  });
  return (
    <>
      <Header title="Users" lead="Who can sign in, and as what. A disabled account is refused on its next request, even with a valid token.">
        <ExportMenu onCsv={() => downloadCsv("users", q.data?.items ?? [], [{ header: "Id", value: (u: any) => u.app_user_id }, { header: "Email", value: (u: any) => u.email },
          { header: "Role", value: (u: any) => u.role }, { header: "Student", value: (u: any) => u.student_id }, { header: "Program", value: (u: any) => u.program_id }, { header: "Enabled", value: (u: any) => u.enabled }])} />
      </Header>
      <form onSubmit={(e) => { e.preventDefault(); create.mutate(); }} className="panel mb-6 grid gap-3" aria-label="Create account">
        <h2>Create an account</h2>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <Field text="Email"><input className="field" type="email" required value={f.email} onChange={(e) => setF({ ...f, email: e.target.value })} /></Field>
          <Field text="Password (12+ characters)"><input className="field" type="password" autoComplete="new-password" required minLength={12} maxLength={128} value={f.password} onChange={(e) => setF({ ...f, password: e.target.value })} /></Field>
          <Field text="Role"><Sel value={f.role} set={(v) => setF({ ...f, role: v })} options={ROLES} /></Field>
          {f.role === "LEARNER" && <Field text="Student id"><input className="field" required pattern="STU-\d{6}" placeholder="STU-000001" value={f.student_id} onChange={(e) => setF({ ...f, student_id: e.target.value })} /></Field>}
          {f.role === "INSTRUCTOR" && <Field text="Program"><Sel value={f.program_id} set={(v) => setF({ ...f, program_id: v })} options={(programs.data?.items ?? []).map((p: any) => [p.program_id, `${p.program_id} ${p.name}`])} /></Field>}
        </div>
        <Err error={create.error} />
        <div><button className="btn btn-solid" disabled={create.isPending}>{create.isPending && <Spinner />}Create account</button></div>
      </form>
      {q.isPending ? <Loading /> : q.isError ? <ErrorBox error={q.error} retry={() => q.refetch()} /> : q.data.items.length === 0 ? <Empty>No accounts.</Empty> : (
        <div className="panel scroll-x"><table className="register"><thead><tr><th>Id</th><th>Email</th><th>Role</th><th>Scope</th><th>Created</th><th>Access</th><th /></tr></thead><tbody>
          {q.data.items.map((u: any) => (
            <tr key={u.app_user_id}><td>{u.app_user_id}</td><td>{u.email}</td><td>{label(u.role)}</td><td className="text-muted">{u.student_id ?? u.program_id ?? "-"}</td><td>{shortDate(u.created_at)}</td>
              <td><Stamp status={u.enabled ? "COMPLETED" : "REVOKED"} /></td>
              <td className="text-right"><button className="btn" disabled={toggle.isPending} onClick={() => toggle.mutate({ id: u.app_user_id, enabled: !u.enabled })}>{u.enabled ? "Disable" : "Enable"}</button></td></tr>))}
        </tbody></table></div>)}
      {toggle.isError && <p role="alert" className="note text-red">{(toggle.error as Error).message}</p>}
    </>
  );
}
