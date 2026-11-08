import {
  Link,
  Outlet,
  createRootRouteWithContext,
  useNavigate,
} from "@tanstack/react-router";
import type { AppRouterContext } from "@/main";
import { ReactQueryDevtools } from "@tanstack/react-query-devtools";
import { TanStackRouterDevtools } from "@tanstack/react-router-devtools";
import { ErrorComponent } from "@/components/ErrorComponent";
import { NotFoundComponent } from "@/components/NotFoundComponent";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { fetchProfile, profileQueryKey, signOut } from "@/lib/profile";

export const Route = createRootRouteWithContext<AppRouterContext>()({
  component: RootComponent,
  notFoundComponent: NotFoundComponent,
  errorComponent: ErrorComponent,
});

function RootComponent() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const profile = useQuery({
    queryKey: profileQueryKey,
    queryFn: fetchProfile,
  });
  const signOutMutation = useMutation({
    mutationFn: signOut,
    onSuccess: async () => {
      await queryClient.cancelQueries();
      queryClient.removeQueries({
        predicate: (query) => query.queryKey[0] !== profileQueryKey[0],
      });
      queryClient.setQueryData(profileQueryKey, null);
      await navigate({ to: "/" });
    },
  });

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
            {profile.data ? (
              <>
                <span className="hidden text-slate-500 sm:inline">
                  {profile.data.email}
                </span>
                <button
                  type="button"
                  onClick={() => signOutMutation.mutate()}
                  disabled={signOutMutation.isPending}
                  className="hover:text-indigo-700 disabled:cursor-wait disabled:opacity-60"
                >
                  {signOutMutation.isPending ? "Signing out…" : "Sign out"}
                </button>
              </>
            ) : (
              <Link to="/login" className="hover:text-indigo-700">
                Email sign in
              </Link>
            )}
          </nav>
        </div>
      </header>
      {signOutMutation.isError && (
        <p
          role="alert"
          className="mx-auto max-w-6xl px-5 pt-4 text-sm text-red-700 sm:px-8"
        >
          {signOutMutation.error.message}
        </p>
      )}
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
