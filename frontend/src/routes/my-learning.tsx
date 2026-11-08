import { useQuery } from "@tanstack/react-query";
import { createFileRoute, Link } from "@tanstack/react-router";
import {
  apiRequest,
  lessonById,
  lessonCount,
  LearningSessionSchema,
} from "@/lib/api";

export const Route = createFileRoute("/my-learning")({
  component: MyLearningPage,
});

function MyLearningPage() {
  const sessions = useQuery({
    queryKey: ["learning-sessions"],
    queryFn: () =>
      apiRequest("/api/v1/learning-sessions", LearningSessionSchema.array()),
  });

  return (
    <main className="mx-auto max-w-5xl px-5 py-12 sm:px-8">
      <Link to="/" className="text-sm font-semibold text-indigo-700">
        ← Course catalogue
      </Link>
      <h1 className="mt-6 text-3xl font-semibold text-slate-950">My learning</h1>
      <p className="mt-2 text-slate-600">
        Your course progress is saved here so you can continue later.
      </p>
      {sessions.isPending && <p className="mt-8 text-slate-600">Loading sessions…</p>}
      {sessions.isError && (
        <p role="alert" className="mt-8 rounded-xl bg-red-50 p-4 text-red-800">
          {sessions.error.message}
        </p>
      )}
      {sessions.data?.length === 0 && (
        <div className="mt-8 rounded-2xl border border-dashed border-slate-300 p-8">
          <p className="text-slate-700">You haven’t started a course yet.</p>
          <Link to="/" className="mt-4 inline-block font-semibold text-indigo-700">
            Browse courses →
          </Link>
        </div>
      )}
      {sessions.data && sessions.data.length > 0 && (
        <div className="mt-8 space-y-4">
          {sessions.data.map((session) => {
            const count = lessonCount(session.plan);
            const completed = session.completed_lessons.length;
            const currentLesson = lessonById(
              session.plan,
              session.current_lesson_id,
            );
            return (
              <Link
                key={session.id}
                to="/learning-sessions/$sessionId"
                params={{ sessionId: session.id }}
                className="block rounded-2xl border border-slate-200 bg-white p-6 shadow-sm transition hover:border-indigo-300 hover:shadow-md"
              >
                <div className="flex flex-wrap items-start justify-between gap-4">
                  <div>
                    <p className="text-sm font-medium capitalize text-indigo-700">
                      {session.status}
                    </p>
                    <h2 className="mt-1 text-xl font-semibold text-slate-950">
                      {session.course.title}
                    </h2>
                    <p className="mt-2 text-slate-600">
                      {currentLesson
                        ? `Next: ${currentLesson.title}`
                        : "All lessons completed"}
                    </p>
                  </div>
                  <span className="text-sm text-slate-500">
                    {completed} / {count} lessons
                  </span>
                </div>
                <div className="mt-5 h-2 overflow-hidden rounded-full bg-slate-100">
                  <div
                    className="h-full rounded-full bg-indigo-600"
                    style={{
                      width: `${count === 0 ? 0 : (completed / count) * 100}%`,
                    }}
                  />
                </div>
              </Link>
            );
          })}
        </div>
      )}
    </main>
  );
}
