import { Link, isRouteErrorResponse, useRouteError } from "react-router";
import { homeFor } from "../components/Shell";
import { useAuth } from "../lib/auth";
import { usePage } from "../lib/page";

function Page({ code, title, text, children }: { code: string; title: string; text: string; children?: React.ReactNode }) {
  return (
    <main className="mx-auto grid min-h-[70vh] max-w-2xl content-center gap-4 px-5 py-16">
      <div className="margin-rule">
        <p className="eyebrow m-0">Error {code}</p>
        <h1 className="display">{title}</h1>
        <p className="max-w-md text-muted">{text}</p>
        <div className="flex flex-wrap gap-3">{children}</div>
      </div>
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
