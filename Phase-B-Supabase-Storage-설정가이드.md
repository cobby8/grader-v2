# Phase B — Supabase Storage 설정 가이드 (등록 패턴 파일 영속화)

> **이 문서가 필요한 이유(쉬운 비유)**
> 우리 서버(Render)의 저장 공간은 "임시 사물함" 같아요. 재배포(업데이트)를 하면
> 사물함이 통째로 새것으로 바뀌면서, 그동안 **화면에서 등록한 패턴 폴더가 사라집니다.**
> (코드에 처음부터 들어있던 2개만 남습니다.)
> 그래서 등록할 때마다 패턴을 **Supabase Storage(영구 창고)** 에 zip으로 자동 백업해 두고,
> 서버가 켜질 때 **없어진 것만 창고에서 다시 꺼내오도록** 만듭니다.
>
> 이 문서는 그 "영구 창고(버킷)" 를 Supabase 대시보드에서 만드는 방법입니다.
> **코딩 지식 없이 클릭과 복붙만으로** 끝나도록 단계별로 적었습니다.

---

## ⚠️ 시작 전 꼭 알아둘 것

- 버킷(창고) 이름은 반드시 **`pattern-presets`** 로 만들어야 합니다.
- 이 이름은 **2단계 코드(`webapp/storage_backup.py`)의 상수와 글자 하나까지 정확히 일치**해야
  백업/복원이 동작합니다. 오타(예: `pattern_presets`, `patternpresets`)가 있으면 조용히 실패합니다.
- 작업은 **Supabase 대시보드 로그인 → 우리 프로젝트 선택** 상태에서 진행합니다.

---

## 1단계 — 버킷(창고) 만들기

1. Supabase 대시보드 왼쪽 메뉴에서 **Storage** 를 클릭합니다.
2. **New bucket**(새 버킷) 버튼을 클릭합니다.
3. 입력 창이 뜨면:
   - **Name of bucket**: `pattern-presets` 를 정확히 입력합니다.
   - **Public bucket**: **끕니다(OFF, 비공개)**.
     → 비공개로 두어도 아래 RLS 정책으로 "읽기"는 열어줄 것이라 복원은 잘 됩니다.
       비공개로 두는 이유는 아무나 URL을 추측해서 파일을 가져가지 못하게 하기 위함입니다.
4. **Save**(저장) 를 눌러 버킷을 만듭니다.

여기까지 하면 `pattern-presets` 라는 빈 창고가 생깁니다.

---

## 2단계 — 접근 규칙(RLS) 3개 넣기

창고를 만들었어도 "누가 읽고 쓸 수 있는지" 규칙(RLS)을 정해줘야 합니다.
아래 SQL을 **그대로 복사해서 한 번에 실행**하면 3개의 규칙이 한꺼번에 들어갑니다.

**규칙 요약(사람 말로):**
- **읽기(SELECT)**: 누구나(로그인 안 한 사람 포함) 읽을 수 있음.
  → 서버가 켜질 때(startup) 복원하는 순간에는 로그인 토큰이 없어서, 읽기는 열어둬야 복원이 됩니다.
    (창고 자체가 비공개라 URL 추측은 막혀 있으니 안전합니다.)
- **쓰기(INSERT/UPDATE/DELETE)**: **관리자(admin) 만** 가능.
  → 즐겨찾기용 `pattern_meta` 표와 똑같은 방식(관리자 도장이 찍힌 로그인만 허용)입니다.

### 실행 방법
1. 왼쪽 메뉴에서 **SQL Editor** 를 클릭합니다.
2. **New query**(새 쿼리) 를 누릅니다.
3. 아래 내용을 **통째로 복사 → 붙여넣기 → Run(실행)** 합니다.

```sql
-- =====================================================================
-- Phase B: pattern-presets 버킷 접근 규칙(RLS) 3개
-- 대상 테이블: storage.objects (Supabase Storage 내부 파일 목록 테이블)
-- =====================================================================

-- (안전) 같은 이름의 정책이 이미 있으면 지우고 다시 만든다(재실행해도 안전).
drop policy if exists "pattern_presets_read"   on storage.objects;
drop policy if exists "pattern_presets_insert" on storage.objects;
drop policy if exists "pattern_presets_update" on storage.objects;
drop policy if exists "pattern_presets_delete" on storage.objects;

-- 1) 읽기(SELECT): 누구나(anon+authenticated) pattern-presets 창고를 읽을 수 있다.
--    → 서버 startup 복원이 로그인 토큰 없이 목록/다운로드해야 하므로 읽기는 개방.
create policy "pattern_presets_read"
on storage.objects
for select
to anon, authenticated
using ( bucket_id = 'pattern-presets' );

-- 2) 넣기(INSERT): 관리자(app_metadata.role = 'admin') 로그인만 업로드 가능.
create policy "pattern_presets_insert"
on storage.objects
for insert
to authenticated
with check (
  (auth.jwt() -> 'app_metadata' ->> 'role') = 'admin'
  and bucket_id = 'pattern-presets'
);

-- 3) 수정(UPDATE): 관리자만. (같은 이름으로 다시 올릴 때 upsert에 필요)
create policy "pattern_presets_update"
on storage.objects
for update
to authenticated
using (
  (auth.jwt() -> 'app_metadata' ->> 'role') = 'admin'
  and bucket_id = 'pattern-presets'
)
with check (
  (auth.jwt() -> 'app_metadata' ->> 'role') = 'admin'
  and bucket_id = 'pattern-presets'
);

-- 4) 삭제(DELETE): 관리자만.
create policy "pattern_presets_delete"
on storage.objects
for delete
to authenticated
using (
  (auth.jwt() -> 'app_metadata' ->> 'role') = 'admin'
  and bucket_id = 'pattern-presets'
);
```

> 실행 후 초록색 "Success" 메시지가 나오면 규칙 4개(읽기1 + 쓰기3)가 정상 적용된 것입니다.
> (`update`와 `insert`를 나눠 넣는 이유: 같은 패턴을 다시 등록해 덮어쓸 때(upsert) 두 권한이
>  모두 필요하기 때문입니다.)

---

## 3단계 — 제대로 됐는지 확인하기(검증)

아래 3가지가 모두 맞으면 설정 완료입니다.

| 확인 항목 | 방법 | 기대 결과 |
|-----------|------|-----------|
| **관리자 업로드 성공** | 관리자(admin) 계정으로 로그인한 상태에서 패턴을 하나 등록 | Storage → `pattern-presets` 창고에 `{패턴이름}.zip` 파일이 생김 |
| **비관리자 업로드 실패** | 일반 직원 계정(admin 아님)으로 시도 | 업로드가 막힘(권한 오류) — 서버는 그냥 백업만 건너뛰고 등록 자체는 정상 |
| **익명 읽기 성공** | 서버를 재배포/재시작 | 시작 로그에 "복원 N개" 가 찍히고, 사라졌던 패턴이 목록에 다시 나타남 |

빠르게 대시보드에서만 확인하려면:
- **Storage → pattern-presets** 를 열어, 등록 후 zip 파일이 쌓이는지 눈으로 보면 됩니다.

---

## 문제가 생기면(자주 겪는 것)

- **패턴을 등록해도 창고에 zip이 안 생겨요**
  → (1) 버킷 이름이 정확히 `pattern-presets` 인지 (2) 등록한 계정이 **관리자(admin)** 인지
     (3) 배포 환경변수 `SUPABASE_URL`·`SUPABASE_PUBLISHABLE_KEY` 가 있는지 확인.
     셋 중 하나라도 없으면 백업은 조용히 건너뜁니다(등록 자체는 정상 동작 — 이건 "고장"이 아니라 안전장치입니다).

- **재배포 후에도 패턴이 안 돌아와요**
  → 읽기(SELECT) 정책이 빠졌을 수 있습니다. 위 SQL을 다시 한 번 실행하세요(재실행해도 안전합니다).

---

**요약**: 버킷 `pattern-presets`(비공개) 하나 만들고, 위 SQL 한 번 실행하면 끝.
버킷 이름 오타만 조심하세요(코드 상수와 일치해야 함).
