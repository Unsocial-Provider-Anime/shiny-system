import { useMutation, useQuery } from "@tanstack/react-query";
import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import {
  apiRequest,
  CourseSchema,
  LearningSessionSchema,
} from "@/lib/api";

export const Route = createFileRoute("/courses/$courseId")({
  component: CourseDetailPage,
});

function CourseDetailPage() {
  const { courseId } = Route.useParams();
  const navigate = useNavigate();
  const course = useQuery({
    queryKey: ["course", courseId],
    queryFn: () =>
      apiRequest(`/api/v1/courses/${courseId}`, CourseSchema),
  });
  const start = useMutation({
    mutationFn: () =>
      apiRequest("/api/v1/learning-sessions", LearningSessionSchema, {
        method: "POST",
        body: JSON.stringify({ course_id: courseId }),
      }),
    onSuccess: async (session) => {
      await navigate({
        to: "/learning-sessions/$sessionId",
        params: { sessionId: session.id },
      });
    },
  });

  if (course.isPending) {
    return <main className="mx-auto max-w-4xl px-5 py-12">Loading course…</main>;
  }
  if (course.isError) {
    return (
      <main className="mx-auto max-w-4xl px-5 py-12">
        <p role="alert" className="rounded-xl bg-red-50 p-4 text-red-800">
          {course.error.message}
        </p>
      </main>
    );
  }

  return (
    <main className="mx-auto max-w-4xl px-5 py-12 sm:px-8">
      <Link to="/" className="text-sm font-semibold text-indigo-700">
        ← Course catalogue
      </Link>
      <header className="mt-7">
        <p className="text-sm font-semibold uppercase tracking-[0.15em] text-indigo-600">
          {course.data.plan.target_audience}
        </p>
        <h1 className="mt-3 text-4xl font-semibold tracking-tight text-slate-950">
          {course.data.title}
        </h1>
        <p className="mt-5 text-lg leading-8 text-slate-600">
          {course.data.description}
        </p>
      </header>

      <section className="mt-9 rounded-2xl border border-slate-200 bg-white p-6">
        <h2 className="text-xl font-semibold text-slate-950">What you’ll learn</h2>
        <ul className="mt-4 space-y-3">
          {course.data.plan.learning_outcomes.map((outcome) => (
            <li key={outcome} className="flex gap-3 leading-7 text-slate-700">
              <span className="text-indigo-600">✓</span>
              {outcome}
            </li>
          ))}
        </ul>
      </section>

      <section className="mt-8">
        <h2 className="text-2xl font-semibold text-slate-950">Course plan</h2>
        <div className="mt-4 space-y-4">
          {course.data.plan.modules.map((module, index) => (
            <article
              key={module.module_id}
              className="rounded-2xl border border-slate-200 bg-white p-6"
            >
              <p className="text-sm font-medium text-indigo-700">
                Module {index + 1}
              </p>
              <h3 className="mt-1 text-lg font-semibold text-slate-950">
                {module.title}
              </h3>
              <p className="mt-2 text-slate-600">{module.description}</p>
              <ol className="mt-4 list-inside list-decimal space-y-2 text-slate-700">
                {module.lessons.map((lesson) => (
                  <li key={lesson.lesson_id}>{lesson.title}</li>
                ))}
              </ol>
            </article>
          ))}
        </div>
      </section>

      <div className="mt-8">
        {start.isError && (
          <p role="alert" className="mb-4 rounded-xl bg-red-50 p-4 text-red-800">
            {start.error.message}
          </p>
        )}
        <button
          type="button"
          onClick={() => start.mutate()}
          disabled={start.isPending}
          className="rounded-xl bg-indigo-600 px-6 py-3 font-semibold text-white hover:bg-indigo-700 disabled:cursor-wait disabled:opacity-60"
        >
          {start.isPending ? "Opening course…" : "Start or resume learning"}
        </button>
      </div>
    </main>
  );
}
