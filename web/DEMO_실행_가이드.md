# 대시보드 실행·시연 가이드 (2026-08-14 작성)

`web/README.md`는 구현 결정을 다루고, 이 문서는 **심사 당일 실제로 켜는 절차**만 다룬다.

---

## 🚀 빠른 시작 — 터미널 3개, 순서대로 그대로 실행

**어느 것도 자동으로 켜지지 않는다.** 서버·터널·회신 감시는 전부 독립된 프로세스라 매번 각각 켜야 한다.

### 터미널 1 — 대시보드 서버

PowerShell:
```powershell
$env:DASHBOARD_DATA_ROOT = "C:\AI_Bootcamp_PJT\keunsamchon-agent-plan\specs"
$env:DISPATCH_MODE = "resend"
python web/app.py
```
Git Bash:
```bash
DASHBOARD_DATA_ROOT=/c/AI_Bootcamp_PJT/keunsamchon-agent-plan/specs DISPATCH_MODE=resend python web/app.py
```
→ `http://127.0.0.1:8420` 에서 로컬 확인 가능.

### 터미널 2 — 외부 공개용 고정 터널

```
C:\Users\anstj\ngrok\ngrok.exe http --domain=stoic-bubble-portion.ngrok-free.dev 8420
```
**심사위원에게 줄 링크**: **https://stoic-bubble-portion.ngrok-free.dev**

### 터미널 3 — 회신 자동 감시 (회신함까지 시연할 때만 필요)

```bash
python Harness/hook/imap_reply_poller.py --watch --dispatch
```
승인 → 실제 메일 발송 → 상대 회신 → **회신함 화면에 자동으로 뜨는 것**까지 보여주려면 이것도 켜야 한다. 승인 대기함 시연만 할 거면 생략 가능.

**세 창 다 시연이 끝날 때까지 그대로 켜둔다.** 닫거나 컴퓨터를 절전모드로 두면 그 순간부터 죽는다 — **시연 중엔 노트북을 덮거나 이동하지 않는다** (③은 처리 중 네트워크가 끊기면 그 회신 1건이 자동 재시도 없이 멈춘다, 4절 참조).

---

## 1. `DISPATCH_MODE` — 승인 버튼을 눌렀을 때 무슨 일이 나는가

| 값 | 승인 버튼을 누르면 |
|---|---|
| (설정 안 함, 기본값) `mock` | 로그만 남긴다. 실제로 아무것도 안 나간다 |
| `real` | `claude -p`로 G5 스킬을 부르지만, 그 스킬은 메일 발송 도구가 없어 **실제 발송까지는 안 간다** |
| **`resend`** (시연용) | **실제로 Resend API를 통해 메일이 나간다.** 단 수신자는 발송대기 파일의 실제 주소(일본 기업)가 아니라 **`.env`의 `DEMO_RECIPIENT`로 강제 치환**된다 — 실제 기업에는 절대 나갈 수 없는 안전장치 |

**시연에서 승인 액션을 실제로 보여주려면 `DISPATCH_MODE=resend`가 필수다.** 위 터미널 1 명령어에 이미 포함돼 있다.

`RESEND_API_KEY`·`DEMO_RECIPIENT`는 이미 `.env`에 등록돼 있다(존재만 확인했고 값은 이 문서에도, 대화에도 남기지 않는다 — `CLAUDE.md` 6절).

---

## 2. 사전 준비 (한 번만 — 이미 끝남, 기록용)

- ngrok 계정 가입 + `ngrok config add-authtoken` 등록 완료
- 무료 고정 서브도메인 `stoic-bubble-portion.ngrok-free.dev` 발급 완료
- **Windows Defender가 `ngrok.exe`를 위협으로 오인해 삭제하는 문제가 있어**, `C:\Users\anstj\ngrok` 폴더를 바이러스 및 위협 방지 제외 목록에 등록해 뒀다 — 이 컴퓨터에서만 유효. 다른 PC에서 실행하면 같은 예외 등록이 다시 필요하다

---

## 3. 화면에서 확인할 수 있는 것

| 화면 | 확인 포인트 |
|---|---|
| 개요(홈) | "성과" 섹션 — 판정 통과·연락처 확보율·발송 승인 등 실측 지표 |
| ③ 연락처 현황 | 기업이 이름까지 지목한 화면(도메인 대신 상태·등급 표시) |
| ④ 승인 대기함 | **여기서 승인 버튼을 실제로 눌러 보여준다** — 유일한 실제 "액션" 화면 |
| ⑤ 발송 현황 | 방금 승인한 건이 발송 기록에 뜨는지 |
| ⑥ 회신함 | 상단 배너로 회신 감시 상태(🟢/🔴) 확인 가능 |

---

## 4. 문제 해결

| 증상 | 원인 · 조치 |
|---|---|
| 터널 링크가 안 열림 | 터미널 1(서버) 또는 2(터널)가 꺼져 있는지 확인. `curl http://127.0.0.1:8420/`로 로컬부터 확인 |
| `ngrok.exe`가 실행 안 되거나 파일이 사라짐 | Defender가 삭제한 것 — `C:\Users\anstj\ngrok` 폴더가 예외 목록에 있는지 재확인 |
| 승인을 눌러도 메일이 안 옴 | `DISPATCH_MODE=resend`로 서버를 켰는지 확인(안 넣으면 기본 mock). 승인 화면의 발송 결과 메시지에 실패 사유가 표시된다 |
| 포트 8420이 이미 사용 중 | PowerShell에서 `Get-NetTCPConnection -LocalPort 8420 \| ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }` 로 기존 프로세스 종료 후 재실행 |
| 회신함에 "🔴 회신 감시가 멎었습니다" | 터미널 3이 안 켜져 있거나 죽은 것. 다시 실행하면 된다 |
| 회신함 "해석 중"에서 몇 분 넘게 안 넘어감 | 터미널 3 처리 중 네트워크가 끊긴 것(노트북 절전·이동 등). **2026-08-14 수정 완료** — 이제는 레코드가 실제로 생긴 것을 확인한 뒤에만 읽음 처리하므로, 끊겨도 다음 감시 주기(60초 뒤)에 같은 메일을 자동으로 다시 시도한다. 그래도 몇 분 넘게 안 풀리면 채팅으로 "회신함 오류"라고 알려주면 수동으로 마무리해줄 수 있다 |

---

## 5. 끝낼 때

세 창(서버·터널·회신 감시)을 그냥 닫으면 된다. 별도 정리 작업 없음 — `mock`이 기본값이라 다음에 다시 켤 때 실수로 `resend`가 켜져 있을 걱정은 없다(매번 직접 지정해야 켜짐).
