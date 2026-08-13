# api/ — 외부 발송 API

이 폴더는 실제 메일 발송 호출이 들어갈 자리를 담는다. `hook/`과 성격이 다르다 — `hook/`은 **밖에서 안으로** 들어오는 신호(회신 도착·바운스 등)를 받는 자리이고, 여기는 **안에서 밖으로** 나가는 호출(실제로 메일을 보내는 것) 자리다.

## 있는 것

- `dummy_send_api.sh` — `to`·`subject`·`body`·`from`을 stdin JSON으로 받아 아무것도 실제로 보내지 않고 `{"status":"sent","message_id":"dummy-...","sent_at":"..."}` 형식의 성공 응답만 stdout으로 낸다. 받았는지·보낸 것으로 처리했는지는 `data/hook로그/api-send.log`에 남긴다. **계약을 눈으로 확인하거나 인프라 없이 발송 로직 나머지를 테스트할 때 계속 쓴다.**
- **`resend_send_api.py` (2026-08-13 신설, 지금 쓰는 것)** — Resend API로 실제 발송하는 구현체. `dummy_send_api.sh`·`real_send_api.py`와 **입출력 계약이 동일**하며, 선택 필드 `reply_to` 하나만 더 받는다(없으면 무시되므로 기존 호출부는 그대로 동작한다). 표준 라이브러리만 쓴다(`urllib`). 환경변수 `RESEND_API_KEY`(필수, 값은 `.env`)·`RESEND_FROM_DEFAULT`·`RESEND_REPLY_TO`(둘 다 선택). **키가 없으면 실제로 아무것도 보내지 않고 `{"status":"error","reason":"Resend 설정 없음..."}`만 낸다** — `real_send_api.py`와 같은 세이프페일 구조다.
- **`real_send_api.py` (2026-08-13 신설)** — SMTP로 실제 발송하는 구현체. `dummy_send_api.sh`와 **입출력 계약이 완전히 동일**해서 호출부(팀원이 만드는 발송 감시 플랫폼) 코드를 안 바꾸고 파일만 바꿔치기하면 된다. 환경변수(`SMTP_HOST`·`SMTP_PORT`·`SMTP_USER`·`SMTP_PASS`·`SMTP_FROM_DEFAULT`·`SMTP_USE_TLS`, 값은 `.env`)로 계정을 받고, **셋(`SMTP_HOST`·`SMTP_USER`·`SMTP_PASS`) 중 하나라도 없으면 실제로 아무것도 보내지 않고 `{"status":"error","reason":"SMTP 설정 없음..."}`만 낸다** — 계정이 아직 없는 지금 이 파일을 호출 자리에 미리 연결해 둬도 dummy와 똑같이 무해하다.

## 지금 상태 — Resend 경로는 실제 발송까지 검증 완료 (2026-08-13)

**발송 채널로 Resend를 채택했고, 실제 메일 1건이 수신함에 도착하는 것까지 확인했다.** `resend_send_api.py`로 일본어 제안 문안(법정 표시 4종 포함)을 실제 발송해 Resend가 `Status: delivered`를 반환하는 것까지 확인했다(message_id `2b210f3c-...`, 로그는 `data/hook로그/api-send.log`). 이 과정에서 실제 버그 하나를 발견·수정했다 — **User-Agent 헤더를 안 붙이면 `api.resend.com` 앞단의 Cloudflare가 urllib 기본 UA(`Python-urllib/3.x`)를 봇으로 보고 403 `error code: 1010`으로 막는다.** Resend API 자체는 정상인데 요청이 도달조차 못 하는 것이라, 오류 본문이 JSON이 아닌 평문으로 와서 원래 코드가 사유를 `Forbidden` 한 단어로 지워 버리던 문제도 함께 고쳤다(파싱 실패 시 원문을 그대로 싣는다).

**남은 제약은 도메인 인증뿐이고, 이는 의도적으로 보류 중이다.** 인증 도메인이 0개라 발신은 `onboarding@resend.dev`로만 가능하고 **수신자는 Resend 계정 소유자 본인 이메일로 제한**된다 — 모르는 제3자(실제 일본 기업)에게는 보낼 수 없다. 시연 목적에는 이 제약이 오히려 안전장치로 작동하므로 그대로 둔다. 발송 도메인·메일 계정 정책은 기업 답변 대기 항목이며(root `docs/10_기업조사.md` 6절 #8, `docs/92` 8행), 우리가 임의 도메인을 사서 확정하지 않는다.

## SMTP 경로 (대안, 계정 대기)

**코드는 완성이고, 남은 건 계정뿐이다.** `real_send_api.py`는 `dummy_send_api.sh`의 계약을 그대로 지키는 SMTP 클라이언트 구현이며, 팀원이 실제 발송 계정(SMTP 서버·인증정보)을 마련해 `.env`에 채우기만 하면 코드 수정 없이 바로 동작한다 — CLAUDE.md 6절(비밀은 `.env`에만, 이 파일이 직접 값을 갖지 않는다)을 지키며 완성할 수 있는 만큼은 완성했다.

**세이프페일 경로는 2026-08-13 실제로 실행해 확인했다.** `echo '{"to":"test@example.com","subject":"t","body":"본문 테스트"}' | python real_send_api.py`를 실제로 돌려 `{"status":"error","reason":"SMTP 설정 없음..."}`이 정확히 나오고 `data/hook로그/api-send.log`에 `BLOCKED` 로그가 남는 것까지 확인했다. 이 과정에서 실제 버그 하나를 발견·수정했다 — Windows 콘솔 기본 코드페이지(cp949)로는 `print()`가 한글·em-dash를 못 내보내 `UnicodeEncodeError`로 죽었고, `sys.stdout`/`sys.stdin`을 UTF-8로 재설정해 해결했다.

**남은 건 실제 계정으로 1건 발송해 보는 것뿐이고, 이건 사용자 지시로 보류 중이다(2026-08-13).** 실 SMTP 계정(팀원 발송 인프라 또는 임시 테스트 계정)이 준비되면 `.env`에 `SMTP_HOST`/`SMTP_USER`/`SMTP_PASS`만 채우고 같은 명령을 다시 돌리면 된다 — 코드는 이미 완성돼 있다.

## 누가 이 스크립트를 부르는가 (2026-08-10 정정)

**`g5-proposal-email-dispatch`(G5) 실행체 자신은 이 스크립트를 부르지 않는다 — 부를 수도 없다.** 그 스킬은 `disallowed-tools: Bash`로 Bash 자체를 막아 뒀다(발신 도구를 실행체가 직접 쥐지 않는다는 설계). G5가 실제로 하는 일은 승인·법정 표시 재확인을 통과한 건마다 `data/발송기록/{기업식별자}-{발송일시}.md`를 **쓰는 것**까지다.

이 스크립트를 부르는 자리는 **그 발송 기록 파일이 새로 쓰인 것을 감지해 실제 발송을 수행하는 외부 시스템**이다 — Hook(H1~H11)과 같은 성격이다: 이 하네스 실행 환경 밖의 사건(이 경우 "발송 기록 파일 생성")을 감지해서 호출하는 것은 팀원이 만드는 플랫폼의 일이고, 여기 있는 것은 그 호출이 받을 입력과 돌려줄 출력의 계약뿐이다.

## 교체 방법

**세 파일이 같은 계약을 지키므로, 호출하는 쪽(팀원이 만드는 발송 감시 플랫폼)은 "어느 파일을 부르는가"만 바꾸면 된다** — 입력·출력 형식이 동일해 그쪽 코드는 안 바뀐다.

| 부를 파일 | 언제 |
|---|---|
| `dummy_send_api.sh` | 계약만 눈으로 확인하거나, 인프라 없이 발송 로직 나머지를 테스트할 때 |
| **`resend_send_api.py`** | **지금 기본값.** `.env`에 `RESEND_API_KEY`만 있으면 된다 |
| `real_send_api.py` | 회사가 자체 SMTP 서버를 쓰기로 정한 경우. `.env`에 SMTP 계정 3종을 채운다 |
