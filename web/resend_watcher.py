"""발송기록 감시자 — `g5-제안메일제작발송` 발송 모드가 무관용 게이트를 통과시켜
새로 쓴 `specs/발송기록/*.md`를 찾아 아직 실제 Resend 발송이 안 된 것만 실제로 보낸다.

왜 필요한가: `web/dispatch.py`의 `DISPATCH_MODE=resend`는 승인 클릭 즉시 스킬을
백그라운드로 던지기만 하고 기다리지 않는다(스킬 실행이 LLM 호출이라 몇 초~몇 분
걸리는 비동기 작업이라서다, `docs/34` 7절 "정지점에서 대기하지 않고 종료"와 같은
원칙). 그래서 스킬이 게이트를 다 통과한 **뒤에** 실제 발송을 잇는 별도 자리가
필요하고, 그 자리가 이 스크립트다 — `.claude/hooks/dummy_platform_poll.sh`가 다른
Hook들의 "언제 부를지"를 감시하는 것과 같은 패턴이다.

이 스크립트 자신은 새 판정 로직을 만들지 않는다 — `dispatch.dispatch_pending_resend_records()`
하나를 호출할 뿐이고, 그 함수가 하는 일(법정 표시·발송금지 재확인 후 Resend 호출,
결과를 발송기록 파일에 이어 적기)은 이미 `web/dispatch.py`에 있다.

실행: python web/resend_watcher.py
(주기 실행하려면 다른 Hook들처럼 Windows 작업 스케줄러 등에 등록 — 이 스크립트가
스스로 스케줄을 돌지는 않는다, `imap_reply_poller.py`의 `--watch`와 달리 매번
한 번 훑고 끝낸다: 발송은 승인 즉시성이 중요해 폴링 주기를 넓게 둘 이유가 없고,
좁게 두려면 OS 스케줄러가 이미 그 역할을 한다)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import dispatch


def main():
    results = dispatch.dispatch_pending_resend_records()
    if not results:
        print("처리할 발송기록 없음(전부 이미 실제 발송 완료됐거나 발송기록 자체가 없음)")
        return
    for r in results:
        status = r.get("status")
        cid = r.get("company_id") or r.get("record")
        if status == "sent":
            print(f"[SENT] {cid} -> message_id={r.get('message_id')}")
        elif status == "skipped":
            continue
        else:
            print(f"[{status}] {cid} — {r.get('reason')}")


if __name__ == "__main__":
    main()
