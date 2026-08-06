# hook/ — 자동 트리거 명세

이 폴더는 이 하네스가 필요로 하는 11개 자동 트리거(Hook)의 명세다. **구현(실제로 어떻게 감시·스케줄링할지)은 이 하네스를 실행하는 플랫폼에서 사람이 직접 한다** — 여기서는 각 Hook이 (a) 언제 눌려야 하는지 (b) 무엇을 신호로 캡처해야 하는지 (c) 어느 스킬을 어떤 인자 형식으로 호출해야 하는지만 정의한다. `skills/*/SKILL.md`는 전부 이 신호를 슬래시 명령 인자로 받는 것을 전제로 이미 만들어져 있다 — Hook은 그 인자를 채워서 호출만 하면 된다.

**부트캠프 템플릿 예시(`settings.json` + `subagent_log.sh`)와 형식이 다른 이유**: 그 예시는 Claude Code 자체의 후킹 메커니즘(도구 호출 전후 자동 로깅·검증)이다. 이 하네스의 실행 플랫폼은 Claude Code가 아니고, 그 플랫폼의 Hook 설정 형식은 아직 정해지지 않았다(구현은 사람이 별도로 한다). 그래서 이 폴더는 설정 파일 형식이 아니라, **어느 플랫폼에 옮기든 그대로 구현할 수 있는 조건·신호·호출 계약 명세**로 채운다.

## 목록

| ID | 파일 | 트리거 종류 | 호출 대상 |
|---|---|---|---|
| H1 | `h01-reply-detected.md` | 이벤트 | `g7-reply-processing` |
| H2 | `h02-bounce-detected.md` | 이벤트 | `g6-delivery-status-judging` |
| H3 | `h03-no-response-deadline.md` | 스케줄(건별 타이머) | `g6-delivery-status-judging` |
| H4 | `h04-g7-correction-relay.md` | 이벤트(종속 — H1 결과에 종속) | `g6-delivery-status-judging` |
| H5 | `h05-g1-weekly-rediscovery.md` | 스케줄 | `g1-company-screening` |
| H6 | `h06-g5-production-trigger.md` | 하이브리드(이벤트+안전장치 스케줄) | `g5-proposal-email-dispatch` |
| H7 | `h07-g10-recollection-cycle.md` | 스케줄(건별 타이머) | `g10-recollection-judging` |
| H8 | `h08-g11-aggregation-cycle.md` | 이벤트(조건부) | `g11-response-aggregation` |
| H9 | `h09-criteria-consistency-review.md` | 이벤트 | `g12-qna` |
| H10 | `h10-g8-cause-analysis-trigger.md` | 이벤트(종속 — H4와 같은 종류) | `g8-cause-analysis` |
| H11 | `h11-g9-brief-generation-cycle.md` | 스케줄 | `g9-handoff-brief` |

각 파일의 항목 구성은 같다: 트리거 종류 / 트리거 조건 / 캡처할 신호 / 호출 대상 / 인자 형식 / 비고.

## H9는 실제 구현 예시가 있다

11개 중 **H9(criteria 수정 감지)만 Claude Code 자체의 Hook 메커니즘으로 실제 구현 가능**하다 — criteria 파일 수정은 이 실행 환경(Claude Code) 자신이 관측할 수 있는 사건이기 때문이다. 나머지 10개는 메일 도착·발송 서비스 응답·시간 경과처럼 이 실행 환경 밖의 사건이라 별도 플랫폼(구현은 사용자가 진행)이 있어야 감지된다.

- `settings.json` — `PostToolUse`(Edit·Write·MultiEdit) 훅 등록. 부트캠프 템플릿 예시와 같은 형식이다.
- `hook_h9_criteria_review.sh` — criteria 파일 수정을 감지해 변경 전/후 값으로 정합성 검토 질문을 조립하고 `/g12-qna`를 호출한다.

**둘 다 예시 구현이다** — 무인 배치 환경에서의 권한·비용 처리는 스크립트 주석에 남겨 두고 완결짓지 않았다(실행 환경마다 다르다).

## 세 갈래로 나뉜다

- **독립 진입(외부 사건·스케줄)**: H1·H2·H3·H5·H6·H7·H8·H9·H11 — 이 하네스 밖에서 오는 신호가 새 실행을 깨운다.
- **종속 파생(다른 실행의 결과가 만드는 후속 호출)**: H4·H10 — 독립된 외부 신호가 아니라 다른 Hook이 이미 돌린 실행의 산출물이 그 자리에서 다음 호출을 만든다.
- **읽기 전용 조회는 이 목록에 없다**: `g12-qna`(H9 제외)는 사람이 언제든 직접 부르는 별도 진입점이라 Hook이 아니다.
