import { useMutation, useQuery } from "@tanstack/react-query";
import { useState, type FormEvent, type ReactNode } from "react";
import { Link, Navigate, useNavigate, useSearchParams } from "react-router";
import { ThemeToggle, homeFor } from "../components/Shell";
import { Logo, Spinner } from "../components/ui";
import { get, post, setToken } from "../lib/api";
import { useAuth } from "../lib/auth";
import { usePage } from "../lib/page";

const DEMO = [["learner", "Learner"], ["instructor", "Instructor"], ["academic", "Academic admin"], ["support", "Support"], ["admin", "Platform admin"]];

function Frame({ title, lead, children }: { title: string; lead: string; children: ReactNode }) {
  return (
    <main className="vx-app">
      <div className="fixed right-4 top-4 z-10"><ThemeToggle /></div>
      <div className="mx-auto grid min-h-screen max-w-6xl items-center gap-8 px-5 py-10 md:grid-cols-[1.1fr_1fr]">
        <section className="hero-card" style={{ minHeight: 360 }}>
          <p className="eyebrow flex items-center gap-2"><Logo size={22} /> StudEase</p>
          <h1 className="mt-6 text-[clamp(44px,6vw,84px)] uppercase leading-[.95]" style={{ fontFamily: "var(--font-serif)", fontWeight: 400, animation: "wipe 1s var(--ease) both" }}>{title}</h1>
          <p className="mt-4 max-w-md text-lg" style={{ fontFamily: "var(--font-serif)" }}>{lead}</p>
          <p className="note mt-8">Every figure is synthetic. Every balance is checked three ways against an append-only ledger.</p>
        </section>
        <section className="panel">{children}</section>
      </div>
    </main>
  );
}

function Err({ error }: { error: unknown }) {
  return error ? <p role="alert" className="m-0 text-red">{(error as Error).message}</p> : null;
}

export function Login() {
  usePage("Sign in", "Sign in to StudEase to review tuition, scholarships, payments and reconciled student balances.");
  const { me, signIn } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const m = useMutation({ mutationFn: () => signIn(email, password) });
  if (me) return <Navigate to={homeFor(me.role)} replace />;
  const submit = (e: FormEvent) => { e.preventDefault(); m.mutate(); };
  return (
    <Frame title="Tuition, reconciled." lead="Fees, scholarships and payments for ten thousand students, with every balance accounted for.">
      <h2 className="serif m-0 mb-3 text-3xl">Sign in</h2>
      <form onSubmit={submit} className="grid gap-3" aria-label="Sign in">
        <label className="grid gap-1 text-sm font-semibold">Email
          <input className="field" type="email" autoComplete="username" required value={email} onChange={(e) => setEmail(e.target.value)} />
        </label>
        <label className="grid gap-1 text-sm font-semibold">Password
          <input className="field" type="password" autoComplete="current-password" required value={password} onChange={(e) => setPassword(e.target.value)} />
        </label>
        <Err error={m.error} />
        <button className="btn btn-solid" disabled={m.isPending}>{m.isPending && <Spinner />}Sign in</button>
        <Link className="btn" to="/signup">Create a new account</Link>
        <div className="text-center text-sm"><Link to="/forgot">Forgot your password?</Link></div>
      </form>
      <div className="mt-5 border-t border-rule pt-4">
        <p className="eyebrow mb-2">Demo accounts (one per role)</p>
        <div className="flex flex-wrap gap-2">
          {DEMO.map(([name, text]) => <button key={name} type="button" className="chip" aria-pressed={email === `${name}@example.edu`} onClick={() => setEmail(`${name}@example.edu`)}>{text}</button>)}
        </div>
        <p className="note">Pick a role, then enter the demo password you were given.</p>
      </div>
    </Frame>
  );
}

export function Signup() {
  usePage("Create an account", "Create a StudEase learner account: pick a program, then enrol, pay and track your balance.");
  const { me } = useAuth();
  const nav = useNavigate();
  const programs = useQuery({ queryKey: ["public-programs"], queryFn: () => get("/auth/programs") });
  const [f, setF] = useState({ full_name: "", email: "", password: "", program_id: "PRG-01", residency: "DOMESTIC", gpa: "8.0", income_band: "MID", sports_quota: false, hostel_resident: false });
  const set = (k: string, v: string | boolean) => setF((p) => ({ ...p, [k]: v }));
  const m = useMutation({
    mutationFn: () => post<{ token: string }>("/auth/signup", { ...f, gpa: parseFloat(f.gpa) }),
    onSuccess: (r) => { setToken(r.token); window.location.assign("/me"); },
  });
  if (me) return <Navigate to={homeFor(me.role)} replace />;
  void nav;
  return (
    <Frame title="Join in a minute." lead="Create a learner account, enrol in the current term and see your fees, scholarship and balance.">
      <h2 className="serif m-0 mb-3 text-3xl">Create account</h2>
      <form onSubmit={(e) => { e.preventDefault(); m.mutate(); }} className="grid gap-3" aria-label="Create account">
        <label className="grid gap-1 text-sm font-semibold">Full name<input className="field" required minLength={2} maxLength={80} value={f.full_name} onChange={(e) => set("full_name", e.target.value)} /></label>
        <label className="grid gap-1 text-sm font-semibold">Email<input className="field" type="email" autoComplete="username" required value={f.email} onChange={(e) => set("email", e.target.value)} /></label>
        <label className="grid gap-1 text-sm font-semibold">Password (10+ characters)<input className="field" type="password" autoComplete="new-password" required minLength={10} maxLength={128} value={f.password} onChange={(e) => set("password", e.target.value)} /></label>
        <label className="grid gap-1 text-sm font-semibold">Program
          <select className="field" value={f.program_id} onChange={(e) => set("program_id", e.target.value)}>{programs.data?.items.map((p: any) => <option key={p.program_id} value={p.program_id}>{p.name} ({p.level})</option>)}</select></label>
        <div className="grid grid-cols-2 gap-3">
          <label className="grid gap-1 text-sm font-semibold">Residency<select className="field" value={f.residency} onChange={(e) => set("residency", e.target.value)}><option value="DOMESTIC">Domestic</option><option value="INTERNATIONAL">International</option></select></label>
          <label className="grid gap-1 text-sm font-semibold">GPA (0 to 10)<input className="field" inputMode="decimal" required pattern="\d{1,2}(\.\d{1,2})?" value={f.gpa} onChange={(e) => set("gpa", e.target.value)} /></label>
        </div>
        <label className="grid gap-1 text-sm font-semibold">Household income band
          <select className="field" value={f.income_band} onChange={(e) => set("income_band", e.target.value)}>{["LOW", "MID", "HIGH", "AFFLUENT"].map((b) => <option key={b} value={b}>{b.charAt(0) + b.slice(1).toLowerCase()}</option>)}</select></label>
        <div className="flex flex-wrap gap-4 text-sm">
          <label className="flex items-center gap-2"><input type="checkbox" checked={f.sports_quota} onChange={(e) => set("sports_quota", e.target.checked)} />Sports quota</label>
          <label className="flex items-center gap-2"><input type="checkbox" checked={f.hostel_resident} onChange={(e) => set("hostel_resident", e.target.checked)} />Hostel resident</label>
        </div>
        <p className="note m-0">This is a demonstration with synthetic data: use a throwaway email and password.</p>
        <Err error={m.error} />
        <button className="btn btn-solid" disabled={m.isPending}>{m.isPending && <Spinner />}Create account</button>
        <Link to="/login" className="text-sm">I already have an account</Link>
      </form>
    </Frame>
  );
}

export function Forgot() {
  usePage("Forgot password", "Request a StudEase password reset link by email.");
  const [email, setEmail] = useState("");
  const m = useMutation({ mutationFn: () => post<{ message: string }>("/auth/forgot", { email }) });
  return (
    <Frame title="Reset access." lead="Enter your email. If it has an account, a single-use link arrives within a minute.">
      <form onSubmit={(e) => { e.preventDefault(); m.mutate(); }} className="grid gap-3">
        <label className="grid gap-1 text-sm font-semibold">Email
          <input className="field" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
        </label>
        {m.isSuccess && <p role="status" className="m-0 text-green">{m.data.message}</p>}
        <Err error={m.error} />
        <button className="btn btn-solid" disabled={m.isPending}>{m.isPending && <Spinner />}Send link</button>
        <Link to="/login" className="text-sm">Back to sign in</Link>
      </form>
    </Frame>
  );
}

export function Reset() {
  usePage("Choose a new password", "Set a new StudEase password using your single-use reset link.");
  const [params] = useSearchParams();
  const nav = useNavigate();
  const [password, setPassword] = useState("");
  const m = useMutation({ mutationFn: () => post("/auth/reset", { token: params.get("token") ?? "", new_password: password }), onSuccess: () => setTimeout(() => nav("/login"), 1200) });
  return (
    <Frame title="New password." lead="Use at least 12 characters. The link works once and expires in 30 minutes.">
      <form onSubmit={(e) => { e.preventDefault(); m.mutate(); }} className="grid gap-3">
        <label className="grid gap-1 text-sm font-semibold">New password
          <input className="field" type="password" autoComplete="new-password" minLength={12} maxLength={128} required value={password} onChange={(e) => setPassword(e.target.value)} />
        </label>
        {m.isSuccess && <p role="status" className="m-0 text-green">Password changed. Taking you to sign in...</p>}
        <Err error={m.error} />
        <button className="btn btn-solid" disabled={m.isPending || m.isSuccess}>{m.isPending && <Spinner />}Change password</button>
      </form>
    </Frame>
  );
}
