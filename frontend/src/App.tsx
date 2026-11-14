import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Navigate, Outlet, RouterProvider, createBrowserRouter } from "react-router";
import Shell, { homeFor } from "./components/Shell";
import { Splash } from "./components/ui";
import { ApiError } from "./lib/api";
import { AuthProvider, useAuth, type Role } from "./lib/auth";
import { Fees, Scholarships } from "./pages/Catalog";
import { Forbidden, NotFound, RouteError } from "./pages/ErrorPages";
import { AddStudent, Users } from "./pages/Admin";
import Exceptions from "./pages/Exceptions";
import { Forgot, Login, Reset, Signup } from "./pages/Auth";
import { Enroll, MyFees, MyScholarships } from "./pages/Learner";
import InvoicePage from "./pages/InvoicePage";
import Overview from "./pages/Overview";
import Quality from "./pages/Quality";
import { MyAccount } from "./pages/StudentPage";
import StudentRoute from "./pages/StudentPage";
import Students from "./pages/Students";

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
