import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import {
  apiRequest,
  CodingAnswerSchema,
  type LessonActivity,
} from "@/lib/api";
import { MarkdownRenderer } from "@/components/MarkdownRenderer";

type Props = {
  activity: LessonActivity;
  sessionId: string;
};

const buttonClass =
  "rounded-lg border border-slate-300 px-4 py-2 text-left text-slate-800 hover:border-indigo-400 hover:bg-indigo-50";

export function ActivityRenderer({ activity, sessionId }: Props) {
  const [selectedChoice, setSelectedChoice] = useState<number | null>(null);
  const [slideIndex, setSlideIndex] = useState(0);
  const [sceneIndex, setSceneIndex] = useState(0);
  const [code, setCode] = useState(activity.content.type === "online-coding"
    ? activity.content.starter_code
    : "");
  const [solutionVisible, setSolutionVisible] = useState(false);
  const codingAnswer = useMutation({
    mutationFn: ({ revealSolution }: { revealSolution: boolean }) => {
      if (activity.content.type !== "online-coding") {
        throw new Error("This activity is not a coding exercise.");
      }
      return apiRequest(
        `/api/v1/learning-sessions/${sessionId}/lessons/${activity.lesson_id}/activities/${activity.id}/check`,
        CodingAnswerSchema,
        {
          method: "POST",
          body: JSON.stringify({ code, reveal_solution: revealSolution }),
        },
      );
    },
  });

  switch (activity.content.type) {
    case "text-and-images":
      return (
        <>
          <MarkdownRenderer className="mt-5" content={activity.content.content} />
          {activity.content.image_descriptions.length > 0 && (
            <section className="mt-6 rounded-xl bg-slate-50 p-4">
              <h4 className="font-semibold text-slate-900">Illustration ideas</h4>
              <ul className="mt-2 list-inside list-disc space-y-2 text-sm text-slate-600">
                {activity.content.image_descriptions.map((description) => (
                  <li key={description}>{description}</li>
                ))}
              </ul>
            </section>
          )}
        </>
      );
    case "interactive-simulations":
      return (
        <div className="mt-5 space-y-5">
          <p className="leading-7 text-slate-700">{activity.content.scenario}</p>
          <div className="grid gap-3">
            {activity.content.choices.map((choice, index) => (
              <button
                key={choice.label}
                type="button"
                aria-pressed={selectedChoice === index}
                onClick={() => setSelectedChoice(index)}
                className={buttonClass}
              >
                {choice.label}
              </button>
            ))}
          </div>
          {selectedChoice !== null && (
            <div className="rounded-xl bg-indigo-50 p-4 text-indigo-950">
              <p className="font-semibold">What happens next</p>
              <p className="mt-2 leading-7">
                {activity.content.choices[selectedChoice].consequence}
              </p>
            </div>
          )}
          <p className="rounded-xl bg-slate-50 p-4 leading-7 text-slate-700">
            <strong>Learning point: </strong>
            {activity.content.learning_point}
          </p>
        </div>
      );
    case "interactive-role-play-activities":
      return (
        <div className="mt-5 space-y-5">
          <p className="leading-7 text-slate-700">{activity.content.scenario}</p>
          <div className="rounded-xl bg-slate-50 p-4 text-sm text-slate-700">
            Your role: <strong>{activity.content.learner_role}</strong>
            {" · "}
            Partner: <strong>{activity.content.partner_role}</strong>
          </div>
          <blockquote className="border-l-4 border-indigo-300 pl-4 text-lg leading-7 text-slate-800">
            {activity.content.opening_prompt}
          </blockquote>
          <fieldset className="space-y-3">
            <legend className="mb-3 font-semibold text-slate-900">
              Choose your response
            </legend>
            {activity.content.response_choices.map((choice, index) => (
              <button
                key={choice.response}
                type="button"
                aria-pressed={selectedChoice === index}
                onClick={() => setSelectedChoice(index)}
                className={`block w-full ${buttonClass}`}
              >
                {choice.response}
              </button>
            ))}
          </fieldset>
          {selectedChoice !== null && (
            <p className="rounded-xl bg-indigo-50 p-4 leading-7 text-indigo-950">
              {activity.content.response_choices[selectedChoice].feedback}
            </p>
          )}
        </div>
      );
    case "games":
      return (
        <div className="mt-5 space-y-5">
          <p className="font-semibold text-indigo-800">
            Objective: {activity.content.objective}
          </p>
          <p className="leading-7 text-slate-700">{activity.content.instructions}</p>
          <div className="rounded-xl bg-amber-50 p-4 leading-7 text-amber-950">
            {activity.content.challenge}
          </div>
          <div className="grid gap-3">
            {activity.content.choices.map((choice, index) => (
              <button
                key={choice.label}
                type="button"
                aria-pressed={selectedChoice === index}
                onClick={() => setSelectedChoice(index)}
                className={buttonClass}
              >
                {choice.label}
              </button>
            ))}
          </div>
          {selectedChoice !== null && (
            <p
              className={`rounded-xl p-4 leading-7 ${
                activity.content.choices[selectedChoice].is_correct
                  ? "bg-emerald-50 text-emerald-900"
                  : "bg-amber-50 text-amber-950"
              }`}
            >
              {activity.content.choices[selectedChoice].feedback}
            </p>
          )}
        </div>
      );
    case "animations": {
      const scene = activity.content.scenes[sceneIndex];
      const sceneCount = activity.content.scenes.length;
      return (
        <section className="mt-5">
          <div className="flex min-h-48 items-center justify-center rounded-2xl bg-gradient-to-br from-indigo-100 via-sky-50 to-violet-100 p-8 text-center motion-safe:animate-pulse">
            <div>
              <p className="text-sm font-semibold uppercase tracking-wide text-indigo-700">
                Scene {sceneIndex + 1} of {activity.content.scenes.length}
              </p>
              <h4 className="mt-2 text-2xl font-semibold text-slate-950">
                {scene.title}
              </h4>
              <p className="mt-3 text-slate-700">{scene.visual_description}</p>
            </div>
          </div>
          <p className="mt-4 leading-7 text-slate-700" aria-live="polite">
            <strong>Narration: </strong>
            {scene.narration}
          </p>
          <div className="mt-4 flex flex-wrap gap-3">
            <button
              type="button"
              onClick={() => {
                if (!("speechSynthesis" in window)) return;
                window.speechSynthesis.cancel();
                window.speechSynthesis.speak(
                  new SpeechSynthesisUtterance(scene.narration),
                );
              }}
              className={buttonClass}
            >
              Play narration
            </button>
            <button
              type="button"
              onClick={() => {
                if ("speechSynthesis" in window) {
                  window.speechSynthesis.cancel();
                }
              }}
              className={buttonClass}
            >
              Stop narration
            </button>
            <button
              type="button"
              onClick={() =>
                setSceneIndex((index) =>
                  index === 0 ? sceneCount - 1 : index - 1,
                )
              }
              disabled={sceneIndex === 0}
              className={buttonClass}
            >
              Previous scene
            </button>
            <button
              type="button"
              onClick={() =>
                setSceneIndex((index) =>
                  Math.min(index + 1, sceneCount - 1),
                )
              }
              disabled={sceneIndex === activity.content.scenes.length - 1}
              className={buttonClass}
            >
              Next scene
            </button>
          </div>
          <p className="mt-2 text-xs text-slate-500">
            Narration uses your browser’s speech voice.
          </p>
        </section>
      );
    }
    case "slides-based": {
      const slideCount = activity.content.slides.length;
      return (
        <section className="mt-5 rounded-2xl bg-slate-50 p-6">
          <p className="text-sm font-semibold uppercase tracking-wide text-indigo-700">
            Slide {slideIndex + 1} of {activity.content.slides.length}
          </p>
          <h4 className="mt-3 text-2xl font-semibold text-slate-950">
            {activity.content.slides[slideIndex].title}
          </h4>
          <MarkdownRenderer
            className="mt-4"
            content={activity.content.slides[slideIndex].content}
          />
          <div className="mt-6 flex justify-between gap-3">
            <button
              type="button"
              onClick={() => setSlideIndex((index) => Math.max(index - 1, 0))}
              disabled={slideIndex === 0}
              className={buttonClass}
            >
              Previous
            </button>
            <button
              type="button"
              onClick={() =>
                setSlideIndex((index) =>
                  Math.min(index + 1, slideCount - 1),
                )
              }
              disabled={slideIndex === activity.content.slides.length - 1}
              className={buttonClass}
            >
              Next
            </button>
          </div>
        </section>
      );
    }
    case "online-coding":
      return (
        <section className="mt-5 space-y-4">
          <div className="rounded-xl bg-slate-50 p-5">
            <h4 className="font-semibold text-slate-950">Your task</h4>
            <MarkdownRenderer
              className="mt-3"
              content={activity.content.instructions}
            />
          </div>
          <label className="block text-sm font-medium text-slate-700">
            Your code
            <textarea
              spellCheck={false}
              value={code}
              onChange={(event) => {
                setCode(event.target.value);
                codingAnswer.reset();
                setSolutionVisible(false);
              }}
              onKeyDown={(event) => {
                if (event.key === "Tab") {
                  event.preventDefault();
                  const target = event.currentTarget;
                  const start = target.selectionStart;
                  const end = target.selectionEnd;
                  const nextCode = `${code.slice(0, start)}    ${code.slice(end)}`;
                  setCode(nextCode);
                  codingAnswer.reset();
                  setSolutionVisible(false);
                  requestAnimationFrame(() => {
                    target.selectionStart = start + 4;
                    target.selectionEnd = start + 4;
                  });
                }
              }}
              rows={Math.min(
                16,
                Math.max(6, activity.content.starter_code.split("\n").length + 2),
              )}
              className="mt-2 block w-full rounded-xl border border-slate-700 bg-slate-950 p-4 font-mono text-sm leading-6 text-slate-100"
            />
          </label>
          <button
            type="button"
            onClick={() => codingAnswer.mutate({ revealSolution: false })}
            disabled={codingAnswer.isPending}
            className="rounded-lg bg-indigo-700 px-4 py-2 font-semibold text-white hover:bg-indigo-800"
          >
            {codingAnswer.isPending ? "Checking…" : "Check answer"}
          </button>
          {codingAnswer.isError && (
            <p role="alert" className="rounded-xl bg-red-50 p-4 text-red-800">
              {codingAnswer.error.message}
            </p>
          )}
          {codingAnswer.data && (
            <div className="rounded-xl bg-slate-50 p-4">
              <p
                className={`font-semibold ${
                  codingAnswer.data.is_correct
                    ? "text-emerald-800"
                    : "text-amber-900"
                }`}
              >
                {codingAnswer.data.message}
              </p>
              <p className="mt-3 leading-7 text-slate-700">
                {activity.content.explanation}
              </p>
              {!codingAnswer.data.is_correct && (
                <button
                  type="button"
                  onClick={() => {
                    if (solutionVisible) {
                      setSolutionVisible(false);
                    } else if (codingAnswer.data?.solution) {
                      setSolutionVisible(true);
                    } else {
                      codingAnswer.mutate(
                        { revealSolution: true },
                        { onSuccess: () => setSolutionVisible(true) },
                      );
                    }
                  }}
                  disabled={codingAnswer.isPending}
                  className="mt-4 rounded-lg border border-indigo-700 px-4 py-2 font-semibold text-indigo-800 hover:bg-indigo-50 disabled:opacity-60"
                >
                  {codingAnswer.isPending
                    ? "Loading solution…"
                    : solutionVisible
                      ? "Hide solution"
                      : "Show solution"}
                </button>
              )}
              {solutionVisible && codingAnswer.data.solution && (
                <section className="mt-4 overflow-hidden rounded-xl border border-slate-700 bg-slate-950">
                  <h5 className="border-b border-slate-700 px-4 py-2 text-sm font-semibold text-slate-100">
                    Reference solution
                  </h5>
                  <div className="overflow-x-auto p-4">
                    <ol className="w-max min-w-full list-none font-mono text-sm leading-6 text-slate-100">
                      {codingAnswer.data.solution.split("\n").map((line, index) => (
                        <li
                          key={index}
                          className="grid grid-cols-[2rem_minmax(0,1fr)] gap-4"
                        >
                          <span
                            aria-hidden="true"
                            className="select-none text-right text-slate-500"
                          >
                            {index + 1}
                          </span>
                          <code className="whitespace-pre">{line || " "}</code>
                        </li>
                      ))}
                    </ol>
                  </div>
                </section>
              )}
            </div>
          )}
          <p className="text-xs text-slate-500">
            Your answer is compared with a reference solution after normalizing
            line endings and trailing whitespace. Code is not executed.
          </p>
        </section>
      );
  }
}
