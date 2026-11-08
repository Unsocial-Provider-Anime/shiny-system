import { useQuery } from "@tanstack/react-query";
import { createFileRoute, Link } from "@tanstack/react-router";
import { apiRequest, CourseSchema } from "@/lib/api";
import { fetchProfile, profileQueryKey } from "@/lib/profile";

export const Route = createFileRoute("/")({
  component: CataloguePage,
});

function CataloguePage() {
  const profile = useQuery({ queryKey: profileQueryKey, queryFn: fetchProfile });
  const courses = useQuery({
    queryKey: ["courses"],
    queryFn: () =>
      apiRequest("/api/v1/courses", CourseSchema.array()),
  });

  return (
    <main className="mx-auto max-w-6xl px-5 py-12 sm:px-8">
      <section className="mb-12 rounded-3xl bg-indigo-950 px-7 py-10 text-white sm:px-12 sm:py-14">
        <p className="text-sm font-semibold uppercase tracking-[0.18em] text-indigo-300">
          Learn by doing
        </p>
        <h1 className="mt-4 max-w-2xl text-4xl font-semibold tracking-tight sm:text-5xl">
          Small courses. Real progress.
        </h1>
        <p className="mt-5 max-w-2xl text-lg leading-8 text-indigo-100">
          Explore a course, follow its lessons, and pick up where you left off.
        </p>
        <div className="mt-8 flex flex-wrap gap-3">
          {profile.data ? (
            <>
              <Link
                to="/my-learning"
                className="rounded-xl bg-white px-5 py-3 font-semibold text-indigo-950 hover:bg-indigo-50"
              >
                My learning
              </Link>
              <Link
                to="/create-course"
                className="rounded-xl border border-indigo-300 px-5 py-3 font-semibold text-white hover:bg-indigo-900"
              >
                Create a course
              </Link>
            </>
          ) : (
            <Link
              to="/login"
              className="rounded-xl bg-white px-5 py-3 font-semibold text-indigo-950 hover:bg-indigo-50"
            >
              Continue with email
            </Link>
          )}
        </div>
      </section>

      <div className="mb-6 flex items-end justify-between gap-4">
        <div>
          <p className="text-sm font-semibold uppercase tracking-[0.15em] text-indigo-600">
            Course catalogue
          </p>
          <h2 className="mt-2 text-2xl font-semibold text-slate-950">
            Find your next skill
          </h2>
        </div>
        {profile.data && (
          <Link
            to="/my-learning"
            className="text-sm font-semibold text-indigo-700 hover:text-indigo-900"
          >
            View my learning →
          </Link>
        )}
      </div>

      {courses.isPending && <p className="text-slate-600">Loading courses…</p>}
      {courses.isError && (
        <p role="alert" className="rounded-xl bg-red-50 p-4 text-red-800">
          {courses.error.message}
        </p>
      )}
      {courses.data?.length === 0 && (
        <p className="rounded-2xl border border-dashed border-slate-300 p-8 text-slate-600">
          No published courses yet. Check back soon.
        </p>
      )}
      {courses.data && courses.data.length > 0 && (
        <div className="grid gap-5 md:grid-cols-2 lg:grid-cols-3">
          {courses.data.map((course) => (
            <Link
              key={course.id}
              to="/courses/$courseId"
              params={{ courseId: course.id }}
              className="group rounded-2xl border border-slate-200 bg-white p-6 shadow-sm transition hover:-translate-y-0.5 hover:border-indigo-300 hover:shadow-md"
            >
              <p className="text-sm font-medium text-indigo-700">
                {course.plan.modules.length} modules ·{" "}
                {course.plan.modules.reduce(
                  (count, module) => count + module.lessons.length,
                  0,
                )}{" "}
                lessons
              </p>
              <h3 className="mt-3 text-xl font-semibold text-slate-950 group-hover:text-indigo-800">
                {course.title}
              </h3>
              <p className="mt-3 line-clamp-3 leading-7 text-slate-600">
                {course.description}
              </p>
              <span className="mt-5 inline-block font-semibold text-indigo-700">
                View course →
              </span>
            </Link>
          ))}
        </div>
      )}
    </main>
  );
}
