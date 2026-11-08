import {
  Link,
  Outlet,
  createRootRouteWithContext,
} from "@tanstack/react-router";
import type { AppRouterContext } from "@/main";
import { ReactQueryDevtools } from "@tanstack/react-query-devtools";
import { TanStackRouterDevtools } from "@tanstack/react-router-devtools";
import { ErrorComponent } from "@/components/ErrorComponent";
import { NotFoundComponent } from "@/components/NotFoundComponent";

export const Route = createRootRouteWithContext<AppRouterContext>()({
  component: RootComponent,
  notFoundComponent: NotFoundComponent,
  errorComponent: ErrorComponent,
});

function RootComponent() {
  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-5 py-4 sm:px-8">
          <Link to="/" className="font-semibold tracking-tight text-slate-950">
            Shiny Learning
          </Link>
          <nav className="flex items-center gap-5 text-sm font-medium text-slate-600">
            <Link to="/" className="hover:text-indigo-700">
              Courses
            </Link>
            <Link to="/my-learning" className="hover:text-indigo-700">
              My learning
            </Link>
            <Link to="/login" className="hover:text-indigo-700">
              Email sign in
            </Link>
          </nav>
        </div>
      </header>
      <Outlet />
      {import.meta.env.DEV && (
        <>
          <ReactQueryDevtools />
          <TanStackRouterDevtools />
        </>
      )}
    </div>
  );
}
