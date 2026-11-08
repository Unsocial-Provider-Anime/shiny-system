create table public.activities (
  id uuid primary key default gen_random_uuid(),
  session_id uuid not null
    references public.learning_sessions(id) on delete cascade,
  lesson_id varchar(80) not null,
  presentation_format varchar(32) not null
    check (presentation_format = 'text-and-images'),
  content jsonb not null
    check (
      jsonb_typeof(content) = 'object'
      and content ->> 'type' = 'text-and-images'
    ),
  created_at timestamptz not null default now(),
  unique (session_id, lesson_id)
);

alter table public.activities enable row level security;

grant select, insert, update, delete
  on public.activities
  to service_role;
