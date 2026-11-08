alter table public.courses
  add column visibility varchar(16) not null default 'restricted'
  check (visibility in ('public', 'restricted'));

update public.courses
  set visibility = 'public'
  where status = 'published';

create table public.course_access (
  course_id uuid not null
    references public.courses(id) on delete cascade,
  user_id bigint not null
    references public."user"(id) on delete cascade,
  granted_by bigint not null
    references public."user"(id) on delete cascade,
  granted_at timestamptz not null default now(),
  primary key (course_id, user_id)
);

create index course_access_user_idx
  on public.course_access (user_id, course_id);

alter table public.course_access enable row level security;

grant select, insert, update, delete
  on public.course_access
  to service_role;
grant select
  on public."user"
  to service_role;

drop function public.save_course_draft(
  bigint, varchar, text, varchar, jsonb, uuid
);

create function public.save_course_draft(
  p_created_by bigint,
  p_title varchar,
  p_description text,
  p_default_presentation_format varchar,
  p_plan jsonb,
  p_course_id uuid default null,
  p_visibility varchar default 'restricted'
)
returns table (course_id uuid, version_id uuid, version_number integer)
language plpgsql
as $$
declare
  target_course_id uuid;
  next_version_number integer;
  new_version_id uuid;
begin
  if p_course_id is null then
    insert into public.courses (
      created_by,
      title,
      description,
      default_presentation_format,
      visibility
    )
    values (
      p_created_by,
      p_title,
      p_description,
      p_default_presentation_format,
      p_visibility
    )
    returning id into target_course_id;
  else
    select id
      into target_course_id
      from public.courses
      where id = p_course_id
        and created_by = p_created_by
        and status = 'draft'
      for update;

    if target_course_id is null then
      raise exception 'draft course not found';
    end if;

    update public.courses
      set title = p_title,
          description = p_description,
          default_presentation_format = p_default_presentation_format,
          visibility = p_visibility,
          updated_at = now()
      where id = target_course_id;
  end if;

  select coalesce(max(cv.version_number), 0) + 1
    into next_version_number
    from public.course_versions cv
    where cv.course_id = target_course_id;

  insert into public.course_versions (course_id, version_number, plan)
    values (target_course_id, next_version_number, p_plan)
    returning id into new_version_id;

  update public.courses
    set current_version_id = new_version_id,
        updated_at = now()
    where id = target_course_id;

  return query
    select target_course_id, new_version_id, next_version_number;
end;
$$;

revoke all on function public.save_course_draft(
  bigint, varchar, text, varchar, jsonb, uuid, varchar
) from public, anon, authenticated;
grant execute on function public.save_course_draft(
  bigint, varchar, text, varchar, jsonb, uuid, varchar
) to service_role;

create or replace function public.start_learning_session(
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
        and (
          c.visibility = 'public'
          or c.created_by = p_user_id
          or exists (
            select 1
              from public.course_access ca
              where ca.course_id = c.id
                and ca.user_id = p_user_id
          )
        )
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

revoke all on function public.start_learning_session(
  bigint, uuid, uuid, varchar, varchar
) from public, anon, authenticated;
grant execute on function public.start_learning_session(
  bigint, uuid, uuid, varchar, varchar
) to service_role;

create function public.set_course_visibility(
  p_course_id uuid,
  p_created_by bigint,
  p_visibility varchar
)
returns setof public.courses
language sql
as $$
  update public.courses
    set visibility = p_visibility,
        updated_at = now()
    where id = p_course_id
      and created_by = p_created_by
    returning *;
$$;

revoke all on function public.set_course_visibility(
  uuid, bigint, varchar
) from public, anon, authenticated;
grant execute on function public.set_course_visibility(
  uuid, bigint, varchar
) to service_role;
