import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createFileRoute, Link } from "@tanstack/react-router";
import {
  apiRequest,
  lessonCount,
  LessonActivitySchema,
  LearningSessionSchema,
  QuizInteractionSchema,
  type LessonActivity,
} from "@/lib/api";
import { ActivityRenderer } from "@/components/ActivityRenderer";

export const Route = createFileRoute("/learning-sessions/$sessionId")({
  component: LearningSessionPage,
});

function LearningSessionPage() {
  const { sessionId } = Route.useParams();
  const queryClient = useQueryClient();
  const [selectedReviewLessonId, setSelectedReviewLessonId] = useState<
    string | null
  >(null);
  const [selectedActivityId, setSelectedActivityId] = useState<string | null>(
    null,
  );
  const [selectedActivityFormat, setSelectedActivityFormat] = useState<{
    lessonId: string;
    format: LessonActivity["presentation_format"];
  } | null>(null);
  const [learnerQuestion, setLearnerQuestion] = useState("");
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
        setSelectedReviewLessonId(null);
        queryClient.setQueryData(sessionKey, updatedSession);
        await queryClient.invalidateQueries({ queryKey: ["learning-sessions"] });
    },
  });
  const interactionsKey = ["learning-interactions", sessionId];
  const interactions = useQuery({
    queryKey: interactionsKey,
    enabled: Boolean(session.data),
    queryFn: () =>
      apiRequest(
        `/api/v1/learning-sessions/${sessionId}/interactions`,
        QuizInteractionSchema.array(),
      ),
  });
  const generateQuiz = useMutation({
    mutationFn: (lessonId: string) =>
      apiRequest(
        `/api/v1/learning-sessions/${sessionId}/interactions`,
        QuizInteractionSchema,
        {
          method: "POST",
          body: JSON.stringify({
            kind: "action",
            action: "quiz-me",
            lesson_id: lessonId,
          }),
        },
      ),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: interactionsKey });
    },
  });
  const [quizSelection, setQuizSelection] = useState<{
    interactionId: string;
    selectedOption: number;
  } | null>(null);
  const answerQuiz = useMutation({
    mutationFn: ({
      interactionId,
      selectedOption,
    }: {
      interactionId: string;
      selectedOption: number;
    }) =>
      apiRequest(
        `/api/v1/learning-sessions/${sessionId}/interactions/${interactionId}/answer`,
        QuizInteractionSchema,
        {
          method: "POST",
          body: JSON.stringify({ selected_option: selectedOption }),
        },
      ),
    onSuccess: async () => {
      setQuizSelection(null);
      await queryClient.invalidateQueries({ queryKey: interactionsKey });
    },
  });
  const data = session.data;
  const currentModuleId = data?.current_module_id;
  const currentLessonId = data?.current_lesson_id;
  const currentModule = data?.plan.modules.find(
    (module) => module.module_id === currentModuleId,
  );
  const currentLesson = currentModule?.lessons.find(
    (lesson) => lesson.lesson_id === currentLessonId,
  );
  const reviewLesson = data?.plan.modules
    .flatMap((module) => module.lessons)
    .find((lesson) => lesson.lesson_id === selectedReviewLessonId);
  const viewedLesson = reviewLesson ?? currentLesson;
  const viewedModule = viewedLesson
    ? data?.plan.modules.find((module) =>
        module.lessons.some(
          (lesson) => lesson.lesson_id === viewedLesson.lesson_id,
        ),
      )
    : undefined;
  const isReviewing = Boolean(
    viewedLesson && viewedLesson.lesson_id !== currentLesson?.lesson_id,
  );
  const activityKey = [
    "lesson-activities",
    sessionId,
    viewedLesson?.lesson_id,
  ] as const;
  const activities = useQuery({
    queryKey: activityKey,
    enabled: Boolean(data && viewedLesson),
    retry: false,
    queryFn: () => {
      if (!viewedLesson) {
        throw new Error("There is no lesson to load.");
      }
      const path = `/api/v1/learning-sessions/${sessionId}/lessons/${viewedLesson.lesson_id}/activities`;
      return apiRequest(path, LessonActivitySchema.array()).then(
        async (savedActivities) =>
          savedActivities.length > 0
            ? savedActivities
            : [
                await apiRequest(path, LessonActivitySchema, {
                  method: "POST",
                  body: JSON.stringify({}),
                }),
              ],
      );
    },
  });
  const regenerateActivity = useMutation({
    mutationFn: ({
      lessonId,
      action,
      presentationFormat,
      question,
    }: {
      lessonId: string;
      action:
        | "teach"
        | "explain-another-way"
        | "give-example"
        | "answer-question"
        | "change-format";
      presentationFormat?: LessonActivity["presentation_format"];
      question?: string;
    }) =>
      apiRequest(
        `/api/v1/learning-sessions/${sessionId}/lessons/${lessonId}/activities`,
        LessonActivitySchema,
        {
          method: "POST",
          body: JSON.stringify({
            regenerate: true,
            action,
            presentation_format: presentationFormat,
            question,
          }),
        },
      ),
    onSuccess: async (newActivity, { lessonId }) => {
      setSelectedActivityId(newActivity.id);
      setSelectedActivityFormat({
        lessonId,
        format: newActivity.presentation_format,
      });
      await queryClient.invalidateQueries({
        queryKey: ["lesson-activities", sessionId, lessonId],
      });
    },
    onError: (_error, { lessonId }) => {
      setSelectedActivityFormat((current) =>
        current?.lessonId === lessonId ? null : current,
      );
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
  if (!data) {
    return <main className="mx-auto max-w-5xl px-5 py-12">Loading your lesson…</main>;
  }

  const totalLessons = lessonCount(data.plan);
  const completedLessons = data.completed_lessons.length;
  const viewedQuiz = viewedLesson
    ? [...(interactions.data ?? [])]
        .reverse()
        .find((item) => item.lesson_id === viewedLesson.lesson_id)
    : undefined;
  const selectedQuizOption =
    viewedQuiz?.selected_option ??
    (quizSelection && quizSelection.interactionId === viewedQuiz?.id
      ? quizSelection.selectedOption
      : null);
  const viewedActivity =
    activities.data?.find((item) => item.id === selectedActivityId) ??
    activities.data?.[0];
  const selectedFormat =
    selectedActivityFormat &&
    selectedActivityFormat.lessonId === viewedLesson?.lesson_id
      ? selectedActivityFormat.format
      : viewedActivity?.presentation_format ?? "text-and-images";

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
                  const selected =
                    lesson.lesson_id ===
                    (isReviewing
                      ? viewedLesson?.lesson_id
                      : data.current_lesson_id);
                  return (
                    <li
                      key={lesson.lesson_id}
                      className="rounded-lg"
                    >
                      <button
                        type="button"
                        disabled={!done && !current}
                        aria-current={selected ? "step" : undefined}
                        onClick={() =>
                          setSelectedReviewLessonId(current ? null : lesson.lesson_id)
                        }
                        className={`w-full rounded-lg px-3 py-2 text-left text-sm ${
                          selected
                            ? "bg-indigo-50 font-semibold text-indigo-800"
                            : done
                              ? "text-emerald-700 hover:bg-emerald-50"
                              : "cursor-not-allowed text-slate-400"
                        }`}
                      >
                        {done ? "✓ " : ""}
                        {lesson.title}
                        {isReviewing && selected ? " · Review" : ""}
                      </button>
                    </li>
                  );
                })}
              </ol>
            </section>
          ))}
        </nav>
      </aside>

      <section className="min-w-0">
        {data.status === "completed" && !viewedLesson ? (
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
        ) : viewedLesson ? (
          <>
            {data.status === "completed" && (
              <div className="mb-6 rounded-2xl bg-emerald-50 px-5 py-4 text-emerald-800">
                Course complete. Select any completed lesson to review it.
              </div>
            )}
            <article className="rounded-3xl border border-slate-200 bg-white p-7 shadow-sm sm:p-10">
            {isReviewing && (
              <p className="mb-5 rounded-xl bg-emerald-50 px-4 py-3 text-sm font-medium text-emerald-800">
                Reviewing a completed lesson. Your course progress won’t change.
              </p>
            )}
            <p className="text-sm font-semibold uppercase tracking-[0.15em] text-indigo-600">
              {viewedModule?.title}
              {viewedLesson.estimated_minutes
                ? ` · ${viewedLesson.estimated_minutes} min`
                : ""}
            </p>
            <h2 className="mt-3 text-3xl font-semibold tracking-tight text-slate-950">
              {viewedLesson.title}
            </h2>
            <p className="mt-5 text-lg leading-8 text-slate-700">
              {viewedLesson.purpose}
            </p>

            <section className="mt-8 rounded-2xl bg-slate-50 p-6">
              <h3 className="font-semibold text-slate-950">By the end, you can</h3>
              <ul className="mt-3 space-y-2 text-slate-700">
                {viewedLesson.objectives.map((objective) => (
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
                {viewedLesson.key_topics.map((topic) => (
                  <li
                    key={topic}
                    className="rounded-full bg-indigo-50 px-3 py-1.5 text-sm text-indigo-800"
                  >
                    {topic}
                  </li>
                ))}
              </ul>
            </section>
            <section
              aria-live="polite"
              className="mt-7 rounded-2xl border border-slate-200 p-6"
            >
              <h3 className="text-xl font-semibold text-slate-950">
                Lesson activity
              </h3>
              {activities.isPending && (
                <p className="mt-4 text-slate-600">
                  Preparing your lesson material…
                </p>
              )}
              {activities.isError && (
                <div className="mt-4">
                  <p role="alert" className="rounded-xl bg-red-50 p-4 text-red-800">
                    {activities.error.message}
                  </p>
                  <button
                    type="button"
                    onClick={() => void activities.refetch()}
                    className="mt-3 font-semibold text-indigo-700 hover:text-indigo-900"
                  >
                    Try again
                  </button>
                </div>
              )}
              {viewedActivity && (
                <>
                  {activities.data && activities.data.length > 1 && (
                    <label className="mt-4 block text-sm font-medium text-slate-700">
                      Saved versions
                      <select
                        value={viewedActivity.id}
                        onChange={(event) =>
                          setSelectedActivityId(event.currentTarget.value)
                        }
                        className="mt-1 block w-full rounded-lg border border-slate-300 bg-white px-3 py-2"
                      >
                        {activities.data.map((savedActivity, index) => (
                          <option key={savedActivity.id} value={savedActivity.id}>
                            {index === 0 ? "Latest activity" : `Version ${activities.data.length - index}`}
                          </option>
                        ))}
                      </select>
                    </label>
                  )}
                  <button
                    type="button"
                    onClick={() =>
                      regenerateActivity.mutate({
                        lessonId: viewedLesson.lesson_id,
                        action: "teach",
                        presentationFormat: viewedActivity.presentation_format,
                      })
                    }
                    disabled={regenerateActivity.isPending}
                    className="mt-4 rounded-lg border border-indigo-600 px-4 py-2 text-sm font-semibold text-indigo-700 hover:bg-indigo-50 disabled:cursor-wait disabled:opacity-60"
                  >
                    {regenerateActivity.isPending
                      ? "Generating a new activity…"
                      : "Generate a new activity"}
                  </button>
                  {regenerateActivity.isError && (
                    <p role="alert" className="mt-3 rounded-xl bg-red-50 p-4 text-red-800">
                      {regenerateActivity.error.message}
                    </p>
                  )}
                  <ActivityRenderer key={viewedActivity.id} activity={viewedActivity} />
                </>
              )}
            </section>
            <section className="mt-7 rounded-2xl border border-sky-100 bg-sky-50/50 p-6">
              <h3 className="text-xl font-semibold text-slate-950">
                Learn another way
              </h3>
              <p className="mt-2 text-slate-600">
                Ask about this lesson, request a different explanation, or try a
                concrete example.
              </p>
              <form
                className="mt-4 flex flex-col gap-3 sm:flex-row"
                onSubmit={(event) => {
                  event.preventDefault();
                  if (!viewedLesson || !learnerQuestion.trim()) return;
                  regenerateActivity.mutate(
                    {
                      lessonId: viewedLesson.lesson_id,
                      action: "answer-question",
                      presentationFormat: viewedActivity?.presentation_format,
                      question: learnerQuestion.trim(),
                    },
                    { onSuccess: () => setLearnerQuestion("") },
                  );
                }}
              >
                <label className="sr-only" htmlFor="lesson-question">
                  Ask a question about this lesson
                </label>
                <input
                  id="lesson-question"
                  value={learnerQuestion}
                  onChange={(event) => setLearnerQuestion(event.target.value)}
                  maxLength={2000}
                  placeholder="What would you like clarified?"
                  className="min-w-0 flex-1 rounded-lg border border-slate-300 bg-white px-3 py-2.5"
                />
                <button
                  type="submit"
                  disabled={
                    regenerateActivity.isPending || !learnerQuestion.trim()
                  }
                  className="rounded-lg bg-sky-700 px-4 py-2.5 font-semibold text-white hover:bg-sky-800 disabled:cursor-wait disabled:opacity-60"
                >
                  Ask
                </button>
              </form>
              <div className="mt-3 flex flex-wrap gap-3">
                <button
                  type="button"
                  disabled={regenerateActivity.isPending}
                  onClick={() =>
                    viewedLesson &&
                    regenerateActivity.mutate({
                      lessonId: viewedLesson.lesson_id,
                      action: "explain-another-way",
                      presentationFormat: viewedActivity?.presentation_format,
                    })
                  }
                  className="rounded-lg border border-sky-700 px-4 py-2 font-semibold text-sky-800 hover:bg-sky-100 disabled:opacity-60"
                >
                  Explain another way
                </button>
                <button
                  type="button"
                  disabled={regenerateActivity.isPending}
                  onClick={() =>
                    viewedLesson &&
                    regenerateActivity.mutate({
                      lessonId: viewedLesson.lesson_id,
                      action: "give-example",
                      presentationFormat: viewedActivity?.presentation_format,
                    })
                  }
                  className="rounded-lg border border-sky-700 px-4 py-2 font-semibold text-sky-800 hover:bg-sky-100 disabled:opacity-60"
                >
                  Give an example
                </button>
                <label className="flex items-center gap-2 text-sm font-medium text-slate-700">
                  Present as
                  <select
                    value={selectedFormat}
                    onChange={(event) => {
                      if (viewedLesson) {
                        const presentationFormat =
                          LessonActivitySchema.shape.presentation_format.parse(
                            event.target.value,
                          );
                        setSelectedActivityFormat({
                          lessonId: viewedLesson.lesson_id,
                          format: presentationFormat,
                        });
                        regenerateActivity.mutate({
                          lessonId: viewedLesson.lesson_id,
                          action: "change-format",
                          presentationFormat,
                        });
                      }
                    }}
                    disabled={regenerateActivity.isPending}
                    className="rounded-lg border border-slate-300 bg-white px-3 py-2"
                  >
                    <option value="text-and-images">Text and images</option>
                    <option value="interactive-simulations">Simulation</option>
                    <option value="interactive-role-play-activities">Role-play</option>
                    <option value="games">Mini-game</option>
                    <option value="animations">Narrated animation</option>
                    <option value="slides-based">Slides</option>
                    <option value="online-coding">Coding exercise</option>
                  </select>
                </label>
              </div>
              {regenerateActivity.isPending && (
                <p className="mt-3 text-sm text-slate-600" aria-live="polite">
                  Preparing a lesson activity…
                </p>
              )}
            </section>
            <section className="mt-7 rounded-2xl border border-indigo-100 bg-indigo-50/50 p-6">
              <h3 className="text-xl font-semibold text-slate-950">
                Practice this lesson
              </h3>
              <p className="mt-2 text-slate-600">
                Check your understanding with a question based on this lesson.
              </p>
              <button
                type="button"
                onClick={() => {
                  answerQuiz.reset();
                  setQuizSelection(null);
                  generateQuiz.mutate(viewedLesson.lesson_id);
                }}
                disabled={generateQuiz.isPending}
                className="mt-4 rounded-xl bg-indigo-600 px-5 py-2.5 font-semibold text-white hover:bg-indigo-700 disabled:cursor-wait disabled:opacity-60"
              >
                {generateQuiz.isPending
                  ? "Preparing a question…"
                  : viewedQuiz
                    ? "Try another question"
                    : "Quiz me"}
              </button>
              {generateQuiz.isError && (
                <p role="alert" className="mt-4 rounded-xl bg-red-50 p-4 text-red-800">
                  {generateQuiz.error.message}
                </p>
              )}
              {interactions.isError && (
                <p role="alert" className="mt-4 rounded-xl bg-red-50 p-4 text-red-800">
                  {interactions.error.message}
                </p>
              )}
              {viewedQuiz && (
                <div className="mt-5 rounded-xl border border-slate-200 bg-white p-5">
                  <h4 className="font-semibold leading-7 text-slate-950">
                    {viewedQuiz.question}
                  </h4>
                  <fieldset className="mt-4 space-y-3">
                    <legend className="sr-only">Choose your answer</legend>
                    {viewedQuiz.options.map((option, index) => (
                      <label
                        key={`${viewedQuiz.id}-${index}`}
                        className="flex cursor-pointer items-start gap-3 rounded-lg border border-slate-200 p-3 hover:border-indigo-300"
                      >
                        <input
                          type="radio"
                          name={`quiz-${viewedQuiz.id}`}
                          checked={selectedQuizOption === index}
                          disabled={viewedQuiz.selected_option !== null || answerQuiz.isPending}
                          onChange={() =>
                            setQuizSelection({
                              interactionId: viewedQuiz.id,
                              selectedOption: index,
                            })
                          }
                          className="mt-1 accent-indigo-600"
                        />
                        <span className="text-slate-700">{option}</span>
                      </label>
                    ))}
                  </fieldset>
                  {viewedQuiz.selected_option === null && (
                    <>
                      {answerQuiz.isError && (
                        <p role="alert" className="mt-4 rounded-xl bg-red-50 p-4 text-red-800">
                          {answerQuiz.error.message}
                        </p>
                      )}
                      <button
                        type="button"
                        onClick={() => {
                          if (selectedQuizOption !== null) {
                            answerQuiz.mutate({
                              interactionId: viewedQuiz.id,
                              selectedOption: selectedQuizOption,
                            });
                          }
                        }}
                        disabled={selectedQuizOption === null || answerQuiz.isPending}
                        className="mt-4 rounded-xl border border-indigo-600 px-5 py-2.5 font-semibold text-indigo-700 hover:bg-indigo-50 disabled:cursor-not-allowed disabled:opacity-50"
                      >
                        {answerQuiz.isPending ? "Checking…" : "Check answer"}
                      </button>
                    </>
                  )}
                  {viewedQuiz.selected_option !== null && (
                    <div
                      className={`mt-4 rounded-xl p-4 ${
                        viewedQuiz.is_correct
                          ? "bg-emerald-50 text-emerald-800"
                          : "bg-amber-50 text-amber-900"
                      }`}
                    >
                      <p className="font-semibold">
                        {viewedQuiz.is_correct ? "Correct!" : "Not quite."}
                      </p>
                      <p className="mt-2 leading-7">{viewedQuiz.explanation}</p>
                    </div>
                  )}
                </div>
              )}
            </section>
            <section className="mt-7 rounded-2xl border border-indigo-100 p-5">
              <h3 className="font-semibold text-slate-950">
                {isReviewing ? "Review checkpoint" : "Completion check"}
              </h3>
              <p className="mt-2 leading-7 text-slate-700">
                {viewedLesson.completion_check}
              </p>
              {!isReviewing && (
                <p className="mt-3 text-sm text-slate-500">
                  When you're ready, mark this lesson complete. Your next lesson
                  will be saved automatically.
                </p>
              )}
            </section>

            {!isReviewing && currentLesson && data.status === "active" && (
              <>
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
              </>
            )}
            </article>
          </>
        ) : null}
      </section>
    </main>
  );
}
