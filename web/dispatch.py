"""승인 대기함 액션 (docs/35 4-2절, A안).
승인 버튼 클릭 시: ① 파일에 승인 기록을 쓴다 ② 발송 트리거를 같은 요청 안에서 호출한다.

DISPATCH_MODE:
  mock  (기본, 테스트용) — 로그만 남긴다. 아무것도 나가지 않는다.
  real                   — `claude -p "/g5-... 발송"`을 띄운다. 그 스킬은
                           `disallowed-tools: Bash`라 **실제 메일은 못 보낸다**
                           (발송 기록 파일을 쓰는 데까지가 그 스킬의 일이다).
  resend                 — `Harness/api/resend_send_api.py`를 불러 **실제로 메일을
                           보낸다.** 웹이 Resend를 직접 호출하지 않고 그 스크립트를
                           부르는 이유: `Harness/api/README.md`가 정의한 "발송 기록이
                           새로 쓰인 것을 감지한 외부 시스템이 그 스크립트를 부른다"의
                           그 외부 시스템 자리가 바로 여기다. 발송 로직을 두 벌로
                           복제하지 않는다.

⚠ resend 모드의 수신자 강제 치환:
  Resend 도메인 인증 전이라 수신자가 계정 소유자 본인으로 제한된다. 그래서 이
  모드는 발송대기 파일의 실제 수신 주소(일본 기업)로 보내지 않고 **환경변수
  DEMO_RECIPIENT로 강제 치환**한다. DEMO_RECIPIENT가 없으면 발송하지 않는다 —
  시연 중 실수로 실제 기업에 나가는 경로를 코드 레벨에서 막는다.
"""
import datetime
import json
import os
import re
import subprocess
import sys
from pathlib import Path

from data_source import read_text, write_text, data_root

REPO_ROOT = Path(__file__).resolve().parent.parent
RESEND_SCRIPT = REPO_ROOT / "Harness" / "api" / "resend_send_api.py"


def _now():
    return datetime.datetime.now().strftime("%Y-%m-%d-%H%M%S")


def _replace_row(body: str, label: str, value: str) -> str:
    import re
    pattern = rf"(\|\s*{re.escape(label)}\s*\|)([^\|\n]*)(\|)"
    return re.sub(pattern, lambda m: f"{m.group(1)} {value} {m.group(3)}", body, count=1)


def decide(file_rel: str, company_id: str, decision: str, approver: str = "담당자", reason: str = "") -> dict:
    """decision: '승인' | '거부'. 해당 회사 항목의 승인란만 고쳐서 파일 전체를 다시 쓴다."""
    raw = read_text(file_rel)
    import re
    # 두 표기 관례를 다 받는다 — parsers.py의 _APPROVAL_HEADER_RE와 동일한 이유(2026-08-12).
    headers = list(re.finditer(r"(?m)^##\s*(?:\d+절\s*승인\s*대기\s*건.*|건\s*\d+\s*—.*)$", raw))
    target_idx = None
    for i, h in enumerate(headers):
        if company_id in h.group(0):
            target_idx = i
            break
    if target_idx is None:
        return {"ok": False, "error": f"{company_id} 항목을 찾을 수 없음"}

    start = headers[target_idx].end()
    end = headers[target_idx + 1].start() if target_idx + 1 < len(headers) else len(raw)
    body = raw[start:end]

    body = _replace_row(body, "승인 / 거부", decision)
    if decision == "승인":
        body = _replace_row(body, "승인자", approver)
        body = _replace_row(body, "승인일시", _now())
    else:
        body = _replace_row(body, "거부 사유 (거부일 때)", reason or "(사유 미기재)")

    new_raw = raw[:start] + body + raw[end:]
    write_text(file_rel, new_raw)

    dispatch_result = None
    if decision == "승인":
        dispatch_result = trigger_dispatch(file_rel, company_id, body)

    return {"ok": True, "dispatch": dispatch_result}


def _strip_quote(md: str) -> str:
    """`> `로 시작하는 인용구 블록을 평문 본문으로 되돌린다."""
    lines = [re.sub(r"^>\s?", "", l) for l in md.splitlines()]
    return "\n".join(lines).strip()


def extract_mail(body: str) -> dict:
    """발송대기 파일의 한 항목에서 실제 발송에 필요한 값만 뽑는다.

    parsers.parse_approvals()와 같은 자리를 보지만 용도가 다르다 — 저쪽은
    화면 표시용 HTML, 여기는 발송용 평문이다."""
    subject = ""
    m = re.search(r"\*\*일본어\s*제목\*\*[:：]?\s*([^\n]+)", body)
    if m:
        subject = m.group(1).strip()
    else:
        m = re.search(r"###\s*일본어\s*제목\s*\n+件名[:：]\s*([^\n]+)", body)
        if m:
            subject = m.group(1).strip()

    text = ""
    m = re.search(r"\*\*일본어\s*본문\*\*\s*\n+((?:>.*(?:\n|$))+)", body)
    if not m:
        m = re.search(r"###\s*일본어\s*본문\s*\n+((?:>.*(?:\n|$))+)", body)
    if m:
        text = _strip_quote(m.group(1))

    to_original = ""
    m = re.search(r"\|\s*수신\s*주소\s*\|\s*([^\|\n]+)\|", body)
    if m:
        to_original = m.group(1).strip()

    return {"subject": subject, "text": text, "to_original": to_original}


def _send_via_resend(file_rel: str, company_id: str, body: str) -> dict:
    """Harness/api/resend_send_api.py를 그대로 호출한다(발송 로직 복제 금지)."""
    demo_to = (os.environ.get("DEMO_RECIPIENT") or "").strip()
    mail = extract_mail(body)

    if not demo_to:
        return {"mode": "resend", "file": file_rel, "status": "error",
                "reason": "DEMO_RECIPIENT 미설정 — 실제 기업으로 나가는 것을 막기 위해 발송하지 않음"}
    if not mail["subject"] or not mail["text"]:
        return {"mode": "resend", "file": file_rel, "status": "error",
                "reason": f"이 항목에서 일본어 제목·본문을 찾지 못함(company_id={company_id})"}

    payload = {
        "to": demo_to,
        "reply_to": demo_to,
        "subject": mail["subject"],
        "body": mail["text"],
    }
    try:
        proc = subprocess.run(
            [sys.executable, str(RESEND_SCRIPT)],
            input=json.dumps(payload, ensure_ascii=False),
            capture_output=True, text=True, encoding="utf-8", timeout=60,
        )
        result = json.loads((proc.stdout or "").strip() or "{}")
    except Exception as e:  # noqa: BLE001
        return {"mode": "resend", "file": file_rel, "status": "error", "reason": f"발송 스크립트 호출 실패: {e}"}

    return {
        "mode": "resend", "file": file_rel,
        "status": result.get("status", "error"),
        "reason": result.get("reason", ""),
        "message_id": result.get("message_id", ""),
        "to_actual": demo_to,
        "to_original": mail["to_original"],
        "subject": mail["subject"],
    }


def trigger_dispatch(file_rel: str, company_id: str = "", body: str = "") -> dict:
    """H12가 하던 것과 같은 후속 호출 — docs/35 4-2절."""
    mode = os.environ.get("DISPATCH_MODE", "mock")
    log_path = data_root() / "_dispatch.log"
    line = f"[{_now()}] dispatch mode={mode} file={file_rel} company={company_id or '?'}\n"
    result = {"mode": mode, "file": file_rel}

    if mode == "resend":
        result = _send_via_resend(file_rel, company_id, body)
        if result.get("status") == "sent":
            line += (f"  -> SENT(resend) to={result.get('to_actual')} "
                     f"(원래 수신자 {result.get('to_original') or '?'} 대신 데모 주소로 치환) "
                     f"message_id={result.get('message_id')}\n")
        else:
            line += f"  -> FAILED(resend): {result.get('reason')}\n"
    elif mode == "real":
        cmd = ["claude", "-p", f"/g5-제안메일제작발송 발송 {file_rel}"]
        try:
            subprocess.Popen(cmd, cwd=str(data_root().parent))
            line += f"  -> spawned: {' '.join(cmd)}\n"
        except Exception as e:  # noqa: BLE001
            line += f"  -> FAILED to spawn: {e}\n"
    else:
        line += f"  -> (mock) would call: /g5-제안메일제작발송 발송 {file_rel}\n"

    try:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(line)
    except Exception:  # noqa: BLE001
        pass

    return result
