import { Moon, Sun } from "lucide-react";
import { useEffect, useState } from "react";
import { NavLink, Outlet } from "react-router";
import { useAuth, type Role } from "../lib/auth";
import { label } from "../lib/format";

interface Item { to: string; text: string; roles: Role[] }
const ALL: Role[] = ["LEARNER", "INSTRUCTOR", "ACADEMIC_ADMIN", "SUPPORT", "PLATFORM_ADMIN"];
const FINANCE: Role[] = ["ACADEMIC_ADMIN", "SUPPORT", "PLATFORM_ADMIN"];
const NAV: Item[] = [
  { to: "/", text: "Overview", roles: FINANCE },
  { to: "/me", text: "My account", roles: ["LEARNER"] },
  { to: "/students", text: "Students", roles: ["INSTRUCTOR", ...FINANCE] },
  { to: "/fees", text: "Fee schedules", roles: FINANCE },
  { to: "/scholarships", text: "Scholarships", roles: FINANCE },
  { to: "/exceptions", text: "Exceptions", roles: ["SUPPORT", "PLATFORM_ADMIN"] },
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
  return <button className="btn" onClick={toggle} aria-label={dark ? "Switch to light theme" : "Switch to dark theme"}>{dark ? <Sun size={16} /> : <Moon size={16} />}</button>;
}

export default function Shell() {
  const { me, signOut } = useAuth();
  if (!me) return null;
  const items = NAV.filter((i) => i.roles.includes(me.role) && ALL.includes(me.role));
  return (
    <>
      <a className="skip" href="#main">Skip to content</a>
      <div className="border-b border-rule-strong bg-sheet">
        <div className="mx-auto flex max-w-[1280px] flex-wrap items-center gap-x-5 gap-y-2 px-4 py-3 md:px-8">
          <NavLink to={homeFor(me.role)} className="serif text-2xl text-ink no-underline">StudEase</NavLink>
          <nav aria-label="Main" className="flex flex-wrap gap-x-4 gap-y-1">
            {items.map((i) => (
              <NavLink key={i.to} to={i.to} end={i.to === "/"} className={({ isActive }) => `text-sm font-semibold no-underline ${isActive ? "text-ink underline" : "text-muted"}`}>{i.text}</NavLink>
            ))}
          </nav>
          <div className="ml-auto flex items-center gap-2">
            <span className="hidden text-sm text-muted sm:inline">{me.email} <span className="stamp stamp-mute">{label(me.role)}</span></span>
            <ThemeToggle />
            <button className="btn" onClick={signOut}>Sign out</button>
          </div>
        </div>
      </div>
      <main id="main" className="wrap"><Outlet /></main>
    </>
  );
}
