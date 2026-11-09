create table public.user_token_usage (
  user_id bigint primary key references public."user" (id) on delete cascade,
  window_started_at timestamp with time zone not null default now(),
  used_tokens bigint not null default 0 check (used_tokens >= 0),
  reserved_tokens bigint not null default 0 check (reserved_tokens >= 0)
);

alter table public.user_token_usage enable row level security;
revoke all on public.user_token_usage from public, anon, authenticated;
grant all on public.user_token_usage to service_role;

create or replace function public.reserve_user_token_usage(
  p_user_id bigint,
  p_daily_limit bigint,
  p_reserved_tokens bigint
)
returns table (allowed boolean, used_tokens bigint, reset_at timestamp with time zone)
language plpgsql
security definer
set search_path = ''
as $$
declare
  usage_row public.user_token_usage%rowtype;
begin
  if p_daily_limit <= 0 or p_reserved_tokens <= 0 then
    raise exception 'Token limit and reservation must be positive.';
  end if;

  insert into public.user_token_usage (user_id)
  values (p_user_id)
  on conflict (user_id) do nothing;

  select * into usage_row
  from public.user_token_usage
  where user_id = p_user_id
  for update;

  if usage_row.window_started_at <= now() - interval '24 hours' then
    update public.user_token_usage
    set window_started_at = now(), used_tokens = 0, reserved_tokens = 0
    where user_id = p_user_id
    returning * into usage_row;
  end if;

  if usage_row.used_tokens + usage_row.reserved_tokens + p_reserved_tokens
    > p_daily_limit then
    return query select
      false,
      usage_row.used_tokens + usage_row.reserved_tokens,
      usage_row.window_started_at + interval '24 hours';
    return;
  end if;

  update public.user_token_usage
  set reserved_tokens = reserved_tokens + p_reserved_tokens
  where user_id = p_user_id
  returning * into usage_row;

  return query select
    true,
    usage_row.used_tokens + usage_row.reserved_tokens,
    usage_row.window_started_at + interval '24 hours';
end;
$$;

create or replace function public.settle_user_token_usage(
  p_user_id bigint,
  p_reserved_tokens bigint,
  p_actual_tokens bigint
)
returns void
language plpgsql
security definer
set search_path = ''
as $$
begin
  if p_reserved_tokens < 0 or p_actual_tokens < 0 then
    raise exception 'Token counts cannot be negative.';
  end if;

  update public.user_token_usage
  set reserved_tokens = greatest(reserved_tokens - p_reserved_tokens, 0),
      used_tokens = used_tokens + p_actual_tokens
  where user_id = p_user_id;
end;
$$;

revoke all on function public.reserve_user_token_usage(bigint, bigint, bigint)
  from public, anon, authenticated;
revoke all on function public.settle_user_token_usage(bigint, bigint, bigint)
  from public, anon, authenticated;
grant execute on function public.reserve_user_token_usage(bigint, bigint, bigint)
  to service_role;
grant execute on function public.settle_user_token_usage(bigint, bigint, bigint)
  to service_role;