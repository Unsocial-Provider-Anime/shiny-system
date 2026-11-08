revoke all on function public.save_course_draft(
  bigint, varchar, text, varchar, jsonb, uuid, varchar
) from public, anon, authenticated;

grant execute on function public.save_course_draft(
  bigint, varchar, text, varchar, jsonb, uuid, varchar
) to public, anon, authenticated;
