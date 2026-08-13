# 대시보드 실행·시연 가이드 (2026-08-14 작성)

`web/README.md`는 구현 결정을 다루고, 이 문서는 **심사 당일 실제로 켜는 절차**만 다룬다.

---

## 1. 매번 실행 — 두 명령어

**① 대시보드 서버**(PowerShell)

```powershell
$env:DASHBOARD_DATA_ROOT = "C:\AI_Bootcamp_PJT\keunsamchon-agent-plan\specs"
$env:DISPATCH_MODE = "resend"
python web/app.py
```

Git Bash에서는 한 줄로:
```bash
DASHBOARD_DATA_ROOT=/c/AI_Bootcamp_PJT/keunsamchon-agent-plan/specs DISPATCH_MODE=resend python web/app.py
```

포트 `8420`에 뜬다. `http://127.0.0.1:8420` 으로 로컬 확인 가능.

**② 외부 공개용 고정 터널**

```
C:\Users\anstj\ngrok\ngrok.exe http --domain=stoic-bubble-portion.ngrok-free.dev 8420
```

**심사위원에게 줄 링크**: **https://stoic-bubble-portion.ngrok-free.dev**

①·② 둘 다 켜져 있어야 링크가 살아있다. 창을 닫으면(또는 컴퓨터를 끄면) 같이 죽는다 — 시연 내내 두 창을 그대로 띄워 둔다.

---

## 2. `DISPATCH_MODE` — 승인 버튼을 눌렀을 때 무슨 일이 나는가

| 값 | 승인 버튼을 누르면 |
|---|---|
| (설정 안 함, 기본값) `mock` | 로그만 남긴다. 실제로 아무것도 안 나간다 |
| `real` | `claude -p`로 G5 스킬을 부르지만, 그 스킬은 메일 발송 도구가 없어 **실제 발송까지는 안 간다** |
| **`resend`** (시연용) | **실제로 Resend API를 통해 메일이 나간다.** 단 수신자는 발송대기 파일의 실제 주소(일본 기업)가 아니라 **`.env`의 `DEMO_RECIPIENT`로 강제 치환**된다 — 실제 기업에는 절대 나갈 수 없는 안전장치 |

**시연에서 승인 액션을 실제로 보여주려면 `DISPATCH_MODE=resend`가 필수다.** 위 ①번 명령어에 이미 포함돼 있다.

`RESEND_API_KEY`·`DEMO_RECIPIENT`는 이미 `.env`에 등록돼 있다(존재만 확인했고 값은 이 문서에도, 대화에도 남기지 않는다 — `CLAUDE.md` 6절).

---

## 3. 사전 준비 (한 번만 — 이미 끝남, 기록용)

- ngrok 계정 가입 + `ngrok config add-authtoken` 등록 완료
- 무료 고정 서브도메인 `stoic-bubble-portion.ngrok-free.dev` 발급 완료
- **Windows Defender가 `ngrok.exe`를 위협으로 오인해 삭제하는 문제가 있어**, `C:\Users\anstj\ngrok` 폴더를 바이러스 및 위협 방지 제외 목록에 등록해 뒀다 — 이 컴퓨터에서만 유효. 다른 PC에서 실행하면 같은 예외 등록이 다시 필요하다

---

## 4. 문제 해결

| 증상 | 원인 · 조치 |
|---|---|
| 터널 링크가 안 열림 | ①(서버) 또는 ②(터널) 창이 꺼져 있는지 확인. `curl http://127.0.0.1:8420/`로 로컬부터 확인 |
| `ngrok.exe`가 실행 안 되거나 파일이 사라짐 | Defender가 삭제한 것 — `C:\Users\anstj\ngrok` 폴더가 예외 목록에 있는지 재확인 |
| 승인을 눌러도 메일이 안 옴 | `DISPATCH_MODE=resend`로 서버를 켰는지 확인(안 넣으면 기본 mock). 승인 화면의 발송 결과 메시지에 실패 사유가 표시된다 |
| 포트 8420이 이미 사용 중 | PowerShell에서 `Get-NetTCPConnection -LocalPort 8420 | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }` 로 기존 프로세스 종료 후 재실행 |

---

## 5. 끝낼 때

두 창(서버·터널)을 그냥 닫으면 된다. 별도 정리 작업 없음 — `mock` 모드가 기본값이라 다음에 다시 켜면 안전한 상태로 돌아온다(실수로 `resend`가 계속 켜져 있을 걱정 없음).
