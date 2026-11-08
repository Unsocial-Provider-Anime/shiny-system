create table public.learning_interactions (
  id uuid primary key default gen_random_uuid(),
  session_id uuid not null
    references public.learning_sessions(id) on delete cascade,
  lesson_id varchar(80) not null,
  kind varchar(16) not null check (kind = 'action'),
  action varchar(32) not null check (action = 'quiz-me'),
  content jsonb not null
    check (
      jsonb_typeof(content) = 'object'
      and jsonb_typeof(content -> 'question') = 'string'
      and jsonb_typeof(content -> 'options') = 'array'
      and jsonb_typeof(content -> 'correct_option') = 'number'
      and jsonb_typeof(content -> 'explanation') = 'string'
    ),
  selected_option integer,
  created_at timestamptz not null default now(),
  constraint learning_interactions_selected_option_check
    check (selected_option is null or selected_option >= 0)
);

create index learning_interactions_session_created_idx
  on public.learning_interactions (session_id, created_at);

alter table public.learning_interactions enable row level security;
grant select, insert, update, delete
  on public.learning_interactions
  to public, anon, authenticated;
