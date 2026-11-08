import { z } from "zod";

const errorSchema = z.object({
  detail: z.union([
    z.string(),
    z.object({ message: z.string() }).passthrough(),
  ]),
});

export async function apiRequest<T>(
  path: string,
  schema: z.ZodType<T>,
  init?: RequestInit,
): Promise<T> {
  const response = await fetch(path, {
    ...init,
    credentials: "same-origin",
    headers: {
      ...(init?.body ? { "Content-Type": "application/json" } : {}),
      ...init?.headers,
    },
  });
  const result: unknown = await response.json();
  if (!response.ok) {
    const parsedError = errorSchema.safeParse(result);
    const detail = parsedError.success ? parsedError.data.detail : undefined;
    throw new Error(
      typeof detail === "string"
        ? detail
        : (detail?.message ?? "The request could not be completed."),
    );
  }
  return schema.parse(result);
}

const LessonSchema = z
  .object({
    lesson_id: z.string(),
    title: z.string(),
    purpose: z.string(),
    objectives: z.array(z.string()),
    key_topics: z.array(z.string()),
    suggested_activity: z
      .object({
        title: z.string(),
        description: z.string(),
        presentation_format: z.enum([
          "text-and-images",
          "interactive-simulations",
          "interactive-role-play-activities",
          "games",
          "animations",
          "slides-based",
          "online-coding",
        ]),
      })
      .passthrough(),
    completion_check: z.string(),
    prerequisite_lesson_ids: z.array(z.string()),
    estimated_minutes: z.number().nullable(),
  })
  .passthrough();

const ModuleSchema = z
  .object({
    module_id: z.string(),
    title: z.string(),
    description: z.string(),
    lessons: z.array(LessonSchema),
  })
  .passthrough();

export const CoursePlanSchema = z
  .object({
    overview: z.string(),
    target_audience: z.string(),
    assumptions: z.array(z.string()),
    learning_outcomes: z.array(z.string()),
    prerequisites: z.array(z.string()),
    modules: z.array(ModuleSchema),
    milestones: z.array(z.string()),
    capstone: z.string(),
  })
  .passthrough();

export const CourseDraftProposalSchema = z
  .object({
    title: z.string().min(1).max(200),
    description: z.string().min(1).max(4000),
    default_presentation_format: z.enum([
      "text-and-images",
      "interactive-simulations",
      "interactive-role-play-activities",
      "games",
      "animations",
      "slides-based",
      "online-coding",
    ]),
    visibility: z.enum(["public", "restricted"]),
    plan: CoursePlanSchema,
  })
  .passthrough();

export const CourseSaveResponseSchema = z.object({
  course_id: z.string(),
  version_id: z.string(),
  version_number: z.number(),
  status: z.literal("draft"),
  visibility: z.enum(["public", "restricted"]),
});

export const CourseSchema = z
  .object({
    id: z.string(),
    title: z.string(),
    description: z.string(),
    status: z.enum(["draft", "published", "archived"]).optional(),
    visibility: z.enum(["public", "restricted"]).optional(),
    is_owner: z.boolean().optional(),
    plan: CoursePlanSchema,
  })
  .passthrough();

export const CourseAccessSchema = z
  .object({
    user_id: z.number(),
    email: z.string().nullable(),
    granted_at: z.string(),
  })
  .passthrough();

export const CourseVisibilityResponseSchema = z.object({
  course_id: z.string(),
  visibility: z.enum(["public", "restricted"]),
});

export const LearningSessionSchema = z
  .object({
    id: z.string(),
    course_id: z.string(),
    course_version_id: z.string(),
    status: z.enum(["active", "completed", "abandoned"]),
    current_module_id: z.string().nullable(),
    current_lesson_id: z.string().nullable(),
    started_at: z.string(),
    updated_at: z.string(),
    completed_at: z.string().nullable(),
    course: z
      .object({
        id: z.string(),
        title: z.string(),
        description: z.string(),
      })
      .passthrough(),
    version_number: z.number(),
    plan: CoursePlanSchema,
    completed_lessons: z.array(
      z
        .object({
          lesson_id: z.string(),
          status: z.literal("completed"),
          completed_at: z.string(),
        })
        .passthrough(),
    ),
  })
  .passthrough();

export const LessonActivitySchema = z
  .object({
    id: z.string(),
    session_id: z.string(),
    lesson_id: z.string(),
    presentation_format: z.enum([
      "text-and-images",
      "interactive-simulations",
      "interactive-role-play-activities",
      "games",
      "animations",
      "slides-based",
      "online-coding",
    ]),
    content: z.discriminatedUnion("type", [
      z.object({
        type: z.literal("text-and-images"),
        content: z.string(),
        image_descriptions: z.array(z.string()),
      }),
      z.object({
        type: z.literal("interactive-simulations"),
        scenario: z.string(),
        choices: z.array(z.object({ label: z.string(), consequence: z.string() })),
        learning_point: z.string(),
      }),
      z.object({
        type: z.literal("interactive-role-play-activities"),
        scenario: z.string(),
        learner_role: z.string(),
        partner_role: z.string(),
        opening_prompt: z.string(),
        response_choices: z.array(
          z.object({ response: z.string(), feedback: z.string() }),
        ),
      }),
      z.object({
        type: z.literal("games"),
        objective: z.string(),
        instructions: z.string(),
        challenge: z.string(),
        choices: z.array(
          z.object({
            label: z.string(),
            is_correct: z.boolean(),
            feedback: z.string(),
          }),
        ),
      }),
      z.object({
        type: z.literal("animations"),
        scenes: z.array(
          z.object({
            title: z.string(),
            visual_description: z.string(),
            narration: z.string(),
          }),
        ),
      }),
      z.object({
        type: z.literal("slides-based"),
        slides: z.array(z.object({ title: z.string(), content: z.string() })),
      }),
      z.object({
        type: z.literal("online-coding"),
        instructions: z.string(),
        starter_code: z.string(),
        explanation: z.string(),
      }),
    ]),
    created_at: z.string(),
  })
  .passthrough()
  .refine((activity) => activity.presentation_format === activity.content.type, {
    message: "Activity format must match its content type.",
  });

export const CodingAnswerSchema = z.object({
  is_correct: z.boolean(),
  message: z.string(),
  solution: z.string().nullable(),
});

export const QuizInteractionSchema = z
  .object({
    id: z.string(),
    session_id: z.string(),
    lesson_id: z.string(),
    kind: z.literal("action"),
    action: z.literal("quiz-me"),
    question: z.string(),
    options: z.array(z.string()),
    selected_option: z.number().nullable(),
    is_correct: z.boolean().nullable(),
    explanation: z.string().nullable(),
    created_at: z.string(),
  })
  .passthrough();

export type Lesson = z.infer<typeof LessonSchema>;
export type Module = z.infer<typeof ModuleSchema>;
export type CoursePlan = z.infer<typeof CoursePlanSchema>;
export type Course = z.infer<typeof CourseSchema>;
export type LearningSession = z.infer<typeof LearningSessionSchema>;
export type LessonActivity = z.infer<typeof LessonActivitySchema>;
export type QuizInteraction = z.infer<typeof QuizInteractionSchema>;

export function lessonCount(plan: CoursePlan): number {
  return plan.modules.reduce((total, module) => total + module.lessons.length, 0);
}

export function lessonById(
  plan: CoursePlan,
  lessonId: string | null,
): Lesson | null {
  if (lessonId === null) {
    return null;
  }
  return (
    plan.modules.flatMap((module) => module.lessons).find(
      (lesson) => lesson.lesson_id === lessonId,
    ) ?? null
  );
}
