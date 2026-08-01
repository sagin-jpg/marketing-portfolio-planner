-- Run in Supabase SQL Editor

create table if not exists public.ftd_target_plans (
  plan_key text primary key,
  payload jsonb not null,
  updated_at timestamptz not null default now()
);

create table if not exists public.ftd_actual_snapshots (
  snapshot_date date not null,
  country text not null,
  leads numeric not null default 0,
  ftds numeric not null default 0,
  conversion_rate numeric not null default 0,
  marketing_cost numeric not null default 0,
  cpl numeric not null default 0,
  cpa numeric not null default 0,
  roi numeric not null default 0,
  ndp numeric not null default 0,
  primary key (snapshot_date, country)
);

alter table public.ftd_target_plans enable row level security;
alter table public.ftd_actual_snapshots enable row level security;

create policy "target read" on public.ftd_target_plans for select to anon using (true);
create policy "target insert" on public.ftd_target_plans for insert to anon with check (true);
create policy "target update" on public.ftd_target_plans for update to anon using (true) with check (true);
create policy "target delete" on public.ftd_target_plans for delete to anon using (true);

create policy "actual read" on public.ftd_actual_snapshots for select to anon using (true);
create policy "actual insert" on public.ftd_actual_snapshots for insert to anon with check (true);
create policy "actual update" on public.ftd_actual_snapshots for update to anon using (true) with check (true);
create policy "actual delete" on public.ftd_actual_snapshots for delete to anon using (true);
