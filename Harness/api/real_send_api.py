#!/usr/bin/env python3
"""발송 API 실제 구현 — dummy_send_api.sh와 같은 입출력 계약을 지키는 대체품.

실제 자리: G5(제안메일제작발송)가 승인·법정표시 재확인을 통과한 건마다
발송 기록 파일(data/발송기록/{기업식별자}-{발송일시}.md)을 쓰고 나면, 그
파일이 새로 쓰인 것을 감지한 외부 시스템(팀원이 만드는 발송 감시 플랫폼)이
이 스크립트를 부른다 — G5 자신은 `disallowed-tools: Bash`라 이 스크립트를
직접 부르지 못한다(README.md "누가 이 스크립트를 부르는가" 참고).
README.md "교체 방법"이 예고한 그 교체품이다 — 입출력 계약(아래)은
dummy_send_api.sh와 완전히 동일하게 유지했다. 호출하는 쪽(팀원이 만드는
발송 감시 플랫폼)은 dummy를 이 파일로 바꿔치기만 하면 되고, 자기 쪽 코드를
고칠 필요가 없다.

입력(stdin, JSON): {"to": "<수신 주소>", "subject": "<제목>", "body": "<본문>",
                    "from": "<발신 주소, 미확보면 빈 문자열>"}
출력(stdout, JSON): {"status": "sent", "message_id": "<발신 시각+무작위 기반>",
                     "sent_at": "<ISO 8601>"}
                    실패 시: {"status": "error", "reason": "<사유>"}

설정(환경변수, .env — 값 자체는 이 파일에 쓰지 않는다):
  SMTP_HOST         — 필수. 발송 서비스의 SMTP 서버 주소
  SMTP_PORT         — 선택, 기본 587(STARTTLS)
  SMTP_USER         — 필수. 인증 계정
  SMTP_PASS         — 필수. 인증 비밀번호/앱 비밀번호
  SMTP_FROM_DEFAULT — 선택. 입력의 "from"이 비어 있을 때 쓸 발신 주소
  SMTP_USE_TLS      — 선택, 기본 "1"(STARTTLS 사용). "0"이면 평문 연결(테스트용 로컬 서버 등)

SMTP_HOST·SMTP_USER·SMTP_PASS 중 하나라도 없으면 **실제로 아무것도 보내지
않고** {"status":"error","reason":"SMTP 설정 없음..."}을 낸다 — 계정이
아직 없는 지금 이 스크립트를 실수로 실제 호출 자리에 연결해도 안전하다
(dummy와 동일하게 무해). 계정이 오면 .env에 위 값만 채우면 되고, 이
파일은 다시 손댈 필요가 없다.
"""
import datetime
import json
import os
import smtplib
import sys
import uuid
from email.mime.text import MIMEText
from pathlib import Path


def _log_path() -> Path:
    log_dir = Path(__file__).resolve().parent.parent / "data" / "hook로그"
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir / "api-send.log"


def _log(line: str) -> None:
    try:
        with open(_log_path(), "a", encoding="utf-8") as f:
            f.write(line)
    except OSError:
        pass


def _now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def main() -> int:
    # Windows 콘솔 기본 코드페이지(cp949)로는 em-dash·한글이 stdout/stdin에서
    # UnicodeEncodeError/DecodeError를 낸다 — 실행 테스트로 실제 재현·확인(2026-08-13).
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stdin.reconfigure(encoding="utf-8")

    now = _now_iso()
    raw = sys.stdin.read()
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        _log(f"[{now}] REJECTED — stdin이 JSON이 아님\n")
        print(json.dumps({"status": "error", "reason": "stdin이 JSON이 아님"}, ensure_ascii=False))
        return 1

    to = (payload.get("to") or "").strip()
    subject = (payload.get("subject") or "").strip()
    body = payload.get("body") or ""
    sender = (payload.get("from") or os.environ.get("SMTP_FROM_DEFAULT") or "").strip()

    _log(f"[{now}] RECEIVED send-request to={to or '?'} subject={subject or '?'} from={sender or '(미확보)'}\n")

    if not to or not subject:
        _log(f"[{now}] REJECTED — to 또는 subject 없음\n")
        print(json.dumps({"status": "error", "reason": "to 또는 subject 누락"}, ensure_ascii=False))
        return 1

    host = os.environ.get("SMTP_HOST")
    user = os.environ.get("SMTP_USER")
    password = os.environ.get("SMTP_PASS")
    if not (host and user and password):
        _log(f"[{now}] BLOCKED — SMTP 설정 없음(SMTP_HOST/SMTP_USER/SMTP_PASS 미설정), 실제 발송 시도 안 함\n")
        print(json.dumps({
            "status": "error",
            "reason": "SMTP 설정 없음(SMTP_HOST/SMTP_USER/SMTP_PASS 환경변수 필요) — 계정 연결 대기",
        }, ensure_ascii=False))
        return 1

    if not sender:
        _log(f"[{now}] REJECTED — 발신 주소 없음(from도 SMTP_FROM_DEFAULT도 없음)\n")
        print(json.dumps({"status": "error", "reason": "발신 주소 없음"}, ensure_ascii=False))
        return 1

    port = int(os.environ.get("SMTP_PORT", "587"))
    use_tls = os.environ.get("SMTP_USE_TLS", "1") != "0"

    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = to

    try:
        with smtplib.SMTP(host, port, timeout=30) as server:
            if use_tls:
                server.starttls()
            server.login(user, password)
            server.sendmail(sender, [to], msg.as_string())
    except (smtplib.SMTPException, OSError) as e:
        _log(f"[{now}] FAILED to={to} error={e}\n")
        print(json.dumps({"status": "error", "reason": f"SMTP 발송 실패: {e}"}, ensure_ascii=False))
        return 1

    message_id = f"real-{uuid.uuid4().hex[:12]}"
    _log(f"[{now}] SENT(real) to={to} message_id={message_id}\n")
    print(json.dumps({"status": "sent", "message_id": message_id, "sent_at": now}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
