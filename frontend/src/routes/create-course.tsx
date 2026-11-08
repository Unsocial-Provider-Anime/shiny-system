import { useMutation, useQuery } from "@tanstack/react-query";
import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useState } from "react";
import {
  apiRequest,
  CourseDraftProposalSchema,
  CourseSaveResponseSchema,
  CourseSchema,
  type Lesson,
  type Module,
} from "@/lib/api";
import {
  StringListEditor,
  TextField,
} from "@/components/CourseDraftFields";
import { fetchProfile, profileQueryKey } from "@/lib/profile";

export const Route = createFileRoute("/create-course")({
  component: CreateCoursePage,
});

const formats = [
  ["text-and-images", "Text and images"],
  ["interactive-simulations", "Interactive simulations"],
  ["interactive-role-play-activities", "Role-play activities"],
  ["games", "Games"],
  ["animations", "Animations"],
  ["slides-based", "Slides"],
  ["online-coding", "Online coding"],
] as const;

type CourseProposal = typeof CourseDraftProposalSchema._output;

function CreateCoursePage() {
  const navigate = useNavigate();
  const profile = useQuery({ queryKey: profileQueryKey, queryFn: fetchProfile });
  const [topic, setTopic] = useState("");
  const [learningGoal, setLearningGoal] = useState("");
  const [targetAudience, setTargetAudience] = useState("");
  const [experienceLevel, setExperienceLevel] = useState("");
  const [timeBudget, setTimeBudget] = useState("");
  const [constraints, setConstraints] = useState("");
  const [preferredFormat, setPreferredFormat] =
    useState<(typeof formats)[number][0]>("text-and-images");
  const [proposal, setProposal] = useState<CourseProposal | null>(null);
  const [draftId, setDraftId] = useState<string | null>(null);

  const generate = useMutation({
    mutationFn: () =>
      apiRequest("/api/v1/course-drafts", CourseDraftProposalSchema, {
        method: "POST",
        body: JSON.stringify({
          topic: topic.trim(),
          learning_goal: learningGoal.trim() || null,
          target_audience: targetAudience.trim() || null,
          experience_level: experienceLevel.trim() || null,
          time_budget_minutes: timeBudget ? Number(timeBudget) : null,
          constraints: constraints
            .split("\n")
            .map((constraint) => constraint.trim())
            .filter(Boolean),
          preferred_formats: [preferredFormat],
        }),
      }),
    onSuccess: (generatedProposal) => {
      setProposal(generatedProposal);
      setDraftId(null);
    },
  });

  async function saveProposal(currentProposal: CourseProposal) {
    const validatedProposal = CourseDraftProposalSchema.parse(currentProposal);
    const response = await apiRequest(
      draftId ? `/api/v1/courses/${draftId}` : "/api/v1/courses",
      CourseSaveResponseSchema,
      {
        method: draftId ? "PATCH" : "POST",
        body: JSON.stringify(validatedProposal),
      },
    );
    setDraftId(response.course_id);
    return response.course_id;
  }

  const save = useMutation({
    mutationFn: saveProposal,
  });

  const publish = useMutation({
    mutationFn: async (currentProposal: CourseProposal) => {
      const courseId = await saveProposal(currentProposal);
      return apiRequest(
        `/api/v1/courses/${courseId}/publish`,
        CourseSchema,
        { method: "POST" },
      );
    },
    onSuccess: async (course) => {
      await navigate({
        to: "/courses/$courseId",
        params: { courseId: course.id },
      });
    },
  });

  function updateProposal(update: (current: CourseProposal) => CourseProposal) {
    setProposal((current) => (current ? update(current) : current));
  }

  function updateModule(index: number, changes: Partial<Module>) {
    updateProposal((current) => ({
      ...current,
      plan: {
        ...current.plan,
        modules: current.plan.modules.map((module, moduleIndex) =>
          moduleIndex === index ? { ...module, ...changes } : module,
        ),
      },
    }));
  }

  function updateLesson(
    moduleIndex: number,
    lessonIndex: number,
    changes: Partial<Lesson>,
  ) {
    updateProposal((current) => ({
      ...current,
      plan: {
        ...current.plan,
        modules: current.plan.modules.map((module, currentModuleIndex) =>
          currentModuleIndex === moduleIndex
            ? {
                ...module,
                lessons: module.lessons.map((lesson, currentLessonIndex) =>
                  currentLessonIndex === lessonIndex
                    ? { ...lesson, ...changes }
                    : lesson,
                ),
              }
            : module,
        ),
      },
    }));
  }

  if (profile.isPending) {
    return <main className="mx-auto max-w-4xl px-5 py-12">Loading account…</main>;
  }
  if (profile.isError) {
    return (
      <main className="mx-auto max-w-4xl px-5 py-12">
        <p role="alert" className="rounded-xl bg-red-50 p-4 text-red-800">
          {profile.error.message}
        </p>
      </main>
    );
  }
  if (!profile.data) {
    return (
      <main className="mx-auto max-w-3xl px-5 py-12">
        <h1 className="text-3xl font-semibold text-slate-950">Create a course</h1>
        <p className="mt-3 text-slate-600">
          Sign in to generate and save your own course.
        </p>
        <Link
          to="/login"
          className="mt-6 inline-block rounded-xl bg-indigo-700 px-5 py-3 font-semibold text-white hover:bg-indigo-800"
        >
          Sign in
        </Link>
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
          Course authoring
        </p>
        <h1 className="mt-2 text-3xl font-semibold tracking-tight text-slate-950 sm:text-4xl">
          Create a course with AI
        </h1>
        <p className="mt-3 leading-7 text-slate-600">
          Describe what you want to teach. Review and refine the proposal before
          saving or publishing it.
        </p>
      </header>

      <form
        className="mt-8 space-y-5 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm"
        onSubmit={(event) => {
          event.preventDefault();
          generate.mutate();
        }}
      >
        <h2 className="text-xl font-semibold text-slate-950">Course brief</h2>
        <label className="block text-sm font-medium text-slate-700" htmlFor="topic">
          Topic <span className="text-red-700">*</span>
          <input
            id="topic"
            required
            minLength={3}
            maxLength={200}
            value={topic}
            onChange={(event) => setTopic(event.target.value)}
            placeholder="For example, using AI coding agents effectively"
            className="mt-2 block w-full rounded-lg border border-slate-300 px-3 py-2.5 text-base"
          />
        </label>
        <label className="block text-sm font-medium text-slate-700" htmlFor="learning-goal">
          Learning goal
          <textarea
            id="learning-goal"
            maxLength={1000}
            rows={2}
            value={learningGoal}
            onChange={(event) => setLearningGoal(event.target.value)}
            placeholder="What should learners be able to do?"
            className="mt-2 block w-full rounded-lg border border-slate-300 px-3 py-2.5 text-base"
          />
        </label>
        <div className="grid gap-5 sm:grid-cols-2">
          <label className="block text-sm font-medium text-slate-700" htmlFor="audience">
            Target audience
            <input
              id="audience"
              maxLength={500}
              value={targetAudience}
              onChange={(event) => setTargetAudience(event.target.value)}
              placeholder="Who is this course for?"
              className="mt-2 block w-full rounded-lg border border-slate-300 px-3 py-2.5 text-base"
            />
          </label>
          <label className="block text-sm font-medium text-slate-700" htmlFor="experience">
            Experience level
            <input
              id="experience"
              maxLength={100}
              value={experienceLevel}
              onChange={(event) => setExperienceLevel(event.target.value)}
              placeholder="Beginner, intermediate…"
              className="mt-2 block w-full rounded-lg border border-slate-300 px-3 py-2.5 text-base"
            />
          </label>
        </div>
        <div className="grid gap-5 sm:grid-cols-2">
          <label className="block text-sm font-medium text-slate-700" htmlFor="time-budget">
            Time budget (minutes)
            <input
              id="time-budget"
              type="number"
              min={1}
              max={10080}
              value={timeBudget}
              onChange={(event) => setTimeBudget(event.target.value)}
              placeholder="e.g. 120"
              className="mt-2 block w-full rounded-lg border border-slate-300 px-3 py-2.5 text-base"
            />
          </label>
          <label className="block text-sm font-medium text-slate-700" htmlFor="format">
            Preferred activity format
            <select
              id="format"
              value={preferredFormat}
              onChange={(event) =>
                setPreferredFormat(event.target.value as (typeof formats)[number][0])
              }
              className="mt-2 block w-full rounded-lg border border-slate-300 bg-white px-3 py-2.5 text-base"
            >
              {formats.map(([value, label]) => (
                <option key={value} value={value}>{label}</option>
              ))}
            </select>
          </label>
        </div>
        <label className="block text-sm font-medium text-slate-700" htmlFor="constraints">
          Requirements or constraints
          <textarea
            id="constraints"
            rows={3}
            value={constraints}
            onChange={(event) => setConstraints(event.target.value)}
            placeholder={"One per line, e.g.\nUse practical examples\nAvoid assuming programming experience"}
            className="mt-2 block w-full rounded-lg border border-slate-300 px-3 py-2.5 text-base"
          />
        </label>
        {generate.isError && (
          <p role="alert" className="rounded-lg bg-red-50 p-3 text-sm text-red-800">
            {generate.error.message}
          </p>
        )}
        <button
          type="submit"
          disabled={generate.isPending}
          className="rounded-xl bg-indigo-700 px-5 py-3 font-semibold text-white hover:bg-indigo-800 disabled:cursor-wait disabled:opacity-60"
        >
          {generate.isPending ? "Generating proposal…" : "Generate course proposal"}
        </button>
      </form>

      {proposal && (
        <section className="mt-10 space-y-6">
          <div>
            <p className="text-sm font-semibold uppercase tracking-[0.15em] text-indigo-600">
              Review and edit
            </p>
            <h2 className="mt-1 text-2xl font-semibold text-slate-950">
              Your course proposal
            </h2>
          </div>
          <div className="space-y-5 rounded-2xl border border-slate-200 bg-white p-6">
            <TextField
              label="Course title"
              value={proposal.title}
              onChange={(title) =>
                updateProposal((current) => ({ ...current, title }))
              }
            />
            <TextField
              label="Course description"
              value={proposal.description}
              multiline
              onChange={(description) =>
                updateProposal((current) => ({ ...current, description }))
              }
            />
            <label className="block text-sm font-medium text-slate-700">
              Course access
              <select
                value={proposal.visibility}
                onChange={(event) =>
                  updateProposal((current) => ({
                    ...current,
                    visibility: event.target.value as CourseProposal["visibility"],
                  }))
                }
                className="mt-2 block rounded-lg border border-slate-300 bg-white px-3 py-2.5"
              >
                <option value="restricted">Restricted (only you and selected learners)</option>
                <option value="public">Public</option>
              </select>
            </label>
            <TextField
              label="Course overview"
              value={proposal.plan.overview}
              multiline
              onChange={(overview) =>
                updateProposal((current) => ({
                  ...current,
                  plan: { ...current.plan, overview },
                }))
              }
            />
            <TextField
              label="Target audience"
              value={proposal.plan.target_audience}
              onChange={(audience) =>
                updateProposal((current) => ({
                  ...current,
                  plan: { ...current.plan, target_audience: audience },
                }))
              }
            />
            <StringListEditor
              label="Learning outcomes"
              values={proposal.plan.learning_outcomes}
              onChange={(learning_outcomes) =>
                updateProposal((current) => ({
                  ...current,
                  plan: { ...current.plan, learning_outcomes },
                }))
              }
            />
            <div className="border-t border-slate-200 pt-5">
              <h3 className="text-lg font-semibold text-slate-950">Modules and lessons</h3>
              <div className="mt-4 space-y-5">
                {proposal.plan.modules.map((module, moduleIndex) => (
                  <article
                    key={module.module_id}
                    className="space-y-4 rounded-xl border border-slate-200 bg-slate-50 p-4"
                  >
                    <p className="text-xs font-semibold uppercase tracking-wide text-indigo-700">
                      Module {moduleIndex + 1}
                    </p>
                    <TextField
                      label="Module title"
                      value={module.title}
                      onChange={(title) => updateModule(moduleIndex, { title })}
                    />
                    <TextField
                      label="Module description"
                      value={module.description}
                      multiline
                      onChange={(description) =>
                        updateModule(moduleIndex, { description })
                      }
                    />
                    <div className="space-y-4">
                      {module.lessons.map((lesson, lessonIndex) => (
                        <div
                          key={lesson.lesson_id}
                          className="space-y-3 rounded-lg border border-slate-200 bg-white p-4"
                        >
                          <p className="text-sm font-semibold text-slate-700">
                            Lesson {lessonIndex + 1}
                          </p>
                          <TextField
                            label="Lesson title"
                            value={lesson.title}
                            onChange={(title) =>
                              updateLesson(moduleIndex, lessonIndex, { title })
                            }
                          />
                          <TextField
                            label="Lesson purpose"
                            value={lesson.purpose}
                            multiline
                            onChange={(purpose) =>
                              updateLesson(moduleIndex, lessonIndex, { purpose })
                            }
                          />
                          <TextField
                            label="Completion check"
                            value={lesson.completion_check}
                            multiline
                            onChange={(completion_check) =>
                              updateLesson(moduleIndex, lessonIndex, {
                                completion_check,
                              })
                            }
                          />
                          <p className="text-sm text-slate-600">
                            Activity: {lesson.suggested_activity.title} ·{" "}
                            {formatLabel(lesson.suggested_activity.presentation_format)}
                          </p>
                        </div>
                      ))}
                    </div>
                  </article>
                ))}
              </div>
            </div>
            <TextField
              label="Capstone"
              value={proposal.plan.capstone}
              multiline
              onChange={(capstone) =>
                updateProposal((current) => ({
                  ...current,
                  plan: { ...current.plan, capstone },
                }))
              }
            />
          </div>

          {(save.isError || publish.isError) && (
            <p role="alert" className="rounded-xl bg-red-50 p-4 text-red-800">
              {save.error?.message ?? publish.error?.message}
            </p>
          )}
          {draftId && (
            <p className="text-sm text-green-800" role="status">
              Draft saved. Save again after making further edits.
            </p>
          )}
          <div className="flex flex-wrap gap-3">
            <button
              type="button"
              onClick={() => save.mutate(proposal)}
              disabled={save.isPending || publish.isPending}
              className="rounded-xl border border-indigo-700 px-5 py-3 font-semibold text-indigo-800 hover:bg-indigo-50 disabled:opacity-60"
            >
              {save.isPending ? "Saving draft…" : "Save as draft"}
            </button>
            <button
              type="button"
              onClick={() => publish.mutate(proposal)}
              disabled={save.isPending || publish.isPending}
              className="rounded-xl bg-indigo-700 px-5 py-3 font-semibold text-white hover:bg-indigo-800 disabled:opacity-60"
            >
              {publish.isPending ? "Publishing…" : "Save and publish"}
            </button>
          </div>
          <p className="text-sm text-slate-600">
            Publishing makes this course available according to its access setting.
          </p>
        </section>
      )}
    </main>
  );
}

function formatLabel(format: string) {
  return formats.find(([value]) => value === format)?.[1] ?? format;
}
