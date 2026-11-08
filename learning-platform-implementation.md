# Learning Platform: Greenfield Implementation

## 1. Product goal

Build a platform where an instructor or learner can design a course with AI, review and save its learning plan, and then learn through a guided session. The lesson page should feel like an interactive learning workspace rather than a chat room. Learners can ask questions and use actions to ask the AI to explain, practice, or present the current material in another format.

This document assumes a new project with no existing frontend or backend behavior.

## 2. Core product concepts

- **Course:** A titled, reusable learning offering, with a description, target audience, learning outcomes, and a structured plan.
- **Course owner:** The user who can edit a course and manage its sharing settings. Any user can own courses and also learn from public, shared, or personally owned courses.
- **Course access:** Published courses are either public or restricted. Restricted courses are visible only to their owner and users explicitly granted access.
- **Module:** A group of related lessons in a course.
- **Lesson:** A bounded learning step with objectives, content guidance, activities, and a completion check.
- **Learning session:** One learner's progress through a particular version of a course.
- **Activity:** A rendered learning experience for a lesson, such as an explanation, quiz, role-play, or simulation.
- **Interaction:** A learner action or message that may ask the AI to respond or update the current activity.

Keep the course plan distinct from generated lesson content. The plan describes what to teach; the session contains a learner's progress and generated experiences.

## 3. Main user journeys

### Course authoring

1. The author enters a topic and, optionally, a learning goal, audience or experience level, time budget, constraints, and preferred formats.
2. The backend asks the AI to create a structured course proposal.
3. The author reviews and edits the title, description, outcomes, modules, lessons, and activities.
4. The author saves the course as a draft with public or restricted access and can publish it when ready.
5. For a restricted course, the owner can grant or revoke access for existing user accounts.
6. The owner can change a published course's visibility without creating a new content version.

The author should be able to revise a proposal before saving it. Do not silently publish AI-generated plans.

### Learner starting a course

1. The learner browses public courses and courses shared with them.
2. The learner opens a course detail page and reviews its description, outcomes, requirements, and learning plan.
3. The learner chooses **Start learning**.
4. The backend creates a learning session tied to the course and a snapshot of its plan.
5. The frontend navigates to the new session.

### Learner studying

1. The session page loads the current lesson and progress.
2. The backend generates the initial activity for that lesson.
3. The frontend renders the activity in a learning-focused layout, with lesson navigation and progress.
4. The learner can continue, answer a check, ask a question, or choose an action such as **Explain another way**, **Give an example**, or **Quiz me**.
5. The learner can also request a different presentation format for the current learning objective.
6. The backend saves the interaction and returns validated, structured content. The frontend renders it using the matching activity component.
7. The learner can leave and resume the session later.

## 4. Experience and interface

### Course pages

- Course catalogue: searchable or filterable cards for published courses.
- Course detail: goal, intended audience, estimated effort, outcomes, prerequisites, and module/lesson outline.
- Course designer: input form, generated proposal, editable plan, and explicit save/publish controls.

### Learning session page

Use a three-area layout rather than a full-screen chat transcript:

1. **Progress navigation:** course title, modules, lessons, completion states, and current lesson.
2. **Learning canvas:** the current explanation or activity, rendered according to its content type.
3. **Learner controls:** suggested actions and an optional question input. Conversation can be available as supporting context, but should not dominate the page.

On small screens, collapse progress navigation and place learner controls below the learning canvas.

The page should show loading, retryable error, empty, and completed states. Preserve a learner's current lesson and activity when navigating away and returning.

## 5. Presentation formats

Use stable format identifiers in the API and database:

| Identifier | Initial rendering approach |
|---|---|
| `text-and-images` | Formatted text, examples, and optional safe image references or diagram descriptions |
| `interactive-simulations` | A scenario, state, learner choices, and consequences |
| `interactive-role-play-activities` | Roles, goal, current turn, and response choices or free-text input |
| `games` | Rules, objective, state, allowed actions, and feedback |
| `animations` | A sequence of scenes with visual directions and narration |
| `slides-based` | Ordered slides with titles, concise content, and navigation |
| `online-coding` | Task instructions, starter code, expected behavior, and verification guidance |

Use `text-and-images` as the default. A format change should adapt the current lesson or objective; it should not create a new course or reset session progress.

Formats differ in how they behave, so avoid treating them as styling options on one generic text response. Validate each format's payload and render it with a known frontend component. Do not execute arbitrary model-generated scripts or HTML. If an activity later needs an iframe, only embed trusted, explicitly allowed origins in a sandboxed frame; do not let model output choose an unrestricted URL.

## 6. Suggested architecture

Start with a separately testable frontend and backend communicating over a versioned JSON API:

- **Frontend:** course authoring and catalogue pages, course detail, session workspace, and format-specific activity components.
- **Backend API:** authentication, authorization, course and session lifecycle, AI orchestration, validation, and persistence.
- **Relational database:** users, courses, course plan versions, modules, lessons, sessions, activity results, and interaction history.
- **AI provider adapter:** one server-side integration for structured generation, with timeouts, error reporting, and schema validation.

Keep provider credentials on the server. Treat AI output as untrusted input: parse it, validate it against a schema, and return a clear service error if it is malformed. Do not silently replace invalid output with an empty or success-shaped response.

## 7. Data model

The following is a logical model; names can be adapted to the chosen database.

### `courses`

- `id`
- `created_by`
- `title`
- `description`
- `status` (`draft`, `published`, `archived`)
- `default_presentation_format`
- `created_at`, `updated_at`, optional `published_at`

### `course_versions`

- `id`
- `course_id`
- `version_number`
- `plan` (validated structured course plan)
- `created_at`

Publishing or materially editing a course creates a new plan version. Existing sessions remain attached to the version they started with.

### Course plan structure

Each plan should include:

- `overview`
- `target_audience`
- `assumptions`
- `learning_outcomes`
- `prerequisites`
- `modules[]`
- `milestones`
- `capstone`

Each module should include an ordered list of lessons. Each lesson should include:

- stable lesson identifier within the plan version
- title and purpose
- two or three observable objectives
- key topics in order
- suggested activity and format
- completion check
- prerequisite lesson identifiers, if any
- approximate effort, when known

### `learning_sessions`

- `id`
- `user_id`
- `course_id`
- `course_version_id`
- `status` (`active`, `completed`, `abandoned`)
- `current_module_id`, `current_lesson_id`
- `started_at`, `updated_at`, optional `completed_at`

### `lesson_progress`

- `id`
- `session_id`
- `lesson_id`
- `status` (`not_started`, `in_progress`, `completed`)
- `completed_at`
- optional learner response or check result

### `activities`

- `id`
- `session_id`
- `lesson_id`
- `presentation_format`
- `content` (validated JSON matching that format's schema)
- `created_at`

### `interactions`

- `id`
- `session_id`
- optional `activity_id`
- `kind` (`question`, `action`, `answer`, `format_change`)
- `input` (structured action data or learner text)
- `created_at`

Persist only the context needed to resume a session and provide relevant AI context. Enforce ownership checks for every session and course operation.

## 8. API outline

All endpoints return JSON, use consistent error objects, and require authentication where they access private or learner-specific data.

### Course design and management

- `POST /api/v1/course-drafts` — generate a proposed course plan from author input; does not publish or save implicitly.
- `POST /api/v1/courses` — save a reviewed course as a draft.
- `GET /api/v1/courses` — list published courses, with optional search and filters.
- `GET /api/v1/courses/{course_id}` — return course details and the published plan.
- `PATCH /api/v1/courses/{course_id}` — update an owned draft.
- `POST /api/v1/courses/{course_id}/publish` — publish an owned course and its current plan version.
- `PATCH /api/v1/courses/{course_id}/visibility` — change an owned course's visibility without changing its published plan version.
- `GET /api/v1/courses/{course_id}/access` — list users with access to an owned course.
- `POST /api/v1/courses/{course_id}/access` — grant an existing user access by email.
- `DELETE /api/v1/courses/{course_id}/access/{user_id}` — revoke a user's access.

### Learning sessions

- `POST /api/v1/learning-sessions` — create a session for a published course and pin its course version. Request includes `course_id` and optional learning preferences.
- `GET /api/v1/learning-sessions` — list the authenticated learner's sessions.
- `GET /api/v1/learning-sessions/{session_id}` — return session state, plan snapshot, progress, and current activity.
- `POST /api/v1/learning-sessions/{session_id}/lessons/{lesson_id}/activities` — generate the initial activity or a requested format for a lesson.
- `POST /api/v1/learning-sessions/{session_id}/interactions` — submit a question, named action, learner response, or format-change request.
- `POST /api/v1/learning-sessions/{session_id}/lessons/{lesson_id}/complete` — record completion after the learner completes the lesson check.

Do not expose a generic endpoint that accepts arbitrary system prompts from the browser. The backend maps named learner actions to server-owned instructions and supplies only the authorized course, lesson, session, and relevant interaction context.

### Example interaction request

```json
{
  "kind": "action",
  "action": "quiz-me",
  "activity_id": "activity-uuid"
}
```

### Example activity response

```json
{
  "activity_id": "activity-uuid",
  "lesson_id": "lesson-identifier",
  "presentation_format": "slides-based",
  "content": {
    "type": "slides-based",
    "slides": [
      {
        "title": "The core idea",
        "blocks": [
          {
            "type": "text",
            "text": "A concise explanation grounded in this lesson."
          }
        ]
      }
    ]
  },
  "suggested_actions": ["ask-question", "give-example", "quiz-me"]
}
```

The server validates the response before persisting or returning it. The frontend validates the API response too and displays an actionable error if a payload cannot be rendered.

## 9. AI generation responsibilities

### Course plan generation

The course-design prompt should ask for a complete plan matching a strict schema. Include the author's input and require the model to:

- work toward the stated learner goal;
- sequence prerequisites before dependent material;
- use observable outcomes and active practice;
- scale scope to the learner's experience and available time;
- mark important assumptions;
- avoid invented sources and unsupported precision.

### Lesson activity generation

For each generation, provide only relevant context:

- course title, goal, outcomes, and pinned plan version;
- current module and lesson details;
- learner preferences and experience level, if provided;
- current presentation format;
- relevant prior activity and recent interactions;
- requested action, when applicable.

Require a structured response matching the requested format. Keep system instructions and action mappings on the backend. Apply request timeouts and reasonable size limits; surface provider and validation failures as errors rather than storing invalid content.

## 10. Security, privacy, and reliability

- Authenticate learners and authors; check ownership on private resources and author-only operations.
- Validate identifiers, enum values, lengths, and nested JSON on every API boundary.
- Use parameterized database operations and least-privilege database access.
- Do not expose AI provider secrets or internal prompts to the frontend.
- Treat learner text and model output as untrusted. Sanitize rendered Markdown and disallow unsafe HTML.
- Rate-limit expensive generation endpoints and set provider timeouts.
- Make session creation and completion operations safe against accidental duplicate submissions where practical.
- Record operational errors without logging secrets or unnecessary learner content.
- Explain what learning data is saved and provide appropriate retention and deletion behavior.

## 11. Implementation sequence

### Phase 1: Product foundation

- Establish frontend and backend applications, environment configuration, database migrations, and automated checks.
- Define shared API schemas and error conventions.
- Add authentication and course/session ownership rules.

### Phase 2: Course design and discovery

- Implement course plan schema and AI draft generation.
- Build the author review/edit/save flow.
- Build published course catalogue and detail pages.
- Add draft/publish lifecycle and immutable plan versions.

### Phase 3: Session lifecycle and first lesson

- Implement session creation, plan-version pinning, session listing, and resume.
- Build the progress navigation and learning canvas.
- Generate and render the initial `text-and-images` lesson activity.
- Persist learner progress and lesson completion.

### Phase 4: Guided interactions

- Add named actions such as explain differently, give an example, and quiz me.
- Add learner questions with relevant course and lesson context.
- Persist interaction history and render responses in the learning canvas rather than replacing it with a chat room.

### Phase 5: Additional formats

- Add one format at a time, beginning with slides or role-play.
- Define and validate a separate content schema and renderer for each format.
- Add simulations, games, animations, and coding only when their interaction state and completion behavior are designed.

## 12. Acceptance criteria for the first usable release

- An author can generate, edit, save, and publish a course plan.
- A course owner can choose public or restricted access and manage access for existing users.
- A learner can browse a published course and inspect its plan before starting.
- A learner can start a public course or a restricted course shared with them; other users cannot view or start a restricted course.
- A course owner can also start a separate learner session for their own published course.
- Starting a course creates a session pinned to the published plan version and opens that session.
- A learner can view the initial lesson in a learning-focused interface, not only as a chat transcript.
- A learner can request at least one named AI action and see a validated response in the lesson experience.
- Session progress is saved and can be resumed.
- Learners cannot access another user's private session by changing an identifier.
- Invalid AI output and provider failures are visible errors and do not result in malformed saved activities.
