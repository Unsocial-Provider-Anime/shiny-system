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
