create table public.courses (
  id uuid primary key default gen_random_uuid(),
  created_by bigint not null
    references public."user"(id) on delete cascade,
  title varchar(200) not null check (length(btrim(title)) > 0),
  description text not null check (length(btrim(description)) > 0),
  status varchar(16) not null default 'draft'
    check (status in ('draft', 'published', 'archived')),
  default_presentation_format varchar(40) not null default 'text-and-images'
    check (
      default_presentation_format in (
        'text-and-images',
        'interactive-simulations',
        'interactive-role-play-activities',
        'games',
        'animations',
        'slides-based',
        'online-coding'
      )
    ),
  current_version_id uuid,
  published_version_id uuid,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  published_at timestamptz,
  constraint courses_published_state_check
    check (
      status <> 'published'
      or (published_at is not null and published_version_id is not null)
    ),
  constraint courses_draft_state_check
    check (status <> 'draft' or published_at is null)
);

create table public.course_versions (
  id uuid primary key default gen_random_uuid(),
  course_id uuid not null
    references public.courses(id) on delete cascade,
  version_number integer not null check (version_number > 0),
  plan jsonb not null check (jsonb_typeof(plan) = 'object'),
  created_at timestamptz not null default now(),
  constraint course_versions_course_version_key
    unique (course_id, version_number),
  constraint course_versions_course_id_id_key
    unique (course_id, id)
);

alter table public.courses
  add constraint courses_current_version_fk
  foreign key (id, current_version_id)
  references public.course_versions(course_id, id);

alter table public.courses
  add constraint courses_published_version_fk
  foreign key (id, published_version_id)
  references public.course_versions(course_id, id);

create index courses_published_catalogue_idx
  on public.courses (published_at desc)
  where status = 'published';

create index courses_owner_updated_idx
  on public.courses (created_by, updated_at desc);

alter table public.courses enable row level security;
alter table public.course_versions enable row level security;

create function public.save_course_draft(
  p_created_by bigint,
  p_title varchar,
  p_description text,
  p_default_presentation_format varchar,
  p_plan jsonb,
  p_course_id uuid default null
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
      default_presentation_format
    )
    values (
      p_created_by,
      p_title,
      p_description,
      p_default_presentation_format
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

create function public.publish_course(
  p_course_id uuid,
  p_created_by bigint
)
returns setof public.courses
language plpgsql
as $$
declare
  target_version_id uuid;
begin
  select current_version_id
    into target_version_id
    from public.courses
    where id = p_course_id
      and created_by = p_created_by
      and status = 'draft'
    for update;

  if target_version_id is null then
    raise exception 'draft course not found';
  end if;

  update public.courses
    set status = 'published',
        published_version_id = target_version_id,
        published_at = now(),
        updated_at = now()
    where id = p_course_id;

  return query
    select c.*
      from public.courses c
      where c.id = p_course_id;
end;
$$;
