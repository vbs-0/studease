import { useMutation } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Link, Navigate, useNavigate, useSearchParams } from "react-router";
import { ThemeToggle, homeFor } from "../components/Shell";
import { Spinner } from "../components/ui";
import { post } from "../lib/api";
import { useAuth } from "../lib/auth";
import { usePage } from "../lib/page";

const DEMO = [["learner", "Learner"], ["instructor", "Instructor"], ["academic", "Academic admin"], ["support", "Support"], ["admin", "Platform admin"]];

function Frame({ title, lead, children }: { title: string; lead: string; children: React.ReactNode }) {
  return (
    <main className="mx-auto grid min-h-screen max-w-5xl items-center gap-10 px-5 py-10 md:grid-cols-2">
      <section className="margin-rule">
        <p className="eyebrow m-0">StudEase</p>
        <h1 className="display">{title}</h1>
        <p className="max-w-md text-muted">{lead}</p>
        <p className="text-sm text-muted">Every figure here is synthetic. Every balance is checked three ways against an append-only ledger.</p>
      </section>
      <section className="panel">{children}</section>
      <div className="fixed right-4 top-4"><ThemeToggle /></div>
    </main>
  );
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
      <form onSubmit={submit} className="grid gap-3" aria-label="Sign in">
        <label className="grid gap-1 text-sm font-semibold">Email
          <input className="field" type="email" autoComplete="username" required value={email} onChange={(e) => setEmail(e.target.value)} />
        </label>
        <label className="grid gap-1 text-sm font-semibold">Password
          <input className="field" type="password" autoComplete="current-password" required value={password} onChange={(e) => setPassword(e.target.value)} />
        </label>
        {m.isError && <p role="alert" className="m-0 text-red">{(m.error as Error).message}</p>}
        <button className="btn btn-solid" disabled={m.isPending}>{m.isPending && <Spinner />}Sign in</button>
        <Link to="/forgot" className="text-sm">Forgot your password?</Link>
      </form>
      <div className="mt-5 border-t border-rule pt-4">
        <p className="eyebrow m-0 mb-2">Demo accounts (one per role)</p>
        <div className="flex flex-wrap gap-2">
          {DEMO.map(([name, text]) => <button key={name} type="button" className="btn" onClick={() => setEmail(`${name}@example.edu`)}>{text}</button>)}
        </div>
        <p className="mb-0 mt-2 text-sm text-muted">Pick a role, then enter the demo password you were given.</p>
      </div>
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
        {m.isError && <p role="alert" className="m-0 text-red">{(m.error as Error).message}</p>}
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
        {m.isError && <p role="alert" className="m-0 text-red">{(m.error as Error).message}</p>}
        <button className="btn btn-solid" disabled={m.isPending || m.isSuccess}>{m.isPending && <Spinner />}Change password</button>
      </form>
    </Frame>
  );
}
