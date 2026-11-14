import { lazy } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Navigate, Outlet, RouterProvider, createBrowserRouter } from "react-router";
import Shell, { homeFor } from "./components/Shell";
import { Splash } from "./components/ui";
import { ApiError } from "./lib/api";
import { AuthProvider, useAuth, type Role } from "./lib/auth";
import { Forbidden, NotFound, RouteError } from "./pages/ErrorPages";
import { Forgot, Login, Reset, Signup } from "./pages/Auth";

// Route-level code splitting: each page is its own chunk, fetched the first time it is visited.
const page = <T extends Record<string, any>>(load: () => Promise<T>, key: keyof T) => lazy(() => load().then((m) => ({ default: m[key] })));
const Fees = page(() => import("./pages/Catalog"), "Fees");
const Scholarships = page(() => import("./pages/Catalog"), "Scholarships");
const Exceptions = page(() => import("./pages/Exceptions"), "default");
const Enroll = page(() => import("./pages/Learner"), "Enroll");
const MyFees = page(() => import("./pages/Learner"), "MyFees");
const MyScholarships = page(() => import("./pages/Learner"), "MyScholarships");
const InvoicePage = page(() => import("./pages/InvoicePage"), "default");
const Overview = page(() => import("./pages/Overview"), "default");
const Quality = page(() => import("./pages/Quality"), "default");
const MyAccount = page(() => import("./pages/StudentPage"), "MyAccount");
const StudentRoute = page(() => import("./pages/StudentPage"), "default");
const Students = page(() => import("./pages/Students"), "default");
const AddStudent = page(() => import("./pages/Admin"), "AddStudent");
const Users = page(() => import("./pages/Admin"), "Users");

const client = new QueryClient({
  defaultOptions: { queries: { staleTime: 30_000, refetchOnWindowFocus: false, retry: (n, e) => !(e instanceof ApiError && e.status < 500 && e.status !== 0) && n < 2 } },
});

/** Signed-out visitors go to /login; a role not in `roles` sees the 403 page. */
function Guard({ roles }: { roles?: Role[] }) {
  const { me, loading } = useAuth();
  if (loading) return <Splash />;
  if (!me) return <Navigate to="/login" replace />;
  if (roles && !roles.includes(me.role)) return <Forbidden />;
  return <Outlet />;
}

function Home() {
  const { me } = useAuth();
  return <Navigate to={me ? homeFor(me.role) : "/login"} replace />;
}

const FINANCE: Role[] = ["ACADEMIC_ADMIN", "SUPPORT", "PLATFORM_ADMIN"];
const router = createBrowserRouter([
  { path: "/login", element: <Login />, errorElement: <RouteError /> },
  { path: "/signup", element: <Signup />, errorElement: <RouteError /> },
  { path: "/forgot", element: <Forgot /> },
  { path: "/reset", element: <Reset /> },
  {
    element: <Guard />, errorElement: <RouteError />,
    children: [{
      element: <Shell />,
      children: [
        { path: "/", element: <Guard roles={FINANCE} />, children: [{ index: true, element: <Overview /> }] },
        { path: "/home", element: <Home /> },
        { path: "/me", element: <Guard roles={["LEARNER"]} />, children: [
          { index: true, element: <MyAccount /> }, { path: "enroll", element: <Enroll /> },
          { path: "scholarships", element: <MyScholarships /> }, { path: "fees", element: <MyFees /> }] },
        { path: "/students", element: <Guard roles={["INSTRUCTOR", ...FINANCE]} />, children: [{ index: true, element: <Students /> }, { path: "new", element: <Guard roles={FINANCE} />, children: [{ index: true, element: <AddStudent /> }] }, { path: ":id", element: <StudentRoute /> }] },
        { path: "/invoices/:id", element: <Guard roles={["LEARNER", ...FINANCE]} />, children: [{ index: true, element: <InvoicePage /> }] },
        { path: "/fees", element: <Guard roles={FINANCE} />, children: [{ index: true, element: <Fees /> }] },
        { path: "/scholarships", element: <Guard roles={FINANCE} />, children: [{ index: true, element: <Scholarships /> }] },
        { path: "/exceptions", element: <Guard roles={["SUPPORT", "PLATFORM_ADMIN"]} />, children: [{ index: true, element: <Exceptions /> }] },
        { path: "/users", element: <Guard roles={["PLATFORM_ADMIN"]} />, children: [{ index: true, element: <Users /> }] },
        { path: "/quality", element: <Guard roles={["PLATFORM_ADMIN"]} />, children: [{ index: true, element: <Quality /> }] },
      ],
    }],
  },
  { path: "*", element: <NotFound /> },
]);

export default function App() {
  return (
    <QueryClientProvider client={client}>
      <AuthProvider><RouterProvider router={router} /></AuthProvider>
    </QueryClientProvider>
  );
}
