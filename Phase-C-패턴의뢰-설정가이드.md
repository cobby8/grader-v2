# Phase C — 패턴 의뢰(실물 수집) Supabase 설정 가이드

현장 직원이 폰으로 **실물 옷 사진·치수·구조**를 올리는 «패턴 의뢰» 기능의 저장소를 만든다.
그레이더용 Supabase 프로젝트에서 **한 번만** 실행하면 된다(다시 실행해도 안전).

만드는 것 (사람 말로):

| 무엇 | 이름 | 하는 일 |
|---|---|---|
| 표 | `pattern_intakes` | 의뢰 1건 = 1줄. 제품·사이즈·옷 형태·부품·상태·치수/구조 답(JSON) |
| 표 | `intake_examples` | 사진·치수 가이드에 붙는 «예시 사진» 목록 |
| 사진 창고 | `pattern-intake` (비공개) | 의뢰 사진 `intakes/{의뢰id}/…` · 예시 사진 `examples/…` |

누가 무엇을 할 수 있나:

| | 로그인 직원 | 작성자 본인 | 관리자(admin) |
|---|---|---|---|
| 의뢰 보기 | ✅ 전부 | ✅ | ✅ |
| 의뢰 만들기 | ✅ | — | ✅ |
| 의뢰 고치기 | ❌ | ✅ (검토 완료 전까지) | ✅ |
| 검토 완료로 바꾸기 | ❌ | ❌ | ✅ |
| 의뢰 지우기 | ❌ | ✅ 작성 중인 것만 | ✅ |
| 사진 올리기·지우기 | ❌ | ✅ 자기 의뢰 폴더만 | ✅ |
| 예시 사진 관리 | ❌ | ❌ | ✅ |

로그인 안 한 사람(anon)은 아무것도 못 한다.
관리자 판정은 기존과 같다 — `app_metadata.role = 'admin'` (pattern_meta·pattern-presets 와 같은 방식).

---

## 1단계 — SQL 실행

1. Supabase 대시보드 → 그레이더 프로젝트 → 왼쪽 **SQL Editor** → **New query**
2. 아래 SQL 을 **통째로 복사 → 붙여넣기 → Run**
3. 아래쪽에 초록색 **Success** 가 나오면 끝

```sql
-- =====================================================================
-- Phase C: 패턴 의뢰(실물 수집) — 표 2개 + 사진 창고 1개 + 접근 규칙
-- 다시 실행해도 안전하다(있으면 건너뛰거나 지우고 다시 만든다).
-- =====================================================================
-- ※ 함수 3개는 모두 search_path = '' 로 고정한다 (Supabase 보안 점검 권고).
--   이름을 찾을 때 기본 내장과 적어 둔 스키마(public.·auth.·storage.)만 본다 —
--   누가 같은 이름의 가짜 함수를 다른 곳에 만들어도 끼어들 수 없다.

-- 0) 관리자 판정 — 기존 pattern_meta·pattern-presets 와 같은 기준
create or replace function public.intake_is_admin()
returns boolean language sql stable set search_path = '' as $$
  select coalesce((auth.jwt() -> 'app_metadata' ->> 'role') = 'admin', false)
$$;

-- 1) 의뢰 표 ----------------------------------------------------------
create table if not exists public.pattern_intakes (
  id               uuid primary key default gen_random_uuid(),
  code             text unique,                         -- 사람이 부르는 번호 PI-251019-001 (자동)
  product_name     text not null default '',            -- 제품 이름
  size_label       text not null default '',            -- 실물 사이즈 (M 등)
  base_type        text not null default '',            -- 기본 형태 키 (sleeve_top 등 — 목록 파일 기준)
  parts            jsonb not null default '[]'::jsonb,  -- 고른 부품 키 목록 ["neck_v","yoke",...]
  catalog_version  text not null default '',            -- 그때 쓴 목록 파일 버전
  ref_url          text not null default '',            -- 실물 판매 링크
  status           text not null default 'draft'
                   check (status in ('draft', 'submitted', 'reviewed')),   -- 작성 중 / 제출 / 검토 완료
  data             jsonb not null default '{}'::jsonb,
  -- data 모양 (열쇠는 목록 파일 webapp/static/intake/catalog.json 의 key):
  --   sel      {"neck": "v_rib", "sleeve": "set_in", ..., "extra": ["yoke"]}   ← 고른 옷 모양
  --   photos   {"neck_out": [{"path": "intakes/<id>/neck_out_<시각>.jpg", "w": 1600, "h": 1200, "at": "..."}], ...}
  --   skipped  {"label": "라벨이 잘려 있음"}                   ← «못 찍음» 과 이유
  --   measures {"cuff_half": {"values": {"relaxed": 9.5}, "skip": {"stretched": "못 잼"}, "note": ""}, ...}
  --            값이 하나인 칸은 values 의 열쇠가 "v"  ·  skip 은 "못 잼" 또는 "없음"
  --   answers  {"rib_layers": {"choice": "2겹 (반 접은 립)", "note": ""}, "insert_where": {"text": "V 아래"}}
  --   extras   [{"name": "어깨 덧댐", "where": "", "height": 6, "width": null}]   ← 목록에 없는 조각
  note             text not null default '',            -- 현장 메모
  created_by       uuid not null default auth.uid(),
  created_by_email text not null default coalesce(auth.jwt() ->> 'email', ''),
  created_at       timestamptz not null default now(),
  updated_at       timestamptz not null default now(),
  submitted_at     timestamptz,
  reviewed_at      timestamptz,
  reviewed_by      uuid
);
create index if not exists pattern_intakes_status_idx  on public.pattern_intakes (status, created_at desc);
create index if not exists pattern_intakes_creator_idx on public.pattern_intakes (created_by, created_at desc);

-- 1-1) 번호·시각 자동 채우기
create or replace function public.pattern_intakes_stamp()
returns trigger language plpgsql set search_path = '' as $$
declare
  d   text := to_char(now() at time zone 'Asia/Seoul', 'YYMMDD');
  n   int;
begin
  if tg_op = 'INSERT' then
    -- 오늘 몇 번째 의뢰인지 (한국 시각 기준) — 개수가 아니라 «가장 큰 번호 + 1»
    --   (개수로 세면 작성 중 의뢰를 지운 뒤 같은 번호가 다시 나와 저장이 막힌다)
    select coalesce(max(substr(code, 11)::int), 0) + 1 into n
      from public.pattern_intakes where code like 'PI-' || d || '-%';
    new.code := 'PI-' || d || '-' || lpad(n::text, 3, '0');
    new.created_at := now();
  end if;
  new.updated_at := now();
  if new.status = 'submitted' and (tg_op = 'INSERT' or old.status is distinct from 'submitted') then
    new.submitted_at := now();
  end if;
  if new.status = 'reviewed' and (tg_op = 'INSERT' or old.status is distinct from 'reviewed') then
    new.reviewed_at := now();
    new.reviewed_by := auth.uid();
  end if;
  if tg_op = 'UPDATE' then
    new.created_by := old.created_by;          -- 작성자는 바꿀 수 없다
    new.created_by_email := old.created_by_email;
    new.code := old.code;
  end if;
  return new;
end $$;
drop trigger if exists pattern_intakes_stamp on public.pattern_intakes;
create trigger pattern_intakes_stamp before insert or update on public.pattern_intakes
  for each row execute function public.pattern_intakes_stamp();

-- 1-2) 접근 규칙
alter table public.pattern_intakes enable row level security;
revoke all on public.pattern_intakes from anon;
grant select, insert, update, delete on public.pattern_intakes to authenticated;

drop policy if exists "intakes_read"   on public.pattern_intakes;
drop policy if exists "intakes_insert" on public.pattern_intakes;
drop policy if exists "intakes_update" on public.pattern_intakes;
drop policy if exists "intakes_delete" on public.pattern_intakes;

create policy "intakes_read" on public.pattern_intakes
  for select to authenticated using (true);

create policy "intakes_insert" on public.pattern_intakes
  for insert to authenticated
  with check (created_by = auth.uid() and status = 'draft');

-- 고치기: 관리자, 또는 작성자 본인(검토 완료 전까지). 작성자는 «검토 완료» 로 못 바꾼다.
create policy "intakes_update" on public.pattern_intakes
  for update to authenticated
  using (public.intake_is_admin() or (created_by = auth.uid() and status <> 'reviewed'))
  with check (public.intake_is_admin() or (created_by = auth.uid() and status in ('draft', 'submitted')));

-- 지우기: 관리자, 또는 작성자 본인의 «작성 중» 의뢰
create policy "intakes_delete" on public.pattern_intakes
  for delete to authenticated
  using (public.intake_is_admin() or (created_by = auth.uid() and status = 'draft'));

-- 2) 예시 사진 표 -----------------------------------------------------
create table if not exists public.intake_examples (
  id            uuid primary key default gen_random_uuid(),
  item_key      text not null,                          -- "photo:S06" / "measure:M10"
  storage_path  text not null,                          -- examples/... (사진 창고 안 경로)
  line          jsonb,                                  -- 치수 예시면 사진 위 줄자 선 {"x1":0.1,"y1":0.2,"x2":0.5,"y2":0.6} (0~1)
  caption       text not null default '',
  sort          int  not null default 0,
  source_intake uuid references public.pattern_intakes(id) on delete set null,
  created_by    uuid default auth.uid(),
  created_at    timestamptz not null default now()
);
create index if not exists intake_examples_item_idx on public.intake_examples (item_key, sort);

alter table public.intake_examples enable row level security;
revoke all on public.intake_examples from anon;
grant select, insert, update, delete on public.intake_examples to authenticated;

drop policy if exists "examples_read"  on public.intake_examples;
drop policy if exists "examples_write" on public.intake_examples;
create policy "examples_read" on public.intake_examples
  for select to authenticated using (true);
create policy "examples_write" on public.intake_examples
  for all to authenticated
  using (public.intake_is_admin()) with check (public.intake_is_admin());

-- 3) 사진 창고 ---------------------------------------------------------
--    비공개 · 한 장 8MB 까지 · 사진 형식만 (폰에서 1600px 로 줄여 올리므로 보통 0.3~0.6MB)
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('pattern-intake', 'pattern-intake', false, 8388608, array['image/jpeg', 'image/png', 'image/webp'])
on conflict (id) do update
  set public = false, file_size_limit = 8388608, allowed_mime_types = array['image/jpeg', 'image/png', 'image/webp'];

-- 3-1) 사진을 올릴 수 있는지 판정 — intakes/{의뢰id}/... 는 그 의뢰를 고칠 수 있는 사람만,
--      examples/... 는 관리자만
create or replace function public.intake_photo_writable(object_name text)
returns boolean language sql stable set search_path = '' as $$
  select case (storage.foldername(object_name))[1]
    when 'examples' then public.intake_is_admin()
    when 'intakes' then exists (
      select 1 from public.pattern_intakes i
      where i.id::text = (storage.foldername(object_name))[2]
        and (public.intake_is_admin() or (i.created_by = auth.uid() and i.status <> 'reviewed'))
    )
    else false
  end
$$;

drop policy if exists "intake_photos_read"   on storage.objects;
drop policy if exists "intake_photos_insert" on storage.objects;
drop policy if exists "intake_photos_update" on storage.objects;
drop policy if exists "intake_photos_delete" on storage.objects;

create policy "intake_photos_read" on storage.objects
  for select to authenticated
  using (bucket_id = 'pattern-intake');

create policy "intake_photos_insert" on storage.objects
  for insert to authenticated
  with check (bucket_id = 'pattern-intake' and public.intake_photo_writable(name));

create policy "intake_photos_update" on storage.objects
  for update to authenticated
  using (bucket_id = 'pattern-intake' and public.intake_photo_writable(name))
  with check (bucket_id = 'pattern-intake' and public.intake_photo_writable(name));

create policy "intake_photos_delete" on storage.objects
  for delete to authenticated
  using (bucket_id = 'pattern-intake' and public.intake_photo_writable(name));
```

---

## 2단계 — 잘 됐는지 확인

같은 SQL Editor 에서 **New query** → 아래를 실행한다. 결과 표의 `있음` 칸이 전부 `true` 면 끝.

```sql
select '표 pattern_intakes'    as 항목, to_regclass('public.pattern_intakes') is not null as 있음
union all select '표 intake_examples', to_regclass('public.intake_examples') is not null
union all select '사진 창고 pattern-intake (비공개)', exists (select 1 from storage.buckets where id = 'pattern-intake' and public = false)
union all select '의뢰 표 규칙 4개', (select count(*) = 4 from pg_policies where schemaname = 'public' and tablename = 'pattern_intakes')
union all select '예시 표 규칙 2개', (select count(*) = 2 from pg_policies where schemaname = 'public' and tablename = 'intake_examples')
union all select '사진 창고 규칙 4개', (select count(*) = 4 from pg_policies where schemaname = 'storage' and tablename = 'objects' and policyname like 'intake_photos_%')
union all select '번호 자동 붙이기', exists (select 1 from pg_trigger where tgname = 'pattern_intakes_stamp')
union all select '함수 3개 검색 경로 고정', (select count(*) = 3 from pg_proc p join pg_namespace n on n.oid = p.pronamespace
  where n.nspname = 'public' and p.proname in ('intake_is_admin', 'pattern_intakes_stamp', 'intake_photo_writable')
    and p.proconfig @> array['search_path=""']);
```

⚠️ SQL Editor 는 관리자 권한으로 돌아서 «직원 계정이면 막히는지» 는 여기서 시험할 수 없다.
그건 화면이 만들어진 뒤 **직원 계정으로 로그인해서** 확인한다(다른 사람 의뢰 사진 올리기 → 막혀야 정상).

---

## 되돌리기 (필요할 때만)

```sql
drop policy if exists "intake_photos_read"   on storage.objects;
drop policy if exists "intake_photos_insert" on storage.objects;
drop policy if exists "intake_photos_update" on storage.objects;
drop policy if exists "intake_photos_delete" on storage.objects;
drop function if exists public.intake_photo_writable(text);
drop table if exists public.intake_examples;
drop table if exists public.pattern_intakes;
drop function if exists public.pattern_intakes_stamp();
drop function if exists public.intake_is_admin();
-- 사진 창고는 안에 파일이 있으면 지워지지 않는다 — 대시보드 Storage 에서 비운 뒤 지운다.
```
