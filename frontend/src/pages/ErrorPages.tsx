import { Link, isRouteErrorResponse, useRouteError } from "react-router";
import { homeFor } from "../components/Shell";
import { useAuth } from "../lib/auth";
import { usePage } from "../lib/page";

function Page({ code, title, text, children }: { code: string; title: string; text: string; children?: React.ReactNode }) {
  return (
    <main className="vx-app grid min-h-screen place-items-center px-5 py-16">
      <section className="hero-card w-full max-w-2xl">
        <p className="eyebrow">Error {code}</p>
        <h1 className="mt-4 text-[clamp(48px,9vw,110px)] uppercase leading-[.92]" style={{ fontFamily: "var(--font-serif)", fontWeight: 400, animation: "wipe 1s var(--ease) both" }}>{title}</h1>
        <p className="mt-3 max-w-md text-lg" style={{ fontFamily: "var(--font-serif)" }}>{text}</p>
        <div className="mt-6 flex flex-wrap gap-3">{children}</div>
      </section>
    </main>
  );
}

function Home() {
  const { me } = useAuth();
  return <Link className="btn btn-solid" to={me ? homeFor(me.role) : "/login"}>{me ? "Back to your home page" : "Go to sign in"}</Link>;
}

export function NotFound() {
  usePage("Page not found", "The page you asked for does not exist.");
  return <Page code="404" title="Not found." text="That page does not exist, or the link is out of date."><Home /></Page>;
}

export function Forbidden() {
  usePage("Not allowed", "Your role cannot open this page.");
  return <Page code="403" title="Not for your role." text="Your account is not allowed to open this page. Staff roles see different parts of the system."><Home /></Page>;
}

/** React Router errorElement: a render crash or a failed route shows this instead of a blank screen. */
export function RouteError() {
  const err = useRouteError();
  usePage("Something went wrong", "An unexpected error occurred.");
  if (isRouteErrorResponse(err) && err.status === 404) return <NotFound />;
  return (
    <Page code="500" title="Something broke." text="The page hit an unexpected error. Reloading usually fixes it; if not, tell us what you were doing.">
      <button className="btn btn-solid" onClick={() => location.reload()}>Reload</button><Home />
    </Page>
  );
}
