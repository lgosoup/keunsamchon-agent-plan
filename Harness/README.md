# Harness — 해외 잠재고객 탐색·제안 메일 AI 에이전트

일본 기업 공개 정보를 근거로 후보를 발굴하고, 특성이 비슷한 기업끼리 묶어 문안을 만들고, 사람 승인을 거쳐 발송하고, 회신을 해석해 반응을 학습에 되먹이는 12개 기능(G1~G12)의 하네스다. 이 폴더 하나로 완결된다 — 다른 어떤 파일도 참조하지 않는다.

## 구성

| 경로 | 내용 |
|---|---|
| `spec.md` | **이 하네스 전체**의 6요소(목표·맥락·범위·제약·출력 형식·성공 기준) — 폴더를 열었을 때 가장 먼저 읽는 한 장. 개별 기능 6요소는 `specs/`가 정본이며 여기서 복제하지 않는다 |
| `specs/`(각 기능 카드) | 기능 12개, 각각 목표·맥락·입력·범위·제약·출력 형식·성공 기준 6요소로 확정. **스킬이 실행마다 다시 읽는 런타임 필수 요소**라 하나로 합치지 않았다 |
| `skills/` | 실제 일을 하는 재사용 절차 12개(`SKILL.md`) |
| `agents/` | 스킬을 실행하는 서브에이전트 5개 + 실행 배선을 맡는 오케스트레이터 1개(`run-orchestrator`) |
| `criteria/` | 판정 값·임계값 카드 — 무엇을 보고 O/X를 가르는가(Spec과 짝) |
| `data/` | 파이프라인 실행 산출물이 쌓이는 자리 — G1~G7·G12를 합성 시나리오 1회 실행한 결과가 채워져 있다(실제 발송·수신은 아님, `data/README.md` 참조) |
| `role-table.md` | 전체 실행체 역할·입력·출력·도구 권한 한 표 |
| `workflow.md` | 완성 시 사람이 실제로 언제·어떻게 마주치는가(리듬 3종·정지점 2곳) |
| `hook/` | 자동 트리거 12개(H1~H12) 명세 — 언제·무슨 신호로·어느 스킬을 호출하는가. **H9(criteria 수정 감지)·H12(발송 승인 감지, 2026-08-10 신설)는 Claude Code 자체 메커니즘으로 실제 구현**(`settings.json`+`hook_h9_criteria_review.sh`+`hook_h12_approval_send_gate.sh`)이고, **나머지 10개는 더미 모듈**(`hook_h01_*.sh`~`hook_h11_*.sh`) — 감지·스케줄링은 여전히 팀원이 만드는 플랫폼의 일이고, 이 더미는 이미 감지된 신호를 정해진 인자로 받아 대상 스킬을 호출·전달 로그만 남긴다(`hook/README.md` 참조) |
| `api/` | **발송 API 더미**(2026-08-10 신설) — `g5-proposal-email-dispatch`가 쓰는 `data/발송기록/`을 감지해 실제로 발송하는 외부 시스템(팀원 연동 중, `disallowed-tools: Bash`라 G5 자신은 못 부른다)이 호출할 자리를 대신한다. 입출력 계약만 지키면 실제 API로 그대로 바꿔치기 가능(`api/README.md` 참조) |
| `docs/` | 왜 이 구조인가(`problem-and-solution.md`), 운영 변수의 단일 출처(`deployment-assumptions.md`), 확정값의 근거(`design-rationale.md`), 합성 데이터 검증 기록(`test-validation.md`) |

## 기능 12개 — Spec · 판정 값 · 실행체

| 기능 | Spec | 판정 값 | 실행체 |
|---|---|---|---|
| G1 대상 기업 발굴 | `specs/g1-company-screening.md` | `criteria/g1-company-screening.json` | `skills/g1-company-screening/SKILL.md` |
| G2 세그먼트화 | `specs/g2-segmentation.md` | `criteria/g2-segmentation.md` | `skills/g2-segmentation/SKILL.md` |
| G3 적합도 평가(부가) | `specs/g3-fit-scoring.md` | `criteria/g3-fit-scoring.md` | `skills/g3-fit-scoring/SKILL.md` |
| G4 연락처 확보 | `specs/g4-contact-acquisition.md` | `criteria/g4-contact-acquisition.md` | `skills/g4-contact-acquisition/SKILL.md` |
| G5 제안 메일 제작·발송 | `specs/g5-proposal-email-dispatch.md` | `criteria/g7-reply-processing.md` 3절 재사용(번역 검증 기준 공용) | `skills/g5-proposal-email-dispatch/SKILL.md` + `agents/g5-copy-drafting.md`·`g5-translation-verification.md`·`g5-approval-check.md` |
| G6 발송 결과 판정 | `specs/g6-delivery-status-judging.md` | `criteria/g6-delivery-status-judging.md` | `skills/g6-delivery-status-judging/SKILL.md` |
| G7 회신 해석·정리 | `specs/g7-reply-processing.md` | `criteria/g7-reply-processing.md` | `skills/g7-reply-processing/SKILL.md` + `agents/g7-reply-interpretation.md`·`g7-translation-verification.md` |
| G8 원인 분석(부가) | `specs/g8-cause-analysis.md` | `criteria/g8-cause-analysis.md` | `skills/g8-cause-analysis/SKILL.md` |
| G9 사람 접촉 위임 브리프(부가) | `specs/g9-handoff-brief.md` | `criteria/g4-contact-acquisition.md`·`criteria/g3-fit-scoring.md` 재사용 | `skills/g9-handoff-brief/SKILL.md` |
| G10 재수집 판단(부가) | `specs/g10-recollection-judging.md` | `criteria/g1-company-screening.json` 재사용 | `skills/g10-recollection-judging/SKILL.md` |
| G11 반응 집계·기준 조정(부가) | `specs/g11-response-aggregation.md` | `criteria/g11-response-aggregation.md` | `skills/g11-response-aggregation/SKILL.md` |
| G12 질의응답(부가) | `specs/g12-qna.md` | 별도 카드 없음(판정 문턱이 아니라 조회) | `skills/g12-qna/SKILL.md` |

**MVP는 G1·G2·G4·G5·G6·G7 6개다.** 나머지(G3·G8·G9·G10·G11·G12)는 부가 기능이며, 구조는 확정돼 있지만 일부는 발송·회신 데이터가 쌓여야 실제로 값이 채워진다(각 Spec의 "확인 후 채울 것" 참조).

## 실행

전체 파이프라인은 `agents/run-orchestrator.md`가 배선한다 — 조사(G1~G4)는 즉시 연쇄, 발송(G5)은 사람 승인에서 반드시 멈추는 정지점, 반응(G6~G7)은 바운스·회신 도착을 기다리는 비동기 리듬이다. 세 리듬의 정의와 사람이 실제로 멈추는 두 지점은 `workflow.md`를 본다. 개별 기능만 단독으로 부를 때는 각 `skills/*/SKILL.md`의 `/이름 인자` 형식을 그대로 쓴다.
