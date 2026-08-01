-- Run this in Supabase SQL Editor
create table if not exists public.marketing_country_plans (
  country text primary key,
  payload jsonb not null default '{}'::jsonb,
  updated_at timestamptz not null default now()
);

alter table public.marketing_country_plans enable row level security;

-- Simple private-app policy using the anon key.
-- Keep the Streamlit app private or protect it with APP_PASSWORD.
create policy "allow app read"
on public.marketing_country_plans
for select
to anon
using (true);

create policy "allow app insert"
on public.marketing_country_plans
for insert
to anon
with check (true);

create policy "allow app update"
on public.marketing_country_plans
for update
to anon
using (true)
with check (true);
