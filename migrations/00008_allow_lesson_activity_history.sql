alter table public.activities
  drop constraint if exists activities_session_id_lesson_id_key;

create index activities_session_lesson_created_idx
  on public.activities (session_id, lesson_id, created_at desc);
