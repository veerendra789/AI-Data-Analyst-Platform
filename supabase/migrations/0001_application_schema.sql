create extension if not exists pgcrypto;

create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = timezone('utc', now());
  return new;
end;
$$;

create table if not exists public.profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  email text not null default '',
  display_name text not null default 'Analyst',
  role text not null default 'ANALYST' check (role in ('ADMIN', 'ANALYST', 'VIEWER')),
  is_active boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.structuring_jobs (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  source_filename text not null,
  source_storage_path text not null,
  output_storage_path text,
  file_size bigint not null check (file_size >= 0),
  status text not null default 'UPLOADING'
    check (status in ('UPLOADING', 'ANALYZED', 'APPLIED', 'FAILED')),
  metadata_json jsonb not null default '{}'::jsonb,
  plan_json jsonb not null default '[]'::jsonb,
  history_json jsonb not null default '[]'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.datasets (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  name text not null,
  original_filename text not null,
  storage_path text not null,
  file_size bigint not null check (file_size >= 0),
  mime_type text not null default 'text/csv',
  row_count integer not null default 0 check (row_count >= 0),
  column_count integer not null default 0 check (column_count >= 0),
  status text not null default 'UPLOADING'
    check (status in ('UPLOADING', 'PROCESSING', 'COMPLETED', 'FAILED')),
  columns jsonb not null default '[]'::jsonb,
  source_preparation_id uuid references public.structuring_jobs(id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (user_id, source_preparation_id)
);

create table if not exists public.analyses (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  dataset_id uuid not null references public.datasets(id) on delete cascade,
  question text not null,
  generated_sql text,
  execution_time double precision check (execution_time is null or execution_time >= 0),
  status text not null default 'PROCESSING',
  result_json jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.reports (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  dataset_id uuid not null references public.datasets(id) on delete cascade,
  title text not null,
  content text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists profiles_email_idx on public.profiles (lower(email));
create index if not exists datasets_user_created_idx on public.datasets (user_id, created_at desc);
create index if not exists datasets_source_preparation_idx on public.datasets (user_id, source_preparation_id);
create index if not exists analyses_user_dataset_created_idx on public.analyses (user_id, dataset_id, created_at);
create index if not exists reports_user_created_idx on public.reports (user_id, created_at desc);
create index if not exists structuring_jobs_user_created_idx on public.structuring_jobs (user_id, created_at desc);

create or replace function public.create_profile_for_auth_user()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  insert into public.profiles (id, email, display_name)
  values (
    new.id,
    coalesce(new.email, ''),
    coalesce(nullif(new.raw_user_meta_data ->> 'display_name', ''), nullif(split_part(coalesce(new.email, ''), '@', 1), ''), 'Analyst')
  )
  on conflict (id) do update
    set email = excluded.email,
        display_name = excluded.display_name,
        updated_at = now();
  return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
  after insert or update of email, raw_user_meta_data on auth.users
  for each row execute function public.create_profile_for_auth_user();

do $$
begin
  if not exists (select 1 from storage.buckets where id = 'datasets') then
    insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
    values ('datasets', 'datasets', false, 52428800, array['text/csv', 'application/csv', 'application/vnd.ms-excel', 'text/plain']);
  else
    update storage.buckets
      set public = false,
          file_size_limit = 52428800,
          allowed_mime_types = array['text/csv', 'application/csv', 'application/vnd.ms-excel', 'text/plain']
      where id = 'datasets';
  end if;
end $$;

alter table public.profiles enable row level security;
alter table public.datasets enable row level security;
alter table public.analyses enable row level security;
alter table public.reports enable row level security;
alter table public.structuring_jobs enable row level security;

drop policy if exists "profiles_select_own" on public.profiles;
create policy "profiles_select_own" on public.profiles
  for select to authenticated using (id = (select auth.uid()));

drop policy if exists "datasets_select_own" on public.datasets;
create policy "datasets_select_own" on public.datasets
  for select to authenticated using (user_id = (select auth.uid()));
drop policy if exists "datasets_insert_own" on public.datasets;
create policy "datasets_insert_own" on public.datasets
  for insert to authenticated with check (user_id = (select auth.uid()));
drop policy if exists "datasets_update_own" on public.datasets;
create policy "datasets_update_own" on public.datasets
  for update to authenticated using (user_id = (select auth.uid())) with check (user_id = (select auth.uid()));
drop policy if exists "datasets_delete_own" on public.datasets;
create policy "datasets_delete_own" on public.datasets
  for delete to authenticated using (user_id = (select auth.uid()));

drop policy if exists "analyses_select_own" on public.analyses;
create policy "analyses_select_own" on public.analyses
  for select to authenticated using (user_id = (select auth.uid()));
drop policy if exists "analyses_insert_own" on public.analyses;
create policy "analyses_insert_own" on public.analyses
  for insert to authenticated with check (user_id = (select auth.uid()));
drop policy if exists "analyses_update_own" on public.analyses;
create policy "analyses_update_own" on public.analyses
  for update to authenticated using (user_id = (select auth.uid())) with check (user_id = (select auth.uid()));
drop policy if exists "analyses_delete_own" on public.analyses;
create policy "analyses_delete_own" on public.analyses
  for delete to authenticated using (user_id = (select auth.uid()));

drop policy if exists "reports_select_own" on public.reports;
create policy "reports_select_own" on public.reports
  for select to authenticated using (user_id = (select auth.uid()));
drop policy if exists "reports_insert_own" on public.reports;
create policy "reports_insert_own" on public.reports
  for insert to authenticated with check (user_id = (select auth.uid()));
drop policy if exists "reports_update_own" on public.reports;
create policy "reports_update_own" on public.reports
  for update to authenticated using (user_id = (select auth.uid())) with check (user_id = (select auth.uid()));
drop policy if exists "reports_delete_own" on public.reports;
create policy "reports_delete_own" on public.reports
  for delete to authenticated using (user_id = (select auth.uid()));

drop policy if exists "structuring_jobs_select_own" on public.structuring_jobs;
create policy "structuring_jobs_select_own" on public.structuring_jobs
  for select to authenticated using (user_id = (select auth.uid()));
drop policy if exists "structuring_jobs_insert_own" on public.structuring_jobs;
create policy "structuring_jobs_insert_own" on public.structuring_jobs
  for insert to authenticated with check (user_id = (select auth.uid()));
drop policy if exists "structuring_jobs_update_own" on public.structuring_jobs;
create policy "structuring_jobs_update_own" on public.structuring_jobs
  for update to authenticated using (user_id = (select auth.uid())) with check (user_id = (select auth.uid()));
drop policy if exists "structuring_jobs_delete_own" on public.structuring_jobs;
create policy "structuring_jobs_delete_own" on public.structuring_jobs
  for delete to authenticated using (user_id = (select auth.uid()));

drop policy if exists "dataset_objects_select_own" on storage.objects;
create policy "dataset_objects_select_own" on storage.objects
  for select to authenticated using (
    bucket_id = 'datasets' and (storage.foldername(name))[2] = (select auth.uid())::text
  );
drop policy if exists "dataset_objects_insert_own" on storage.objects;
create policy "dataset_objects_insert_own" on storage.objects
  for insert to authenticated with check (
    bucket_id = 'datasets'
    and (storage.foldername(name))[2] = (select auth.uid())::text
    and (metadata ->> 'mimetype') in ('text/csv', 'application/csv', 'application/vnd.ms-excel', 'text/plain')
  );
drop policy if exists "dataset_objects_update_own" on storage.objects;
create policy "dataset_objects_update_own" on storage.objects
  for update to authenticated using (
    bucket_id = 'datasets' and (storage.foldername(name))[2] = (select auth.uid())::text
  ) with check (
    bucket_id = 'datasets' and (storage.foldername(name))[2] = (select auth.uid())::text
  );
drop policy if exists "dataset_objects_delete_own" on storage.objects;
create policy "dataset_objects_delete_own" on storage.objects
  for delete to authenticated using (
    bucket_id = 'datasets' and (storage.foldername(name))[2] = (select auth.uid())::text
  );

drop trigger if exists profiles_set_updated_at on public.profiles;
create trigger profiles_set_updated_at before update on public.profiles
  for each row execute function public.set_updated_at();
drop trigger if exists datasets_set_updated_at on public.datasets;
create trigger datasets_set_updated_at before update on public.datasets
  for each row execute function public.set_updated_at();
drop trigger if exists analyses_set_updated_at on public.analyses;
create trigger analyses_set_updated_at before update on public.analyses
  for each row execute function public.set_updated_at();
drop trigger if exists reports_set_updated_at on public.reports;
create trigger reports_set_updated_at before update on public.reports
  for each row execute function public.set_updated_at();
drop trigger if exists structuring_jobs_set_updated_at on public.structuring_jobs;
create trigger structuring_jobs_set_updated_at before update on public.structuring_jobs
  for each row execute function public.set_updated_at();