# G7(회신 해석·정리) — TimelyAI Harness

큰삼촌컴퍼니 기업과제의 G1~G11 기능 중 **G7 하나만** 구현 대상으로 선정해(2026-08-05, 선정 근거는 `00_TimelyAI_매핑설계.md` 0절 참조), Upstage 자사 에이전트 플랫폼 **TimelyAI**에서 실제로 돌아가도록 만든 harness다. 이 폴더 하나만으로 구조를 이해하고 재현할 수 있다 — 외부 저장소 경로를 참조하지 않는다.

## 폴더 구조

```
G7/
├─ spec.md              🔴 필수 — 결과 명확화 6요소 (목표/맥락/입력/범위/제약/출력/성공기준)
├─ 기준.md                🔴 필수 — spec.md의 판정 문장·값 (8분류, 수신거부 판별 표현, 번역 검증 3층)
├─ role-table.md         🟢 권장 — 역할·입력·출력·도구권한 표
├─ workflow.md           🟢 권장 — 실행 순서 요약 (상세는 package/automation/)
├─ hooks/README.md       🟢 권장 자리 — TimelyAI에 훅 계층이 없는 이유 + 대체 수단
├─ 00_TimelyAI_매핑설계.md — G7 Spec을 TimelyAI 개념(스킬/자동화/커넥터)에 매핑한 설계 근거·미확인 사항
└─ package/              TimelyAI에 실제로 업로드하는 파일들
   ├─ skills/g7-interpret/SKILL.md   🔴 필수 — 스킬 1 (해석)
   ├─ skills/g7-verify/SKILL.md      🔴 필수 — 스킬 2 (검증)
   ├─ automation/AGENT.md       🔴 필수 — 자동화(오케스트레이터)
   └─ README.md                      업로드 순서 + 첫 실행 확인 체크리스트
```

`data/`(입력 데이터 파일)와 커넥터 등록은 없다 — G7의 입력은 회신 텍스트 **붙여넣기**이고(spec.md 「확인 후 채울 것」), 발신 커넥터는 의도적으로 미연결이다(무관용 제약, `00_TimelyAI_매핑설계.md` 참조).

## 무엇을 확인해야 완성인가

`package/README.md`의 "확인 체크리스트"를 실제 TimelyAI 업로드 후 통과해야 한다. 이 저장소(Claude Code)에서는 TimelyAI를 직접 실행할 수 없어 — 설계·시뮬레이션 검증까지만 이 harness가 보장하고, 실제 동작 확인은 업로드 후 사람이 한다.
