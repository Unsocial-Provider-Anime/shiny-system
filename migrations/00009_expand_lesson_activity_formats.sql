alter table public.activities
  drop constraint if exists activities_presentation_format_check,
  drop constraint if exists activities_content_check;

alter table public.activities
  add constraint activities_presentation_format_check
    check (
      presentation_format in (
        'text-and-images',
        'interactive-simulations',
        'interactive-role-play-activities',
        'games',
        'animations',
        'slides-based',
        'online-coding'
      )
    ),
  add constraint activities_content_check
    check (
      jsonb_typeof(content) = 'object'
      and content ->> 'type' = presentation_format
    );
