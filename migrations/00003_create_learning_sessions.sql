create table public.learning_sessions (
  id uuid primary key default gen_random_uuid(),
  user_id bigint not null
    references public."user"(id) on delete cascade,
  course_id uuid not null
    references public.courses(id) on delete cascade,
  course_version_id uuid not null,
  status varchar(16) not null default 'active'
    check (status in ('active', 'completed', 'abandoned')),
  current_module_id varchar(80),
  current_lesson_id varchar(80),
  started_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  completed_at timestamptz,
  constraint learning_sessions_course_version_fk
    foreign key (course_id, course_version_id)
    references public.course_versions(course_id, id),
  constraint learning_sessions_completion_check
    check (
      (status = 'completed' and completed_at is not null)
      or (status <> 'completed' and completed_at is null)
    ),
  constraint learning_sessions_current_lesson_check
    check (
      (current_module_id is null and current_lesson_id is null)
      or (current_module_id is not null and current_lesson_id is not null)
    )
);

create unique index learning_sessions_one_active_course_idx
  on public.learning_sessions (user_id, course_id)
  where status = 'active';

create index learning_sessions_user_updated_idx
  on public.learning_sessions (user_id, updated_at desc);

create table public.lesson_progress (
  session_id uuid not null
    references public.learning_sessions(id) on delete cascade,
  lesson_id varchar(80) not null,
  status varchar(16) not null default 'completed'
    check (status = 'completed'),
  completed_at timestamptz not null default now(),
  primary key (session_id, lesson_id)
);

alter table public."user" enable row level security;
alter table public.learning_sessions enable row level security;
alter table public.lesson_progress enable row level security;

grant select, insert, update, delete
  on public."user"
  to service_role;
grant select, insert, update, delete
  on public.learning_sessions, public.lesson_progress
  to service_role;

create function public.start_learning_session(
  p_user_id bigint,
  p_course_id uuid,
  p_course_version_id uuid,
  p_first_module_id varchar,
  p_first_lesson_id varchar
)
returns setof public.learning_sessions
language plpgsql
as $$
begin
  if not exists (
    select 1
      from public.courses c
      where c.id = p_course_id
        and c.status = 'published'
        and c.published_version_id = p_course_version_id
  ) then
    raise exception 'published course not found';
  end if;

  return query
    insert into public.learning_sessions (
      user_id,
      course_id,
      course_version_id,
      current_module_id,
      current_lesson_id
    )
    values (
      p_user_id,
      p_course_id,
      p_course_version_id,
      p_first_module_id,
      p_first_lesson_id
    )
    on conflict (user_id, course_id) where status = 'active'
    do update set updated_at = now()
    returning *;
end;
$$;

create function public.complete_learning_lesson(
  p_user_id bigint,
  p_session_id uuid,
  p_lesson_id varchar
)
returns setof public.learning_sessions
language plpgsql
as $$
declare
  target_session public.learning_sessions%rowtype;
  course_plan jsonb;
  next_module_id varchar(80);
  next_lesson_id varchar(80);
begin
  select *
    into target_session
    from public.learning_sessions
    where id = p_session_id
      and user_id = p_user_id
    for update;

  if not found or target_session.status <> 'active' then
    raise exception 'active learning session not found';
  end if;
  if target_session.current_lesson_id <> p_lesson_id then
    raise exception 'lesson is not the current lesson';
  end if;

  select cv.plan
    into course_plan
    from public.course_versions cv
    where cv.course_id = target_session.course_id
      and cv.id = target_session.course_version_id;

  if not exists (
    select 1
      from jsonb_array_elements(course_plan -> 'modules') as module(value)
      cross join lateral jsonb_array_elements(module.value -> 'lessons') as lesson(value)
      where lesson.value ->> 'lesson_id' = p_lesson_id
        and module.value ->> 'module_id' = target_session.current_module_id
  ) then
    raise exception 'lesson does not belong to the session plan';
  end if;

  insert into public.lesson_progress (session_id, lesson_id)
    values (target_session.id, p_lesson_id)
    on conflict (session_id, lesson_id)
    do update set completed_at = excluded.completed_at;

  with ordered_lessons as (
    select
      module.value ->> 'module_id' as module_id,
      lesson.value ->> 'lesson_id' as lesson_id,
      row_number() over (
        order by module.ordinality, lesson.ordinality
      ) as lesson_number
    from jsonb_array_elements(course_plan -> 'modules')
      with ordinality as module(value, ordinality)
    cross join lateral jsonb_array_elements(module.value -> 'lessons')
      with ordinality as lesson(value, ordinality)
  ),
  current_lesson as (
    select lesson_number
      from ordered_lessons
      where lesson_id = p_lesson_id
  )
  select ordered_lessons.module_id, ordered_lessons.lesson_id
    into next_module_id, next_lesson_id
    from ordered_lessons
    cross join current_lesson
    where ordered_lessons.lesson_number = current_lesson.lesson_number + 1;

  if next_lesson_id is null then
    update public.learning_sessions
      set status = 'completed',
          current_module_id = null,
          current_lesson_id = null,
          completed_at = now(),
          updated_at = now()
      where id = target_session.id;
  else
    update public.learning_sessions
      set current_module_id = next_module_id,
          current_lesson_id = next_lesson_id,
          updated_at = now()
      where id = target_session.id;
  end if;

  return query
    select *
      from public.learning_sessions
      where id = target_session.id;
end;
$$;

revoke all on function public.start_learning_session(
  bigint, uuid, uuid, varchar, varchar
) from public, anon, authenticated;
grant execute on function public.start_learning_session(
  bigint, uuid, uuid, varchar, varchar
) to service_role;

revoke all on function public.complete_learning_lesson(
  bigint, uuid, varchar
) from public, anon, authenticated;
grant execute on function public.complete_learning_lesson(
  bigint, uuid, varchar
) to service_role;
