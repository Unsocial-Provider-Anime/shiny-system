# Backend

## Supabase setup

Apply the SQL files in `../migrations` in numeric order to the Supabase project.
The backend uses `SUPABASE_URL` and `SUPABASE_KEY`; configure `SUPABASE_KEY`
with a server-only service-role key so the API can call the database RPCs.
Never put this key in the frontend or expose it to browsers. Migration `00006`
grants execute permission on `save_course_draft` to `public`, `anon`, and
`authenticated`. This function-level grant does not grant those roles direct
table access. If an RPC reports `permission denied for function`, verify that
migration `00006` has been applied after the function was created.

The API stores each email-only demo account in `public."user"` and uses that
row's numeric ID for course ownership and learning sessions. The email-only
sign-in does not verify control of the email address, so it is for a trusted
prototype only and is not suitable for production accounts or sensitive data.
Set a long, random `SESSION_SECRET` and use HTTPS outside development.

## Course sharing

Apply migration `00005_course_sharing.sql` after the earlier migrations.
Courses default to `restricted`; existing published courses are migrated as
`public` to preserve their prior discoverability. Course owners can set a
draft's visibility to `public` or `restricted`, then grant or revoke access for
existing accounts using the course access endpoints. Public courses are
discoverable without signing in; restricted courses are visible only to their
owner and users with a grant. Owners may change visibility after publishing
without changing the published content version. Pending invites for email
addresses without an account are not supported.

Users may create courses and learn from courses using the same account. Course
ownership does not grant access to another user's restricted course, and access
is checked both by the API and when the database creates a learning session.

## Learning sessions

- `POST /api/v1/learning-sessions` starts or resumes the learner's active
  session for a published course.
- `GET /api/v1/learning-sessions` lists the signed-in learner's sessions.
- `GET /api/v1/learning-sessions/{session_id}` loads a session pinned to its
  published course version.
- `POST /api/v1/learning-sessions/{session_id}/lessons/{lesson_id}/activities`
  returns the latest saved activity for the current or a completed lesson.
  Send `{"regenerate": true}` to save a new activity version without removing
  earlier versions.
- `POST /api/v1/learning-sessions/{session_id}/lessons/{lesson_id}/complete`
  saves completion and advances to the next lesson.

Apply migration `00004_create_lesson_activities.sql` to persist lesson
activities, then apply migration `00008_allow_lesson_activity_history.sql` to
preserve regenerated activity versions.

Apply migration `00007_create_learning_interactions.sql` to persist guided
learning interactions. The session API currently supports the `quiz-me` action:
it generates a validated multiple-choice question for the current lesson,
records the learner's selected option, and returns feedback. Learners can reload
the session and resume their saved quiz interactions. It can also generate
quizzes for completed lessons without changing lesson progress.

Apply migration `00007_create_learning_interactions.sql` to persist guided
learning interactions. The session API currently supports the `quiz-me` action:
it generates a validated multiple-choice question for the current lesson,
records the learner's selected option, and returns feedback. Learners can reload
the session and resume their saved quiz interactions.

The user and learning-session tables have RLS enabled without browser-facing
policies. The API uses the server-side service-role key and enforces ownership
using the email account's internal user ID.

## AI generation diagnostics

Course-generation responses from the AI provider are written to backend logs
at `INFO` level. AI-generation schema validation failures include the failed
fields at `WARNING` level, and truncated lesson activity responses are
identified in the backend logs. The API continues to return generic errors to
clients. Generated output may reflect course briefs and learner context, so
restrict access to backend logs accordingly.