# Harness — 제출용 패키지

**2026-08-06 — G1~G12 전 기능 + 데모 체인 스냅샷으로 패키징했다.** 정본은 원본 위치(`specs/`·`기준/`·`.claude/`)이고, 이 폴더는 제출·시연 때 한 번에 열어 보기 위한 복사본이다. 실제 메일 발송 인프라가 없는 구간은 `demo/` 아래 파일 머리에 `데모/시뮬레이션 — 실제 발송 아님`으로 표시했다.

## 패키지 구성

| 경로 | 내용 |
|---|---|
| `specs/` | G1~G12 Spec 스냅샷 |
| `기준/` | 기준 카드·JSON 스냅샷 |
| `skills/` | G1~G12 실행 스킬 스냅샷 |
| `agents/` | `.claude/agents` 전체 스냅샷 — G5·G7 서브에이전트, 빌드/런/채점 오케스트레이터, 검토 보조 에이전트 |
| `docs/` | 사용자 흐름·핵심문제·운영 변수 문서 |
| `demo/` | 실제 회사 데이터 기반 데모 체인 산출물 + 상류 근거 스냅샷 |
| `평가항목.md` | 제출 평가 기준 정본 전사본 |

## 원본 위치

| 기능 | Spec | 기준 카드 | 실행체 |
|---|---|---|---|
| G1 | `specs/G1_대상기업발굴.md` | `기준/G1_기업판정기준.json` | `.claude/skills/g1-기업판정/SKILL.md` |
| G2 | `specs/G2_세그먼트화.md` | `기준/G2_세그먼트기준.md` | `.claude/skills/g2-세그먼트화/SKILL.md` |
| G3 | `specs/G3_적합도평가.md` | `기준/G3_적합도기준.md` | `.claude/skills/g3-적합도평가/SKILL.md` |
| G4 | `specs/G4_연락처확보.md` | `기준/G4_연락처유효성기준.md` | `.claude/skills/g4-연락처확보/SKILL.md` |
| G5 | `specs/G5_제안메일제작발송.md` | `기준/G7_회신판정기준.md` 3절 재사용 | `.claude/skills/g5-제안메일제작발송/SKILL.md` + `.claude/agents/g5-*`(문안·번역·승인확인) |
| G6 | `specs/G6_발송결과판정.md` | `기준/G6_판정기준.md` | `.claude/skills/g6-발송결과판정/SKILL.md` |
| G7 | `specs/G7_회신해석정리.md` | `기준/G7_회신판정기준.md` | `.claude/skills/g7-회신처리/SKILL.md` + `.claude/agents/g7-*` |
| G8 | `specs/G8_원인분석.md` | `기준/G8_원인분석기준.md` | `.claude/skills/g8-원인분석/SKILL.md` |
| G9 | `specs/G9_위임브리프.md` | `기준/G4`·`기준/G3` 재사용 | `.claude/skills/g9-위임브리프/SKILL.md` |
| G10 | `specs/G10_재수집판단.md` | `기준/G1_기업판정기준.json` 재사용 | `.claude/skills/g10-재수집판단/SKILL.md` |
| G11 | `specs/G11_반응집계_기준조정.md` | 별도 카드 없음 | `.claude/skills/g11-반응집계/SKILL.md` |
| G12 | `specs/G12_질의응답.md` | 별도 카드 없음 | `.claude/skills/g12-질의응답/SKILL.md` |

## 데모 체인

`demo/`에는 `ingni-store-com` 기반 시연 흐름이 들어 있다. `demo/source/`에는 이 흐름이 참조한 상류 실제 데이터(`후보목록.md`, `SEG-A-v1.md`, `ingni-store-com` 연락처·채점, G5 발송대기 파일)를 같이 넣었다.

G1 실제 후보 판정 → G2 시험 세그먼트 → G4 실제 연락처 확보 → G5 데모 발송 기록 → G6 데모 상태 2건([회신], [무응답]) → G7 데모 회신 해석 → G8 데모 원인분석 → G9 데모 위임브리프 → G11 데모 집계까지 조인된다.

주의: 실제 INGNI에 메일을 보내거나 실제 회신을 받은 것이 아니다. 이 저장소에 없는 발송·바운스·수신 인프라만 명시적으로 시뮬레이션했다.
