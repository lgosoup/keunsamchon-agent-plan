-- G1(대상기업발굴) + G2(세그먼트화) 스키마
-- 근거: specs/G1_대상기업발굴.md, specs/G2_세그먼트화.md,
--       기준/G1_기업판정기준.md, 기준/G2_세그먼트기준.md

-- ── ENUM 타입 ─────────────────────────────────────────────────
create type industry_type as enum ('패션', '뷰티', '푸드', '기타');
create type inclusion_status_type as enum ('포함', '제외', '판정불가');
create type unclassified_reason_type as enum ('U-단독', 'U-경계', 'U-정보없음', 'U-이질');

-- ── companies — G1 산출물. G2는 읽기 전용 ──────────────────────
create table companies (
  id                   text primary key,              -- 기업식별자 (도메인 slug, 예: sample-co-jp)
  name_native          text not null,
  url                  text not null,
  category_raw         text,                           -- O2 취급 품목
  industry             industry_type,                  -- O5
  has_product_photo    boolean,                        -- O3 — 필수조건, 통과분 전원 true라 축으로 못 씀
  has_commerce         boolean,                        -- O4 — 같은 이유로 축 불가
  scale_product_count  integer,                        -- O6-a
  scale_channel_count  integer,                        -- O6-b
  reject_mail_flag     boolean not null default false, -- O8
  unclear_reason       text,                           -- O9 — 값이 "없음"인지 "안 봄"인지 구분
  inclusion_status     inclusion_status_type not null,
  collected_at         timestamptz not null default now(),
  created_at           timestamptz not null default now()
);

comment on table companies is 'G1 산출물. G2는 읽기 전용 — 새로 관찰하지 않는다 (specs/G2 제약)';
comment on column companies.has_product_photo is '필수 조건 — 통과분 전원 true라 세그먼트 축으로 못 씀 (기준/G2_세그먼트기준.md 0절)';
comment on column companies.has_commerce is '필수 조건 — 같은 이유로 축 불가';

create index idx_companies_inclusion_status on companies (inclusion_status);
create index idx_companies_industry on companies (industry);

-- ── segment_sets — 세그먼트 세트 헤더. 축 바뀌면 새 row, append-only ──
create table segment_sets (
  id           text primary key,        -- 예: 'SEG-A-v1'
  axis_code    text not null,           -- 'A'(품목축) / 'B'(규모축) — 컬럼에 하드코딩하지 않음
  axis_source  jsonb not null,          -- 축의 출처 관찰항목 코드, 예: '["O5","O2"]'
  version      integer not null,
  created_at   timestamptz not null default now(),
  created_by   text not null
);

comment on table segment_sets is '세그먼트 정의 버전 헤더. 축이 바뀌면 새 row를 추가하고 이전 버전은 지우거나 고치지 않는다 (specs/G2 제약)';

-- ── segments — 1절 무리 정의 ────────────────────────────────────
create table segments (
  id                         text not null,             -- 세그ID, 예: 'S1'
  segment_set_id             text not null references segment_sets(id),
  name                       text not null,
  rule_definition            text not null,              -- 무리 규정(축의 값 서술) — name만으로는 불합격
  representative_company_id  text references companies(id),
  representative_reason      text,
  primary key (segment_set_id, id)
);

comment on table segments is '1절 무리 정의. rule_definition 없이 name만 있으면 불합격 (specs/G2 출력형식)';

create index idx_segments_representative on segments (representative_company_id);

-- ── segment_assignments — 2절 배정 (분류된 건만) ────────────────
create table segment_assignments (
  id                 bigint generated always as identity primary key,
  company_id         text not null references companies(id),
  segment_set_id     text not null,
  segment_id         text not null,
  assignment_reason  text not null,      -- "관찰값 X → 규정 Y에 맞음" 형식 — 무리 이름 재서술 금지
  judged_by          text not null,
  judged_at          timestamptz not null default now(),
  foreign key (segment_set_id, segment_id) references segments (segment_set_id, id),
  unique (company_id, segment_set_id)     -- 같은 세트 안에서 기업 1곳은 세그 1개에만 배정
);

comment on table segment_assignments is
  '2절 배정. 재조사로 관찰값만 채워져 배정이 바뀌면 새 버전을 만들지 않고 이 테이블만 갱신한다(judged_at 갱신, 버전은 그대로) — specs/G2 제약';

create index idx_assignments_segment on segment_assignments (segment_set_id, segment_id);

-- ── unclassified — 3절 미분류. 배정과 반드시 분리된 테이블 ──────
create table unclassified (
  id              bigint generated always as identity primary key,
  company_id      text not null references companies(id),
  segment_set_id  text not null references segment_sets(id),
  reason_code     unclassified_reason_type not null,
  note            text,
  recorded_at     timestamptz not null default now(),
  unique (company_id, segment_set_id)
);

comment on table unclassified is
  '3절 미분류. U-정보없음은 G10 재수집 후보로 넘어간다(specs/G10 입력) — 출력형식 3절';

create index idx_unclassified_reason on unclassified (reason_code);

-- ── 무결성: 같은 세그먼트 세트 안에서 기업 1곳은 배정 또는 미분류 중 하나만 ──
create or replace function check_no_dual_status()
returns trigger as $$
begin
  if tg_table_name = 'segment_assignments' then
    if exists (
      select 1 from unclassified
      where company_id = new.company_id and segment_set_id = new.segment_set_id
    ) then
      raise exception '기업 %는 세그먼트 세트 %에서 이미 미분류 처리됐습니다', new.company_id, new.segment_set_id;
    end if;
  elsif tg_table_name = 'unclassified' then
    if exists (
      select 1 from segment_assignments
      where company_id = new.company_id and segment_set_id = new.segment_set_id
    ) then
      raise exception '기업 %는 세그먼트 세트 %에서 이미 배정 처리됐습니다', new.company_id, new.segment_set_id;
    end if;
  end if;
  return new;
end;
$$ language plpgsql;

create trigger trg_assignment_no_dual
  before insert or update on segment_assignments
  for each row execute function check_no_dual_status();

create trigger trg_unclassified_no_dual
  before insert or update on unclassified
  for each row execute function check_no_dual_status();

-- ── RLS ──────────────────────────────────────────────────────────
alter table companies enable row level security;
alter table segment_sets enable row level security;
alter table segments enable row level security;
alter table segment_assignments enable row level security;
alter table unclassified enable row level security;

-- 로그인한 담당자는 전부 읽기 가능. 쓰기는 백엔드(service_role 키, RLS 우회)에서만 수행한다.
-- 프론트엔드는 절대 service_role 키를 쓰지 않는다 — anon/authenticated 키만 노출한다.
create policy "authenticated_read_companies" on companies for select to authenticated using (true);
create policy "authenticated_read_segment_sets" on segment_sets for select to authenticated using (true);
create policy "authenticated_read_segments" on segments for select to authenticated using (true);
create policy "authenticated_read_assignments" on segment_assignments for select to authenticated using (true);
create policy "authenticated_read_unclassified" on unclassified for select to authenticated using (true);
