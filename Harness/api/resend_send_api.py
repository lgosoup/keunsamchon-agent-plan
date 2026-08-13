#!/usr/bin/env python3
"""발송 API 실제 구현(Resend) — dummy_send_api.sh와 같은 입출력 계약을 지키는 대체품.

`real_send_api.py`(SMTP)와 **형제 파일**이다. 둘 다 같은 계약을 지키므로 호출하는
쪽은 어느 것을 부르든 코드가 같다 — 발송 채널을 SMTP로 갈지 Resend로 갈지는
호출부가 아니라 "어느 파일을 부르는가"로 정해진다.

실제 자리: G5(제안메일제작발송)가 승인·법정표시 재확인을 통과한 건마다 발송
기록 파일(data/발송기록/{기업식별자}-{발송일시}.md)을 쓰고 나면, 그 파일이 새로
쓰인 것을 감지한 외부 시스템이 이 스크립트를 부른다 — G5 자신은
`disallowed-tools: Bash`라 직접 부르지 못한다(README.md "누가 이 스크립트를
부르는가" 참고).

입력(stdin, JSON): {"to": "<수신 주소>", "subject": "<제목>", "body": "<본문>",
                    "from": "<발신 주소, 미확보면 빈 문자열>",
                    "reply_to": "<회신 받을 주소, 선택>"}
출력(stdout, JSON): {"status": "sent", "message_id": "<Resend가 준 id>",
                     "sent_at": "<ISO 8601>"}
                    실패 시: {"status": "error", "reason": "<사유>"}

  ※ "reply_to"는 dummy/SMTP 계약에 없던 선택 필드다. 없으면 무시되므로 기존
    호출부는 그대로 동작한다. 회신 왕복을 검증하려면 이 값이 필요하다 —
    발신 주소가 onboarding@resend.dev일 때 그 주소로는 회신을 받을 수 없다.

설정(환경변수, .env — 값 자체는 이 파일에 쓰지 않는다):
  RESEND_API_KEY     — 필수. 없으면 실제 발송을 시도하지 않는다(세이프페일)
  RESEND_FROM_DEFAULT— 선택. 입력의 "from"이 비어 있을 때 쓸 발신 주소.
                       미설정 시 onboarding@resend.dev (도메인 인증 전 테스트 발신 주소)
  RESEND_REPLY_TO    — 선택. 입력의 "reply_to"가 비어 있을 때 쓸 회신 주소

RESEND_API_KEY가 없으면 **실제로 아무것도 보내지 않고**
{"status":"error","reason":"Resend 설정 없음..."}을 낸다 — 키가 없는 환경에
이 스크립트를 연결해도 dummy와 동일하게 무해하다.

⚠ 도메인 인증 전 제약(2026-08-13 현재 이 계정의 인증 도메인 0개):
  발신은 onboarding@resend.dev로만 가능하고, **수신자는 Resend 계정 소유자
  본인 이메일로 제한**된다. 모르는 제3자(실제 일본 기업)에게는 보낼 수 없다 —
  시연 목적에는 이 제약이 오히려 안전장치로 작동한다. 발송 도메인 정책은
  기업 답변 대기 항목이다(root `docs/10_기업조사.md` 6절 #8).
"""
import datetime
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

RESEND_ENDPOINT = "https://api.resend.com/emails"
FALLBACK_FROM = "onboarding@resend.dev"


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


def _load_dotenv() -> None:
    """저장소 루트 .env에서 아직 설정되지 않은 값만 채운다.

    이미 환경변수로 들어온 값은 절대 덮어쓰지 않는다(셸에서 넘긴 쪽이 이긴다).
    값을 출력하거나 로그에 남기지 않는다 — 비밀은 .env 밖으로 나가지 않는다
    (root CLAUDE.md 6절).
    """
    env_path = _repo_root() / ".env"
    if not env_path.is_file():
        return
    try:
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            if key and key not in os.environ:
                os.environ[key] = value.strip().strip('"').strip("'")
    except OSError:
        pass


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


def _fail(now: str, log_line: str, reason: str) -> int:
    _log(f"[{now}] {log_line}\n")
    print(json.dumps({"status": "error", "reason": reason}, ensure_ascii=False))
    return 1


def main() -> int:
    # Windows 콘솔 기본 코드페이지(cp949)로는 em-dash·한글·일본어가
    # stdout/stdin에서 UnicodeEncodeError/DecodeError를 낸다
    # (real_send_api.py가 실행 테스트로 실제 재현한 버그, 2026-08-13).
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stdin.reconfigure(encoding="utf-8")

    _load_dotenv()
    now = _now_iso()

    raw = sys.stdin.read()
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return _fail(now, "REJECTED — stdin이 JSON이 아님", "stdin이 JSON이 아님")

    to = (payload.get("to") or "").strip()
    subject = (payload.get("subject") or "").strip()
    body = payload.get("body") or ""
    sender = (payload.get("from") or os.environ.get("RESEND_FROM_DEFAULT") or FALLBACK_FROM).strip()
    reply_to = (payload.get("reply_to") or os.environ.get("RESEND_REPLY_TO") or "").strip()

    _log(f"[{now}] RECEIVED send-request to={to or '?'} subject={subject or '?'} from={sender or '(미확보)'}\n")

    if not to or not subject:
        return _fail(now, "REJECTED — to 또는 subject 없음", "to 또는 subject 누락")

    api_key = os.environ.get("RESEND_API_KEY")
    if not api_key:
        return _fail(
            now,
            "BLOCKED — Resend 설정 없음(RESEND_API_KEY 미설정), 실제 발송 시도 안 함",
            "Resend 설정 없음(RESEND_API_KEY 환경변수 필요) — 키 연결 대기",
        )

    request_body = {"from": sender, "to": [to], "subject": subject, "text": body}
    if reply_to:
        request_body["reply_to"] = [reply_to]

    req = urllib.request.Request(
        RESEND_ENDPOINT,
        data=json.dumps(request_body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            # User-Agent를 빼면 api.resend.com 앞단의 Cloudflare가 urllib 기본
            # UA(Python-urllib/3.x)를 봇으로 보고 403 "error code: 1010"으로
            # 막는다 — Resend API 자체는 정상인데 요청이 도달조차 못 한다.
            # 2026-08-13 실제 발송 시도에서 재현·확인.
            "User-Agent": "keunsamchon-agent-plan/1.0 (+resend_send_api.py)",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        # Resend는 실패 사유를 본문 JSON으로 주지만, 앞단 Cloudflare가 막은
        # 경우엔 평문("error code: 1010")이 온다 — JSON이 아니어도 원문을
        # 그대로 실어야 원인을 안다(파싱 실패 시 e.reason만 남기면 "Forbidden"
        # 한 단어가 되어 진짜 원인이 지워진다).
        try:
            raw_body = e.read().decode("utf-8", errors="replace").strip()
        except OSError:
            raw_body = ""
        detail = ""
        if raw_body:
            try:
                detail = json.loads(raw_body).get("message", "") or raw_body
            except ValueError:
                detail = raw_body
        return _fail(
            now,
            f"FAILED to={to} http={e.code} detail={detail or e.reason}",
            f"Resend 발송 실패(HTTP {e.code}): {detail or e.reason}",
        )
    except (urllib.error.URLError, OSError, ValueError) as e:
        return _fail(now, f"FAILED to={to} error={e}", f"Resend 발송 실패: {e}")

    message_id = result.get("id") or "(id 없음)"
    _log(f"[{now}] SENT(resend) to={to} message_id={message_id}\n")
    print(json.dumps({"status": "sent", "message_id": message_id, "sent_at": now}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
