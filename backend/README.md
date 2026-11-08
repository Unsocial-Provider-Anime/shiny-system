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

## Learning sessions

- `POST /api/v1/learning-sessions` starts or resumes the learner's active
  session for a published course.
- `GET /api/v1/learning-sessions` lists the signed-in learner's sessions.
- `GET /api/v1/learning-sessions/{session_id}` loads a session pinned to its
  published course version.
- `POST /api/v1/learning-sessions/{session_id}/lessons/{lesson_id}/complete`
  saves completion and advances to the next lesson.

The user and learning-session tables have RLS enabled without browser-facing
policies. The API uses the server-side service-role key and enforces ownership
using the email account's internal user ID.