"""승인 대기함 액션 (docs/35 4-2절, A안).
승인 버튼 클릭 시: ① 파일에 승인 기록을 쓴다 ② 발송 트리거를 같은 요청 안에서 호출한다.
DISPATCH_MODE=mock(기본, 테스트용) | real(claude -p 실제 호출)."""
import datetime
import os
import subprocess

from data_source import read_text, write_text, data_root


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
        dispatch_result = trigger_dispatch(file_rel)

    return {"ok": True, "dispatch": dispatch_result}


def trigger_dispatch(file_rel: str) -> dict:
    """H12가 하던 것과 같은 후속 호출 — docs/35 4-2절."""
    mode = os.environ.get("DISPATCH_MODE", "mock")
    log_path = data_root() / "_dispatch.log"
    line = f"[{_now()}] dispatch mode={mode} file={file_rel}\n"

    if mode == "real":
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

    return {"mode": mode, "file": file_rel}
