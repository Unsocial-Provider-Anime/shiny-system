import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createFileRoute, Link } from "@tanstack/react-router";
import {
  apiRequest,
  lessonCount,
  LearningSessionSchema,
} from "@/lib/api";

export const Route = createFileRoute("/learning-sessions/$sessionId")({
  component: LearningSessionPage,
});

function LearningSessionPage() {
  const { sessionId } = Route.useParams();
  const queryClient = useQueryClient();
  const sessionKey = ["learning-session", sessionId];
  const session = useQuery({
    queryKey: sessionKey,
    queryFn: () =>
      apiRequest(
        `/api/v1/learning-sessions/${sessionId}`,
        LearningSessionSchema,
      ),
  });
  const complete = useMutation({
    mutationFn: (lessonId: string) =>
      apiRequest(
        `/api/v1/learning-sessions/${sessionId}/lessons/${lessonId}/complete`,
        LearningSessionSchema,
        { method: "POST" },
      ),
    onSuccess: async (updatedSession) => {
      queryClient.setQueryData(sessionKey, updatedSession);
      await queryClient.invalidateQueries({ queryKey: ["learning-sessions"] });
    },
  });

  if (session.isPending) {
    return <main className="mx-auto max-w-5xl px-5 py-12">Loading your lesson…</main>;
  }
  if (session.isError) {
    return (
      <main className="mx-auto max-w-5xl px-5 py-12">
        <p role="alert" className="rounded-xl bg-red-50 p-4 text-red-800">
          {session.error.message}
        </p>
      </main>
    );
  }

  const data = session.data;
  const totalLessons = lessonCount(data.plan);
  const completedLessons = data.completed_lessons.length;
  const currentModule = data.plan.modules.find(
    (module) => module.module_id === data.current_module_id,
  );
  const currentLesson = currentModule?.lessons.find(
    (lesson) => lesson.lesson_id === data.current_lesson_id,
  );

  return (
    <main className="mx-auto grid max-w-6xl gap-8 px-5 py-10 lg:grid-cols-[280px_minmax(0,1fr)] sm:px-8">
      <aside>
        <Link to="/my-learning" className="text-sm font-semibold text-indigo-700">
          ← My learning
        </Link>
        <h1 className="mt-5 text-xl font-semibold text-slate-950">
          {data.course.title}
        </h1>
        <p className="mt-2 text-sm text-slate-600">
          {completedLessons} of {totalLessons} lessons complete
        </p>
        <div className="mt-4 h-2 overflow-hidden rounded-full bg-slate-200">
          <div
            className="h-full rounded-full bg-indigo-600"
            style={{
              width: `${totalLessons === 0 ? 0 : (completedLessons / totalLessons) * 100}%`,
            }}
          />
        </div>
        <nav className="mt-7 space-y-5">
          {data.plan.modules.map((module) => (
            <section key={module.module_id}>
              <h2 className="text-sm font-semibold text-slate-700">
                {module.title}
              </h2>
              <ol className="mt-2 space-y-1">
                {module.lessons.map((lesson) => {
                  const done = data.completed_lessons.some(
                    (item) => item.lesson_id === lesson.lesson_id,
                  );
                  const current = lesson.lesson_id === data.current_lesson_id;
                  return (
                    <li
                      key={lesson.lesson_id}
                      className={`rounded-lg px-3 py-2 text-sm ${
                        current
                          ? "bg-indigo-50 font-semibold text-indigo-800"
                          : done
                            ? "text-emerald-700"
                            : "text-slate-500"
                      }`}
                    >
                      {done ? "✓ " : ""}
                      {lesson.title}
                    </li>
                  );
                })}
              </ol>
            </section>
          ))}
        </nav>
      </aside>

      <section className="min-w-0">
        {data.status === "completed" || !currentLesson ? (
          <div className="rounded-3xl border border-emerald-200 bg-emerald-50 p-8 sm:p-12">
            <p className="text-sm font-semibold uppercase tracking-[0.15em] text-emerald-700">
              Course complete
            </p>
            <h2 className="mt-3 text-3xl font-semibold text-slate-950">
              Nicely done.
            </h2>
            <p className="mt-4 leading-7 text-slate-700">
              You completed all {totalLessons} lessons in this course.
            </p>
            <Link
              to="/my-learning"
              className="mt-6 inline-block rounded-xl bg-emerald-700 px-5 py-3 font-semibold text-white hover:bg-emerald-800"
            >
              Back to my learning
            </Link>
          </div>
        ) : (
          <article className="rounded-3xl border border-slate-200 bg-white p-7 shadow-sm sm:p-10">
            <p className="text-sm font-semibold uppercase tracking-[0.15em] text-indigo-600">
              {currentModule?.title}
              {currentLesson.estimated_minutes
                ? ` · ${currentLesson.estimated_minutes} min`
                : ""}
            </p>
            <h2 className="mt-3 text-3xl font-semibold tracking-tight text-slate-950">
              {currentLesson.title}
            </h2>
            <p className="mt-5 text-lg leading-8 text-slate-700">
              {currentLesson.purpose}
            </p>

            <section className="mt-8 rounded-2xl bg-slate-50 p-6">
              <h3 className="font-semibold text-slate-950">By the end, you can</h3>
              <ul className="mt-3 space-y-2 text-slate-700">
                {currentLesson.objectives.map((objective) => (
                  <li key={objective} className="flex gap-3 leading-7">
                    <span className="text-indigo-600">•</span>
                    {objective}
                  </li>
                ))}
              </ul>
            </section>
            <section className="mt-7">
              <h3 className="font-semibold text-slate-950">Key topics</h3>
              <ul className="mt-3 flex flex-wrap gap-2">
                {currentLesson.key_topics.map((topic) => (
                  <li
                    key={topic}
                    className="rounded-full bg-indigo-50 px-3 py-1.5 text-sm text-indigo-800"
                  >
                    {topic}
                  </li>
                ))}
              </ul>
            </section>
            <section className="mt-7 rounded-2xl border border-indigo-100 p-5">
              <h3 className="font-semibold text-slate-950">Completion check</h3>
              <p className="mt-2 leading-7 text-slate-700">
                {currentLesson.completion_check}
              </p>
              <p className="mt-3 text-sm text-slate-500">
                When you’re ready, mark this lesson complete. Your next lesson
                will be saved automatically.
              </p>
            </section>

            {complete.isError && (
              <p role="alert" className="mt-5 rounded-xl bg-red-50 p-4 text-red-800">
                {complete.error.message}
              </p>
            )}
            <button
              type="button"
              onClick={() => complete.mutate(currentLesson.lesson_id)}
              disabled={complete.isPending}
              className="mt-7 rounded-xl bg-indigo-600 px-6 py-3 font-semibold text-white hover:bg-indigo-700 disabled:cursor-wait disabled:opacity-60"
            >
              {complete.isPending ? "Saving progress…" : "Mark lesson complete"}
            </button>
          </article>
        )}
      </section>
    </main>
  );
}
