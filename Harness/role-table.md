# role-table.md — 전체 실행체 역할·입력·출력·도구 권한

G1~G12 12개 기능의 실행체(Skill 12개 + Subagent 5개 + 오케스트레이터 1개) 전체를 한 표로 본다. 개별 상세는 `specs/`·`criteria/`가 정본이다 — 여기서는 옮겨 적지 않고 요약만 한다.

| Skill(Subagent) | 역할 | 입력 | 출력 | 도구 권한 |
|---|---|---|---|---|
| `g1-company-screening` | 일본 기업 1곳의 공개 페이지를 읽고 관찰 항목(O1~O6·O8~O9)을 기록해 타겟 조건 3종 충족 여부를 판정 | 기업명 + 공개 페이지 URL 1개 이상 | `data/candidates/후보목록.md`에 섹션 1개 append | `disallowed-tools: Bash, PowerShell, Agent` — WebFetch·WebSearch·Read·Write는 허용(공개 페이지 열람 + 목록 파일 갱신) |
| `g2-segmentation` | G1 통과분을 같은 문안을 써도 될 무리로 묶고, 무리마다 대표 1곳 지정, 미분류는 사유 코드와 함께 남김 | `data/candidates/후보목록.md`(포함 판정분) | `data/segments/SEG-{축코드}-v{버전}.md` | `disallowed-tools: Bash, PowerShell, WebFetch, WebSearch, Agent` — 외부 접속 없이 이미 있는 관찰값만 읽고 판단 |
| `g3-fit-scoring`(부가) | G1 통과분을 축별로 채점(채점 모드)하고, 전체를 모아 순위표를 냄(정렬 모드) — 필터가 아니라 정렬 | `data/candidates/후보목록.md` 섹션 | `data/scores/{기업식별자}.md` + `data/scores/순위표-{작성일}.md` | `disallowed-tools: Bash, PowerShell, WebFetch, WebSearch, Agent` |
| `g4-contact-acquisition` | 세그먼트 대표 우선으로 기업을 열어 연락 창구를 확보하고, 옵트인 위법 여부(수신 거부 목록 등재)를 판정 | 세그먼트 정의 + G1 산출물 | `data/contacts/{기업식별자}.md` — [확보]/[발송 금지]/[미확보]/[메일 없음] | `disallowed-tools: Bash, PowerShell, Agent` — WebFetch·WebSearch 허용(연락처 탐색), 실제 발송 도구는 없음 |
| `g5-proposal-email-dispatch` (오케스트레이터 겸) | 세그먼트 대표 문안 제작 → 그룹 확장 → 번역 검증 → **사람 승인** → 발송까지 3개 서브에이전트를 순서대로 호출 | 단위 M = 세그먼트 1개, 단위 E = 세그먼트+대표문안+소속기업 전체 | `data/발송기록/{기업식별자}-{발송일시}.md` | `disallowed-tools: Bash, PowerShell, WebFetch, WebSearch` — Agent(서브에이전트 호출)·발송 도구는 허용, 단 승인 기록 없는 건에는 발송 도구를 호출하지 않음 |
| `g5-copy-drafting` (Subagent, 문안 단위) | 대표 문안 제작(모드 M) / 그룹 확장 생성(모드 E) / 불일치 지점만 받아 재번역(모드 R) | 세그먼트+대표기업 관찰 근거(M), 대표문안+소속기업 근거(E), 불일치 지점(R) | 한국어 발신 의도 전문 + 일본어 발신 문안(제목·본문), 법정 표시 4종 포함 | `tools: Read` — 파일을 쓰지 않고 발송하지 않음 |
| `g5-translation-verification` (Subagent, 검증 단위 V) | 한국어 발신 의도 원문과 일본어 발신 문안, 이 둘만 받아 번역 검증 3층(의미 보존·고유명사와 수치·어조와 방향) 대조 | 한국어 원문 + 일본어 문안 (판단층 없음) | 층별 일치/불일치 + 불일치 지점 | `tools: Read` — 번역을 고치지 않음. 자기 번역을 자기가 검증하지 않도록 문안 제작과 분리된 별도 컨텍스트 |
| `g5-approval-check` (Subagent, 승인 판독 단위) | 발송대기 화면 파일의 승인란만 읽고 건마다 승인/거부/미승인 판정을 반환 | 발송대기 화면 파일 1개 | 건별 승인/거부/미승인 판정 | `tools: Read` — 승인란을 대신 채우거나 발송을 실행하지 않음(판독과 발송 권한을 분리) |
| `g6-delivery-status-judging` | 발송 기록 + 메일 시스템 응답(바운스 코드·회신 도착 여부)을 받아 [대기중]/[회신]/[무응답]/[주소 오류] 판정, G7 정정 신호로 되돌림 | 발송 기록 1건 + 그 건의 메일 시스템 응답 | `data/상태/{기업식별자}-{발송일시}.md` | `disallowed-tools: Bash, PowerShell, WebFetch, WebSearch, Agent` — 회신 내용(`data/replies/`)은 절대 열지 않음(사실만 보고 해석하지 않는 경계) |
| `g7-reply-processing` (오케스트레이터 겸) | 회신 1통을 해석 단위 T·검증 단위 V 두 서브에이전트로 나눠 돌려 원문·해석·8분류·번역검증이 붙은 레코드를 만들고, 수신 거부면 발송금지 목록에 등재 | 회신 원문 1통(헤더·첨부목록·참조발신정보 포함) | `data/replies/{수신일시}-{식별자}.md` + (수신거부 시) `data/발송금지.md` 1행 | `disallowed-tools: Bash, PowerShell, WebFetch, WebSearch` — Agent(서브에이전트 호출) 허용 |
| `g7-reply-interpretation` (Subagent, 해석 단위 T) | 원문 보존 + 한국어 해석 + 회신 성격 8분류 + 수신거부·자동응답 판정 | 회신원문·헤더·첨부목록·참조발신정보(1회차) 또는 원문+불일치지점(2회차) | 레코드 파일(원문층·해석층·판단층) + 수신거부 시 발송금지 1행 | `tools: Read, Write, Edit` — 발신·웹 도구 없음 |
| `g7-translation-verification` (Subagent, 검증 단위 V) | 원문(일본어)과 한국어 해석 둘만 받아 번역 검증 3층 대조(분류 결과·판단 과정은 받지 않음) | 원문 + 해석 전문 (파일 경로 없음, 판단층 없음) | 층별 일치/불일치 + 불일치 지점 + 권고 | `tools: Read` — 파일 쓰기·번역 교정 권한 없음 |
| `g8-cause-analysis`(부가) | G6이 [무응답]/[주소 오류]로 판정한 건의 원인 가설 4종(무시/도달실패/조사오류/판정불가)과 재시도 가치(高/低/해당없음)를 판정 | G6 상태 1건 + 발송 이력 + G1 관찰 근거 + G4 연락처 등급 | `data/원인분석/{기업식별자}-{발송일시}.md` | `disallowed-tools: Bash, PowerShell, WebFetch, WebSearch, Agent` |
| `g9-handoff-brief`(부가) | 연락처 미확보(경로1) 또는 재시도 가치 高(경로2) 건을 사람이 판단할 수 있는 브리프로 만들고, 사람이 찾은 연락처를 G4로 되돌림 | 경로1: G4 [미확보] 1건 / 경로2: G8 재시도가치 高 1건 | `data/위임브리프/{기업식별자}.md`(+ 합류 모드는 `data/연락처후보/{기업식별자}.md`) | `disallowed-tools: Bash, PowerShell, WebFetch, WebSearch, Agent` — 등급 판정·거부 확인은 하지 않음(G4 소관) |
| `g10-recollection-judging`(부가) | G3 보류·G4 미확보·G8 조사오류·외부 신호를 받아 재수집 대상 여부와 재조사 범위(전체/특정항목/연락처만)를 판정 | 재수집 후보 1건 + 유입 사유 | 대상일 때만 `data/재수집대상/{기업식별자}-{판정일}.md` | `disallowed-tools: Bash, PowerShell, WebFetch, WebSearch, Agent` — 재조사를 직접 하지 않음(G1·G4로 넘길 뿐) |
| `g11-response-aggregation`(부가) | 발송·상태·회신·원인 데이터를 세그먼트×조건 조합별로 집계하고, 근거가 붙은 기준 조정 **제안**(자동 적용 아님)을 냄 | G5·G6·G7·G8·G2·G3 산출물 일체 | `data/집계/{집계일}.md` | `disallowed-tools: Bash, PowerShell, WebFetch, WebSearch, Agent` — G2·G3 기준 카드를 스스로 고치지 않음 |
| `g12-qna`(부가) | G1~G11 산출물을 읽기 전용으로 조회해 자연어 질문에 근거를 인용해 답변. 실행·수정 권한 없음 | 사용자의 자연어 질문 | `data/질의응답로그/{일시}.md` + 응답 | `disallowed-tools: Bash, PowerShell, WebFetch, WebSearch, Agent` — 파이프라인 재실행 요청은 실행하지 않고 되돌림 |
| `run-orchestrator` | 완성된 하네스를 실제로 돌리는 실행 배선 — 조사 체인은 즉시 연쇄, 발송은 승인 정지점에서 종료, 반응은 바운스·회신 도착으로 재개하는 세 리듬을 다르게 취급 | 사용자의 실행 지시("조사 돌려줘"·"승인했어 이어서 보내줘" 등) | `data/실행상태.md` + 각 스텝 실행체 호출 | `tools: Read, Grep, Glob, Write, Edit, Skill, Agent` — 스텝의 판정을 대신하지 않고, 실행체가 없으면 멈춘 지점을 적고 종료 |

## 작성 방법 대조 (템플릿 4단계 확인)

1. **작업 분해 기준**: G1~G12는 서로 다른 판정 대상(기업 존재 여부 / 무리 묶기 / 적합도 / 연락처 / 문안·발송 / 상태 / 회신 성격 / 원인 / 위임 / 재수집 / 집계 / 질의)을 갖고, 뒤 기능이 앞 기능의 산출물을 입력으로 받는 파이프라인이다. G5·G7만 내부에 자기검증이 필요한 지점(번역을 만든 주체가 그 번역을 검증하면 안 됨)이 있어 문안/해석 단위와 검증 단위를 별도 서브에이전트로 분리했다. 나머지 10개는 실행 단위가 1개라 서브에이전트가 없다.
2. **객관적 계산 vs 주관적 판단**: G3(채점)·G11(집계)만 순수 계산 성격이 섞여 있고, 나머지는 전부 관찰·판단이 필요한 작업이다. 계산 성격이 있는 자리도 판정 문턱(임계값)은 `criteria/`에서 값으로 분리해, 스킬 본문이 판정 문장을 직접 발명하지 않는다.
3. **입력·출력 정합성**: 각 스킬의 출력 파일명은 다음 스킬이 그대로 조인 키로 쓴다 — `{기업식별자}-{발송일시}`가 G5→G6→G8→G11의 공통 키다(형식은 `specs/g5-proposal-email-dispatch.md` 「출력 형식」이 정본).
4. **도구 권한 최소화**: 판정/생성 단위는 외부 접속·발송 도구가 없고, 발송 권한이 있는 단일 기능(G5)조차 승인 판독(`g5-approval-check`)과 발송 실행을 다른 컨텍스트로 분리해 자기승인을 막는다. 검증 서브에이전트(`g5-translation-verification`·`g7-translation-verification`)는 전부 `Read`만 가진다.

## 점검 체크리스트

- [x] 표에 12개 Skill과 5개 Subagent, 오케스트레이터 1개가 모두 역할·입력·출력·도구 권한과 함께 있다
- [x] 한 Skill의 출력 형식이 다음 Skill의 입력 형식과 조인 키 단위로 일치한다(`{기업식별자}-{발송일시}` 등)
- [x] 자기검증이 필요한 지점(G5·G7)은 생성 단위와 검증 단위가 다른 도구 권한·다른 컨텍스트로 분리돼 있다
- [x] 도구 권한이 그 역할에 실제로 필요한 만큼만 부여됐다(검증 단위는 전부 `Read`만, 승인 판독은 쓰기 권한 없음)

## 알려진 한계 (숨기지 않고 남긴다)

- `g5-proposal-email-dispatch`·`g7-reply-processing`은 별도 서브에이전트가 아니라 **스킬 + 오케스트레이션**이라, 서브에이전트를 호출하는 절차 자체는 세션 자신의 권한으로 수행한다 — 호출되는 서브에이전트만큼 도구 권한이 파일 층에서 물리적으로 좁혀져 있지 않다.
- `disallowed-tools`에는 `Skill`이 빠져 있다 — 이론상 다른 스킬을 슬래시로 불러 자신의 금지 목록을 우회할 여지가 구조적으로 남아 있다. 지금은 지침(스킬 본문의 "하지 않는 것" 절)으로만 막혀 있다.
