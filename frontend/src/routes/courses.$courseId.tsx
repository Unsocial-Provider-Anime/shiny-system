import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { z } from "zod";
import {
  apiRequest,
  CourseAccessSchema,
  CourseSchema,
  LearningSessionSchema,
  CourseVisibilityResponseSchema,
} from "@/lib/api";

export const Route = createFileRoute("/courses/$courseId")({
  component: CourseDetailPage,
});

function CourseDetailPage() {
  const { courseId } = Route.useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const courseKey = ["course", courseId];
  const course = useQuery({
    queryKey: courseKey,
    queryFn: () =>
      apiRequest(`/api/v1/courses/${courseId}`, CourseSchema),
  });
  const access = useQuery({
    queryKey: ["course-access", courseId],
    enabled: course.data?.is_owner === true,
    queryFn: () =>
      apiRequest(`/api/v1/courses/${courseId}/access`, CourseAccessSchema.array()),
  });
  const setVisibility = useMutation({
    mutationFn: (visibility: "public" | "restricted") =>
      apiRequest(
        `/api/v1/courses/${courseId}/visibility`,
        CourseVisibilityResponseSchema,
        { method: "PATCH", body: JSON.stringify({ visibility }) },
      ),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: courseKey }),
        queryClient.invalidateQueries({ queryKey: ["courses"] }),
      ]);
    },
  });
  const grantAccess = useMutation({
    mutationFn: (email: string) =>
      apiRequest(
        `/api/v1/courses/${courseId}/access`,
        z.object({ user_id: z.number(), email: z.string() }),
        { method: "POST", body: JSON.stringify({ email }) },
      ),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["course-access", courseId] });
    },
  });
  const revokeAccess = useMutation({
    mutationFn: (userId: number) =>
      apiRequest(
        `/api/v1/courses/${courseId}/access/${userId}`,
        z.object({ message: z.string() }),
        { method: "DELETE" },
      ),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["course-access", courseId] });
    },
  });
  const [learnerEmail, setLearnerEmail] = useState("");
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

      {course.data.is_owner && course.data.status === "published" && (
        <section className="mt-8 rounded-2xl border border-indigo-200 bg-indigo-50/50 p-6">
          <h2 className="text-xl font-semibold text-slate-950">Course sharing</h2>
          <p className="mt-2 text-sm leading-6 text-slate-600">
            Public courses are discoverable by everyone. Restricted courses are
            available only to you and the learners you add.
          </p>
          <label className="mt-5 block text-sm font-medium text-slate-700" htmlFor="course-visibility">
            Who can access this course?
          </label>
          <select
            id="course-visibility"
            value={course.data.visibility ?? "restricted"}
            onChange={(event) => {
              const visibility =
                event.target.value === "public" ? "public" : "restricted";
              setVisibility.mutate(visibility);
            }}
            disabled={setVisibility.isPending}
            className="mt-2 rounded-lg border border-slate-300 bg-white px-3 py-2 text-slate-900 disabled:opacity-60"
          >
            <option value="public">Public</option>
            <option value="restricted">Restricted</option>
          </select>
          {setVisibility.isError && (
            <p role="alert" className="mt-3 text-sm text-red-700">
              {setVisibility.error.message}
            </p>
          )}

          <div className="mt-6 border-t border-indigo-100 pt-5">
            <h3 className="font-semibold text-slate-900">Selected learners</h3>
            <form
              className="mt-3 flex flex-wrap gap-2"
              onSubmit={(event) => {
                event.preventDefault();
                grantAccess.mutate(learnerEmail.trim(), {
                  onSuccess: () => setLearnerEmail(""),
                });
              }}
            >
              <label className="sr-only" htmlFor="learner-email">
                Learner account email
              </label>
              <input
                id="learner-email"
                type="email"
                required
                value={learnerEmail}
                onChange={(event) => setLearnerEmail(event.target.value)}
                placeholder="learner@example.com"
                className="min-w-0 flex-1 rounded-lg border border-slate-300 bg-white px-3 py-2"
              />
              <button
                type="submit"
                disabled={grantAccess.isPending}
                className="rounded-lg bg-indigo-700 px-4 py-2 font-semibold text-white hover:bg-indigo-800 disabled:opacity-60"
              >
                {grantAccess.isPending ? "Adding…" : "Add learner"}
              </button>
            </form>
            {grantAccess.isError && (
              <p role="alert" className="mt-3 text-sm text-red-700">
                {grantAccess.error.message}
              </p>
            )}
            {revokeAccess.isError && (
              <p role="alert" className="mt-3 text-sm text-red-700">
                {revokeAccess.error.message}
              </p>
            )}
            {access.isPending && <p className="mt-4 text-sm text-slate-600">Loading access list…</p>}
            {access.isError && (
              <p role="alert" className="mt-4 text-sm text-red-700">
                {access.error.message}
              </p>
            )}
            {access.data?.length === 0 && (
              <p className="mt-4 text-sm text-slate-600">No learners have been added.</p>
            )}
            {access.data && access.data.length > 0 && (
              <ul className="mt-4 divide-y divide-indigo-100">
                {access.data.map((learner) => (
                  <li
                    key={learner.user_id}
                    className="flex items-center justify-between gap-4 py-3"
                  >
                    <span className="text-sm text-slate-800">
                      {learner.email ?? `Account ${learner.user_id}`}
                    </span>
                    <button
                      type="button"
                      onClick={() => revokeAccess.mutate(learner.user_id)}
                      disabled={revokeAccess.isPending}
                      className="text-sm font-semibold text-red-700 hover:text-red-900 disabled:opacity-60"
                    >
                      Remove
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </section>
      )}

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
