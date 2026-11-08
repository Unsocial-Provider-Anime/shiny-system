# Backend

## Supabase setup

Apply the SQL files in `../migrations` in numeric order to the Supabase project.
The backend uses `SUPABASE_URL` and `SUPABASE_KEY`; configure `SUPABASE_KEY`
with a server-only service-role key so the API can call the learning-session
RPCs. Never put this key in the frontend or expose it to browsers.

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
  generates and saves the current lesson's validated `text-and-images` activity.
  Repeated requests return the saved activity.
- `POST /api/v1/learning-sessions/{session_id}/lessons/{lesson_id}/complete`
  saves completion and advances to the next lesson.

Apply migration `00004_create_lesson_activities.sql` to persist lesson
activities.

The user and learning-session tables have RLS enabled without browser-facing
policies. The API uses the server-side service-role key and enforces ownership
using the email account's internal user ID.