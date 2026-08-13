"""승인 대기함 액션 (docs/35 4-2절, A안).
승인 버튼 클릭 시: ① 파일에 승인 기록을 쓴다 ② 발송 트리거를 호출한다.

DISPATCH_MODE:
  mock  (기본, 테스트용) — 로그만 남긴다. 아무것도 나가지 않는다.
  real                   — `claude -p "/g5-... 발송"`을 백그라운드로 띄운다. 그
                           스킬은 `disallowed-tools: Bash`라 **실제 메일은 못
                           보낸다**(무관용 게이트를 통과한 건의 발송 기록 파일을
                           쓰는 데까지가 그 스킬의 일이다).
  resend                 — 위 `real`과 **같은 방식으로 스킬을 백그라운드 호출**하고
                           (2026-08-14 재구성 — 이전엔 이 웹 코드가 Resend를 직접
                           호출해 스킬의 무관용 게이트를 통째로 우회했다), 실제
                           발송은 별도 감시자(`web/resend_watcher.py`)가 스킬이
                           **다 통과해서 새로 쓴** `발송기록/`을 찾아 그때 처리한다.
                           그래서 이 함수의 응답은 "발송 완료"가 아니라 "처리 중"이다
                           — `Harness/api/README.md`가 정의한 "발송 기록이 새로
                           쓰인 것을 감지한 외부 시스템이 그 스크립트를 부른다"의
                           그 외부 시스템이 이 웹 요청 자신이 아니라 그 감시자다.

⚠ resend 실제 발송의 수신자 강제 치환:
  Resend 도메인 인증 전이라 수신자가 계정 소유자 본인으로 제한된다. 그래서
  `resend_watcher.py`는 발송기록의 실제 수신 주소(일본 기업)로 보내지 않고
  **환경변수 DEMO_RECIPIENT로 강제 치환**한다. DEMO_RECIPIENT가 없으면 발송하지
  않는다 — 시연 중 실수로 실제 기업에 나가는 경로를 코드 레벨에서 막는다.
"""
import datetime
import json
import os
import re
import subprocess
import sys
from pathlib import Path

from data_source import read_text, write_text, data_root
import parsers

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
    """발송대기 파일의 한 항목에서 표시·참고용으로 값을 뽑는다(승인 화면 쪽 용도).
    추출 규칙은 parsers.py 것을 그대로 쓴다 — 정본은 parsers.py 하나다."""
    jp_body_md = parsers.extract_jp_body_md(body)
    return {
        "subject": parsers.extract_subject(body),
        "text": _strip_quote(jp_body_md) if jp_body_md else "",
        "to_original": _first_match(r"\|\s*수신\s*주소\s*\|\s*([^\|\n]+)\|", body),
    }


def _first_match(pattern: str, body: str) -> str:
    m = re.search(pattern, body)
    return m.group(1).strip() if m else ""


RESEND_RESULT_MARKER = "## 실제 발송(Resend) 결과"


def already_resent(record_raw: str) -> bool:
    return RESEND_RESULT_MARKER in record_raw


def _legal_gate_reason(text: str, to_addr: str) -> str:
    """무관용 재확인 — `specs/G5_제안메일제작발송.md` 「성공 기준」과 같은 판정.

    `g5-제안메일제작발송` 발송 모드가 이미 이 확인을 마친 뒤에만 `발송기록/`을
    쓰므로(SKILL.md 모드 2 2번), 정상 경로에서는 이 함수가 걸릴 일이 없다.
    그래도 다시 확인하는 이유는 이 감시자가 스킬과 **다른 프로세스·다른 시점**에
    실행돼(비동기) 그 사이 `발송금지.md`가 갱신됐을 수 있기 때문이다 — 승인
    이후 등재 가능성은 스킬 자신의 절차(모드 2 2번 "승인 이후에 등재됐을 수
    있다")에도 이미 명시돼 있다."""
    if "(미확인)" in text:
        return "법정 표시(수신 거부 접수처·송신자 주소 등)가 (미확인)로 남아 있음 — 무관용 항목 미충족"
    forbidden = read_text("발송금지.md")
    if to_addr and forbidden and to_addr in forbidden:
        return f"수신 주소({to_addr})가 발송금지.md에 등재됨"
    return ""


def send_record_via_resend(record_rel: str) -> dict:
    """`발송기록/{기업식별자}-{발송일시}.md` 1건을 읽어 아직 실제 Resend 발송
    결과가 없으면 `Harness/api/resend_send_api.py`를 불러 실제로 보내고,
    결과를 그 파일에 이어 적는다(발송 로직 복제 금지 — 스크립트를 그대로 호출).

    `web/resend_watcher.py`(감시자)가 이 함수를 부른다. 스킬이 이미 무관용
    게이트를 통과시킨 뒤에만 존재하는 파일을 대상으로 하므로, 여기서 하는 일은
    "보낼지 판정"이 아니라 "이미 판정된 것을 실제로 보내기"다."""
    raw = read_text(record_rel)
    if not raw:
        return {"record": record_rel, "status": "error", "reason": "파일을 읽을 수 없음"}
    if already_resent(raw):
        return {"record": record_rel, "status": "skipped", "reason": "이미 실제 발송 처리됨"}

    company_id = parsers.send_record_field(raw, "기업\\s*식별자")
    to_original = parsers.send_record_field(raw, "수신\\s*주소")
    subject = parsers.send_record_field(raw, "제목")
    body_md = parsers.send_record_body_md(raw)
    text = _strip_quote(body_md) if body_md else ""

    demo_to = (os.environ.get("DEMO_RECIPIENT") or "").strip()
    result = {"record": record_rel, "company_id": company_id}

    if not demo_to:
        result.update(status="error", reason="DEMO_RECIPIENT 미설정 — 실제 기업으로 나가는 것을 막기 위해 발송하지 않음")
    elif gate_reason := _legal_gate_reason(raw, to_original):
        result.update(status="blocked", reason=gate_reason)
    elif not subject or not text:
        result.update(status="error", reason=f"발송기록에서 제목·본문을 찾지 못함(company_id={company_id})")
    else:
        payload = {"to": demo_to, "reply_to": demo_to, "subject": subject, "body": text}
        try:
            proc = subprocess.run(
                [sys.executable, str(RESEND_SCRIPT)],
                input=json.dumps(payload, ensure_ascii=False),
                capture_output=True, text=True, encoding="utf-8", timeout=60,
            )
            api_result = json.loads((proc.stdout or "").strip() or "{}")
            result.update(
                status=api_result.get("status", "error"),
                reason=api_result.get("reason", ""),
                message_id=api_result.get("message_id", ""),
                to_actual=demo_to, to_original=to_original,
            )
        except Exception as e:  # noqa: BLE001
            result.update(status="error", reason=f"발송 스크립트 호출 실패: {e}")

    stamp = (
        f"\n\n{RESEND_RESULT_MARKER}\n"
        f"- **처리일시**: {_now()}\n"
        f"- **상태**: {result.get('status')}\n"
        f"- **사유**: {result.get('reason') or '-'}\n"
        f"- **message_id**: {result.get('message_id') or '-'}\n"
        f"- **실제 수신(치환)**: {result.get('to_actual') or '-'}\n"
    )
    write_text(record_rel, raw.rstrip("\n") + stamp)
    return result


def dispatch_pending_resend_records() -> list:
    """`발송기록/` 중 아직 실제 Resend 결과가 없는 것 전부를 처리한다.
    `web/resend_watcher.py`(예약 실행 대상)의 본체 — 새 판정 로직 없이 이미
    있는 `send_record_via_resend` 하나를 순회 호출할 뿐이다."""
    from data_source import list_md_files
    out = []
    for rel in list_md_files("발송기록"):
        raw = read_text(rel)
        if already_resent(raw):
            continue
        out.append(send_record_via_resend(rel))
    return out


def send_status_for(company_id: str, file_rel: str) -> dict:
    """resend 비동기 발송의 지금 상태 — 승인 화면의 폴링용.
    processing(스킬이 아직 실행 중이거나, 실행돼 발송기록은 썼지만 이 감시자가
    아직 안 돌았음) / sent·blocked·error(감시자가 남긴 결과 그대로)."""
    from data_source import list_md_files
    for rel in list_md_files("발송기록"):
        raw = read_text(rel)
        if parsers.send_record_field(raw, "기업\\s*식별자") != company_id:
            continue
        if not already_resent(raw):
            return {"status": "processing", "reason": "스킬이 게이트를 통과해 발송 기록을 썼고, 실제 발송 대기 중"}
        m_status = re.search(r"\*\*상태\*\*:\s*(\S+)", raw)
        m_reason = re.search(r"\*\*사유\*\*:\s*(.+)", raw)
        return {
            "status": (m_status.group(1) if m_status else "unknown"),
            "reason": (m_reason.group(1).strip() if m_reason else ""),
        }
    # 발송기록이 아직 없다 — 스킬이 실행 중이거나, 무관용 게이트에 걸려
    # 발송대기 파일에만 사유를 남기고 발송기록은 안 썼을 수 있다.
    raw = read_text(file_rel)
    for item in parsers._split_approval_items(raw):
        if item["id"] == company_id and ("발송 불가" in item["body"] or "미확인" in item["body"]):
            return {"status": "blocked",
                     "reason": "스킬이 무관용 항목 미충족 등으로 발송 기록을 쓰지 않음 — 승인 화면에서 사유 확인"}
    return {"status": "processing", "reason": "스킬 실행 대기/진행 중"}


def trigger_dispatch(file_rel: str, company_id: str = "", body: str = "") -> dict:
    """H12가 하던 것과 같은 후속 호출 — docs/35 4-2절.

    `real`·`resend` 둘 다 스킬을 백그라운드로 던지기만 하고 기다리지 않는다
    (`docs/34` 7절 "정지점에서 대기하지 않고 종료" 원칙과 같다) — 실제 결과는
    `real`이면 사람이 `/sent`에서, `resend`면 `resend_watcher.py`가 처리한 뒤
    같은 화면에서 확인한다."""
    mode = os.environ.get("DISPATCH_MODE", "mock")
    log_path = data_root() / "_dispatch.log"
    line = f"[{_now()}] dispatch mode={mode} file={file_rel} company={company_id or '?'}\n"
    cmd = ["claude", "-p", f"/g5-제안메일제작발송 발송 {file_rel}"]

    if mode in ("resend", "real"):
        try:
            subprocess.Popen(cmd, cwd=str(data_root().parent))
            line += f"  -> spawned: {' '.join(cmd)}\n"
            result = {"mode": mode, "file": file_rel, "status": "processing",
                      "reason": "스킬이 게이트를 확인하는 중 — 잠시 후 발송 이력에서 확인"}
        except Exception as e:  # noqa: BLE001
            line += f"  -> FAILED to spawn: {e}\n"
            result = {"mode": mode, "file": file_rel, "status": "error", "reason": f"스킬 호출 실패: {e}"}
    else:
        line += f"  -> (mock) would call: /g5-제안메일제작발송 발송 {file_rel}\n"
        result = {"mode": mode, "file": file_rel, "status": "mock"}

    try:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(line)
    except Exception:  # noqa: BLE001
        pass

    return result
