import { LogOut, Moon, Sun } from "lucide-react";
import { Suspense, useEffect, useState } from "react";
import { NavLink, Outlet } from "react-router";
import { useAuth, type Role } from "../lib/auth";
import { label } from "../lib/format";
import { initMotion } from "../lib/motion";
import { Logo, PageLoading, Toaster, TopBar } from "./ui";

interface Item { to: string; text: string; roles: Role[]; end?: boolean }
const FINANCE: Role[] = ["ACADEMIC_ADMIN", "SUPPORT", "PLATFORM_ADMIN"];
const NAV: Item[] = [
  { to: "/", text: "Overview", roles: FINANCE, end: true },
  { to: "/me", text: "Account", roles: ["LEARNER"], end: true },
  { to: "/me/enroll", text: "Enroll", roles: ["LEARNER"] },
  { to: "/me/scholarships", text: "Scholarships", roles: ["LEARNER"] },
  { to: "/me/fees", text: "Fees", roles: ["LEARNER"] },
  { to: "/students", text: "Students", roles: ["INSTRUCTOR", ...FINANCE] },
  { to: "/fees", text: "Fee schedules", roles: FINANCE },
  { to: "/scholarships", text: "Scholarships", roles: FINANCE },
  { to: "/exceptions", text: "Exceptions", roles: ["SUPPORT", "PLATFORM_ADMIN"] },
  { to: "/users", text: "Users", roles: ["PLATFORM_ADMIN"] },
  { to: "/quality", text: "Data quality", roles: ["PLATFORM_ADMIN"] },
];
export const homeFor = (r: Role) => (r === "LEARNER" ? "/me" : r === "INSTRUCTOR" ? "/students" : "/");

function useTheme() {
  const [theme, setTheme] = useState<string | null>(() => { try { return localStorage.getItem("studease.theme"); } catch { return null; } });
  useEffect(() => {
    if (theme) document.documentElement.setAttribute("data-theme", theme);
    else document.documentElement.removeAttribute("data-theme");
    try { if (theme) localStorage.setItem("studease.theme", theme); } catch { /* storage blocked */ }
  }, [theme]);
  const dark = theme ? theme === "dark" : window.matchMedia("(prefers-color-scheme: dark)").matches;
  return { dark, toggle: () => setTheme(dark ? "light" : "dark") };
}

export function ThemeToggle() {
  const { dark, toggle } = useTheme();
  return <button className="vx-icon" onClick={toggle} aria-label={dark ? "Switch to light theme" : "Switch to dark theme"}>{dark ? <Sun size={16} /> : <Moon size={16} />}</button>;
}

export default function Shell() {
  const { me, signOut } = useAuth();
  useEffect(() => initMotion(), []);
  if (!me) return null;
  const items = NAV.filter((i) => i.roles.includes(me.role));
  return (
    <div className="vx-app">
      <a className="skip" href="#main">Skip to content</a>
      <div className="vx-progress" aria-hidden="true" />
      <TopBar />
      <header className="vx-head no-print">
        <NavLink to={homeFor(me.role)} className="vx-brand"><Logo size={30} /><span>StudEase</span></NavLink>
        <nav aria-label="Main" className="vx-nav">
          {items.map((i) => <NavLink key={i.to} to={i.to} end={i.end} className={({ isActive }) => `vx-link ${isActive ? "active" : ""}`}>{i.text}</NavLink>)}
        </nav>
        <div className="vx-actions">
          <span className="vx-who" title={me.email}>{label(me.role)}</span>
          <ThemeToggle />
          <button className="vx-pill" onClick={signOut}><LogOut size={15} aria-hidden />Sign out</button>
        </div>
      </header>
      <main id="main" className="vx-wrap"><Suspense fallback={<PageLoading />}><Outlet /></Suspense></main>
      <Toaster />
    </div>
  );
}
