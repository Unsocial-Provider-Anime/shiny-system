revoke all on function public.save_course_draft(
  bigint, varchar, text, varchar, jsonb, uuid, varchar
) from public, anon, authenticated;

grant execute on function public.save_course_draft(
  bigint, varchar, text, varchar, jsonb, uuid, varchar
) to public, anon, authenticated;

grant execute on function public.publish_course(
  uuid, bigint
) to public, anon, authenticated;

grant execute on function public.start_learning_session(
  bigint, uuid, uuid, varchar, varchar
) to public, anon, authenticated;

grant execute on function public.complete_learning_lesson(
  bigint, uuid, varchar
) to public, anon, authenticated;

grant execute on function public.set_course_visibility(
  uuid, bigint, varchar
) to public, anon, authenticated;
