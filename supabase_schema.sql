-- desk-widget: 3-tier RBAC Schema for Supabase (Super Admin / Co-Admin / User)
-- Run this once in your Supabase Dashboard -> SQL Editor.
-- IMPORTANT: Never hardcode your real Super Admin ID or password inside Git-tracked files.

create extension if not exists pgcrypto with schema extensions;

-- 1. User profiles & role permissions
create table if not exists public.profiles (
    id uuid primary key references auth.users(id) on delete cascade,
    email text not null unique,
    role text not null default 'user' check (role in ('super_admin', 'admin', 'user')),
    admin_id_hash text,
    admin_id_fingerprint text unique,
    is_active boolean not null default true,
    failed_admin_attempts int not null default 0,
    admin_locked_until timestamptz,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

alter table public.profiles enable row level security;

-- Normal users can ONLY view their own profile; active admins/super_admin view via SECURITY DEFINER RPC
drop policy if exists "profiles_select_own" on public.profiles;
create policy "profiles_select_own"
    on public.profiles
    for select
    to authenticated
    using (auth.uid() = id);

-- Explicitly deny direct INSERT/UPDATE/DELETE from anon/authenticated REST clients;
-- all role & account mutations go through audited SECURITY DEFINER RPCs + trigger guards.
drop policy if exists "profiles_no_direct_update" on public.profiles;
create policy "profiles_no_direct_update"
    on public.profiles
    for update
    to authenticated
    using (false);

drop policy if exists "profiles_no_direct_delete" on public.profiles;
create policy "profiles_no_direct_delete"
    on public.profiles
    for delete
    to authenticated
    using (false);

-- 2. Remote app settings, announcements & user feature flags
create table if not exists public.remote_settings (
    id int primary key default 1 check (id = 1),
    announcement_title text not null default '',
    announcement_body text not null default '',
    shared_ics_url text not null default '',
    force_theme text not null default '',
    min_version text not null default '',
    feature_flags jsonb not null default '{
        "allow_settings": true,
        "allow_bg_logo": true,
        "allow_style": true,
        "allow_theme": true,
        "allow_esl_export": true,
        "allow_updates": true
    }'::jsonb,
    updated_at timestamptz not null default now(),
    updated_by uuid references public.profiles(id) on delete set null
);

insert into public.remote_settings (id)
values (1)
on conflict (id) do nothing;

alter table public.remote_settings enable row level security;

drop policy if exists "remote_settings_select_authenticated" on public.remote_settings;
create policy "remote_settings_select_authenticated"
    on public.remote_settings
    for select
    to authenticated
    using (true);

-- 3. Auto-create user profile on Auth signup
create or replace function public.handle_new_auth_user()
returns trigger
language plpgsql
security definer
set search_path = public, extensions
as $$
begin
    insert into public.profiles (id, email, role, is_active)
    values (new.id, lower(trim(coalesce(new.email, ''))), 'user', true)
    on conflict (id) do update
        set email = excluded.email,
            updated_at = now();
    return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
    after insert on auth.users
    for each row execute function public.handle_new_auth_user();

-- 4. Immutable Super Admin Protection Trigger
create or replace function public.protect_super_admin()
returns trigger
language plpgsql
security definer
set search_path = public, extensions
as $$
begin
    if tg_op = 'DELETE' then
        if old.role = 'super_admin' then
            raise exception 'super_admin account cannot be deleted';
        end if;
        return old;
    end if;

    if tg_op = 'UPDATE' then
        if current_setting('app.trusted_rpc', true) is distinct from 'true' then
            raise exception 'Direct updates to public.profiles are forbidden';
        end if;

        if old.role = 'super_admin' then
            if current_setting('app.allow_super_bootstrap', true) is distinct from 'true' then
                if new.role <> 'super_admin'
                   or new.is_active is distinct from true
                   or new.admin_id_hash is distinct from old.admin_id_hash
                   or new.admin_id_fingerprint is distinct from old.admin_id_fingerprint
                   or lower(new.email) is distinct from lower(old.email) then
                    raise exception 'super_admin permissions and ID are permanently protected';
                end if;
            end if;
        elsif new.role = 'super_admin' then
            if current_setting('app.allow_super_bootstrap', true) is distinct from 'true' then
                raise exception 'Cannot promote any other account to super_admin';
            end if;
        end if;

        new.updated_at := now();
        return new;
    end if;

    return new;
end;
$$;

drop trigger if exists trg_protect_super_admin on public.profiles;
create trigger trg_protect_super_admin
    before update or delete on public.profiles
    for each row execute function public.protect_super_admin();

-- Helper: generate unbiased 11-digit CSPRNG string not colliding with any existing ID (including super_admin)
create or replace function public._generate_unique_11_digit_admin_id()
returns text
language plpgsql
security definer
set search_path = public, extensions
as $$
declare
    candidate text;
    fp text;
    raw_byte int;
    tries int := 0;
begin
    loop
        tries := tries + 1;
        if tries > 50 then
            raise exception 'Failed to allocate unique 11-digit Admin ID';
        end if;

        candidate := '';
        while length(candidate) < 11 loop
            raw_byte := get_byte(gen_random_bytes(1), 0);
            if raw_byte < 250 then
                candidate := candidate || (raw_byte % 10)::text;
            end if;
        end loop;

        fp := encode(digest(candidate, 'sha256'), 'hex');
        exit when not exists (
            select 1 from public.profiles where admin_id_fingerprint = fp
        );
    end loop;

    return candidate;
end;
$$;

-- 5. One-time Super Admin bootstrap (ONLY runnable from Supabase SQL Editor when no super_admin exists)
create or replace function public.bootstrap_super_admin(target_email text, super_id text)
returns jsonb
language plpgsql
security definer
set search_path = public, auth, extensions
as $$
declare
    clean_email text := lower(trim(coalesce(target_email, '')));
    clean_id text := trim(coalesce(super_id, ''));
    uid uuid;
    fp text;
begin
    if auth.uid() is not null then
        raise exception 'bootstrap_super_admin must be executed from Supabase SQL Editor';
    end if;

    if exists (select 1 from public.profiles where role = 'super_admin') then
        raise exception 'A super_admin already exists';
    end if;

    if clean_id !~ '^[0-9]{11}$' then
        raise exception 'Super Admin ID must be an 11-digit numeric string';
    end if;

    select id into uid from auth.users where lower(email) = clean_email limit 1;
    if uid is null then
        raise exception 'Account % not found. Please sign up in the app first.', clean_email;
    end if;

    fp := encode(digest(clean_id, 'sha256'), 'hex');

    perform set_config('app.trusted_rpc', 'true', true);
    perform set_config('app.allow_super_bootstrap', 'true', true);

    insert into public.profiles (id, email, role, admin_id_hash, admin_id_fingerprint, is_active)
    values (uid, clean_email, 'super_admin', crypt(clean_id, gen_salt('bf')), fp, true)
    on conflict (id) do update
        set email = clean_email,
            role = 'super_admin',
            admin_id_hash = crypt(clean_id, gen_salt('bf')),
            admin_id_fingerprint = fp,
            is_active = true,
            failed_admin_attempts = 0,
            admin_locked_until = null;

    return jsonb_build_object('ok', true, 'email', clean_email, 'role', 'super_admin');
end;
$$;

revoke all on function public.bootstrap_super_admin(text, text) from public, anon, authenticated;

-- 6. Session state & remote settings lookup for logged-in user
create or replace function public.get_my_session_state()
returns jsonb
language plpgsql
security definer
set search_path = public, auth, extensions
as $$
declare
    uid uuid := auth.uid();
    u_email text;
    prof public.profiles%rowtype;
    r_cfg public.remote_settings%rowtype;
begin
    if uid is null then
        return jsonb_build_object('ok', false, 'error', 'not_authenticated');
    end if;

    select * into prof from public.profiles where id = uid;
    if prof.id is null then
        select lower(email) into u_email from auth.users where id = uid;
        insert into public.profiles (id, email, role, is_active)
        values (uid, coalesce(u_email, ''), 'user', true)
        on conflict (id) do nothing;
        select * into prof from public.profiles where id = uid;
    end if;

    select * into r_cfg from public.remote_settings where id = 1;

    return jsonb_build_object(
        'ok', true,
        'id', prof.id,
        'email', prof.email,
        'db_role', prof.role,
        'is_active', prof.is_active,
        'has_admin_id', (prof.admin_id_hash is not null),
        'remote_settings', jsonb_build_object(
            'announcement_title', coalesce(r_cfg.announcement_title, ''),
            'announcement_body', coalesce(r_cfg.announcement_body, ''),
            'shared_ics_url', coalesce(r_cfg.shared_ics_url, ''),
            'force_theme', coalesce(r_cfg.force_theme, ''),
            'min_version', coalesce(r_cfg.min_version, ''),
            'feature_flags', coalesce(r_cfg.feature_flags, '{}'::jsonb)
        )
    );
end;
$$;

grant execute on function public.get_my_session_state() to authenticated;

-- 7. Verify Admin / Super Admin ID with 5-attempt / 15-minute brute-force lockout
create or replace function public.verify_admin_access(input_admin_id text)
returns jsonb
language plpgsql
security definer
set search_path = public, extensions
as $$
declare
    uid uuid := auth.uid();
    prof public.profiles%rowtype;
    clean_id text := trim(coalesce(input_admin_id, ''));
    next_fails int;
    lock_ts timestamptz;
begin
    if uid is null then
        return jsonb_build_object('ok', false, 'error', 'not_authenticated');
    end if;

    select * into prof from public.profiles where id = uid;
    if prof.id is null or not prof.is_active then
        return jsonb_build_object('ok', false, 'error', 'account_disabled');
    end if;

    if prof.role not in ('admin', 'super_admin') or prof.admin_id_hash is null then
        return jsonb_build_object('ok', false, 'error', 'not_an_admin');
    end if;

    if prof.admin_locked_until is not null and prof.admin_locked_until > now() then
        return jsonb_build_object(
            'ok', false,
            'error', 'locked',
            'locked_until', prof.admin_locked_until
        );
    end if;

    perform set_config('app.trusted_rpc', 'true', true);

    if clean_id <> '' and crypt(clean_id, prof.admin_id_hash) = prof.admin_id_hash then
        update public.profiles
        set failed_admin_attempts = 0,
            admin_locked_until = null
        where id = uid;

        return jsonb_build_object(
            'ok', true,
            'role', prof.role,
            'email', prof.email
        );
    end if;

    next_fails := coalesce(prof.failed_admin_attempts, 0) + 1;
    if next_fails >= 5 then
        lock_ts := now() + interval '15 minutes';
        update public.profiles
        set failed_admin_attempts = 0,
            admin_locked_until = lock_ts
        where id = uid;
        return jsonb_build_object('ok', false, 'error', 'locked', 'locked_until', lock_ts);
    end if;

    update public.profiles
    set failed_admin_attempts = next_fails
    where id = uid;

    return jsonb_build_object(
        'ok', false,
        'error', 'invalid_admin_id',
        'attempts_left', 5 - next_fails
    );
end;
$$;

grant execute on function public.verify_admin_access(text) to authenticated;

-- 8. Super Admin ONLY: generate / regenerate unique 11-digit Co-Admin ID
create or replace function public.super_admin_grant_coadmin(target_email text)
returns jsonb
language plpgsql
security definer
set search_path = public, extensions
as $$
declare
    caller public.profiles%rowtype;
    target public.profiles%rowtype;
    clean_email text := lower(trim(coalesce(target_email, '')));
    new_id text;
    new_fp text;
begin
    select * into caller from public.profiles where id = auth.uid();
    if caller.id is null or caller.role <> 'super_admin' or not caller.is_active then
        raise exception 'Only super_admin can create or regenerate Co-Admin IDs';
    end if;

    select * into target from public.profiles where lower(email) = clean_email limit 1;
    if target.id is null then
        raise exception 'Account % does not exist. Ask them to sign up first.', clean_email;
    end if;
    if target.role = 'super_admin' then
        raise exception 'Cannot modify super_admin ID via Co-Admin grant';
    end if;

    new_id := public._generate_unique_11_digit_admin_id();
    new_fp := encode(digest(new_id, 'sha256'), 'hex');

    perform set_config('app.trusted_rpc', 'true', true);

    update public.profiles
    set role = 'admin',
        admin_id_hash = crypt(new_id, gen_salt('bf')),
        admin_id_fingerprint = new_fp,
        is_active = true,
        failed_admin_attempts = 0,
        admin_locked_until = null
    where id = target.id;

    return jsonb_build_object(
        'ok', true,
        'id', target.id,
        'email', target.email,
        'role', 'admin',
        'admin_id', new_id
    );
end;
$$;

grant execute on function public.super_admin_grant_coadmin(text) to authenticated;

-- 9. Super Admin ONLY: revoke Co-Admin back to user
create or replace function public.super_admin_revoke_coadmin(target_user_id uuid)
returns jsonb
language plpgsql
security definer
set search_path = public, extensions
as $$
declare
    caller public.profiles%rowtype;
    target public.profiles%rowtype;
begin
    select * into caller from public.profiles where id = auth.uid();
    if caller.id is null or caller.role <> 'super_admin' or not caller.is_active then
        raise exception 'Only super_admin can revoke Co-Admin rights';
    end if;

    select * into target from public.profiles where id = target_user_id;
    if target.id is null then
        raise exception 'Target account not found';
    end if;
    if target.role = 'super_admin' then
        raise exception 'Cannot revoke super_admin';
    end if;

    perform set_config('app.trusted_rpc', 'true', true);
    update public.profiles
    set role = 'user',
        admin_id_hash = null,
        admin_id_fingerprint = null,
        failed_admin_attempts = 0,
        admin_locked_until = null
    where id = target_user_id;

    return jsonb_build_object('ok', true, 'id', target.id, 'role', 'user');
end;
$$;

grant execute on function public.super_admin_revoke_coadmin(uuid) to authenticated;

-- 10. List users for Admin Panel (never exposes hashes/fingerprints)
create or replace function public.admin_list_profiles()
returns table (
    id uuid,
    email text,
    role text,
    is_active boolean,
    has_admin_id boolean,
    created_at timestamptz
)
language plpgsql
security definer
set search_path = public, extensions
as $$
declare
    caller public.profiles%rowtype;
begin
    select * into caller from public.profiles where profiles.id = auth.uid();
    if caller.id is null or caller.role not in ('admin', 'super_admin') or not caller.is_active then
        raise exception 'Admin access required';
    end if;

    return query
    select p.id, p.email, p.role, p.is_active, (p.admin_id_hash is not null) as has_admin_id, p.created_at
    from public.profiles p
    order by
        case p.role when 'super_admin' then 0 when 'admin' then 1 else 2 end,
        p.created_at desc;
end;
$$;

grant execute on function public.admin_list_profiles() to authenticated;

-- 11. Lock / unlock account (Co-Admin -> user only; Super Admin -> user & admin; nobody -> super_admin)
create or replace function public.admin_set_user_active(target_user_id uuid, new_active boolean)
returns jsonb
language plpgsql
security definer
set search_path = public, extensions
as $$
declare
    caller public.profiles%rowtype;
    target public.profiles%rowtype;
begin
    select * into caller from public.profiles where id = auth.uid();
    if caller.id is null or caller.role not in ('admin', 'super_admin') or not caller.is_active then
        raise exception 'Admin access required';
    end if;

    select * into target from public.profiles where id = target_user_id;
    if target.id is null then
        raise exception 'Account not found';
    end if;
    if target.role = 'super_admin' then
        raise exception 'Cannot modify super_admin';
    end if;
    if caller.role = 'admin' and target.role <> 'user' then
        raise exception 'Co-Admin can only lock/unlock regular user accounts';
    end if;

    perform set_config('app.trusted_rpc', 'true', true);
    update public.profiles set is_active = new_active where id = target_user_id;

    return jsonb_build_object('ok', true, 'id', target_user_id, 'is_active', new_active);
end;
$$;

grant execute on function public.admin_set_user_active(uuid, boolean) to authenticated;

-- 12. Super Admin ONLY: delete user / Co-Admin account completely
create or replace function public.super_admin_delete_user(target_user_id uuid)
returns jsonb
language plpgsql
security definer
set search_path = public, auth, extensions
as $$
declare
    caller public.profiles%rowtype;
    target public.profiles%rowtype;
begin
    select * into caller from public.profiles where id = auth.uid();
    if caller.id is null or caller.role <> 'super_admin' or not caller.is_active then
        raise exception 'Only super_admin can delete accounts';
    end if;

    select * into target from public.profiles where id = target_user_id;
    if target.id is null then
        raise exception 'Account not found';
    end if;
    if target.role = 'super_admin' then
        raise exception 'Cannot delete super_admin';
    end if;

    delete from auth.users where id = target_user_id;
    return jsonb_build_object('ok', true, 'deleted_id', target_user_id);
end;
$$;

grant execute on function public.super_admin_delete_user(uuid) to authenticated;

-- 13. Update remote settings / announcements / feature flags (Admin & Super Admin)
create or replace function public.admin_update_remote_settings(
    p_announcement_title text,
    p_announcement_body text,
    p_shared_ics_url text,
    p_force_theme text,
    p_min_version text,
    p_feature_flags jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = public, extensions
as $$
declare
    caller public.profiles%rowtype;
begin
    select * into caller from public.profiles where id = auth.uid();
    if caller.id is null or caller.role not in ('admin', 'super_admin') or not caller.is_active then
        raise exception 'Admin access required';
    end if;

    update public.remote_settings
    set announcement_title = coalesce(p_announcement_title, ''),
        announcement_body = coalesce(p_announcement_body, ''),
        shared_ics_url = coalesce(p_shared_ics_url, ''),
        force_theme = coalesce(p_force_theme, ''),
        min_version = coalesce(p_min_version, ''),
        feature_flags = coalesce(p_feature_flags, feature_flags),
        updated_at = now(),
        updated_by = caller.id
    where id = 1;

    return jsonb_build_object('ok', true);
end;
$$;

grant execute on function public.admin_update_remote_settings(text, text, text, text, text, jsonb) to authenticated;
