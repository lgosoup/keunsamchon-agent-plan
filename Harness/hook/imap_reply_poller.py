#!/usr/bin/env python3
"""H1(회신 도착 감지)의 **감지 층** 실제 구현 — IMAP으로 메일함을 열어 새 회신을 꺼낸다.

`hook_h01_reply_detected.sh`(더미)가 *"팀원이 만드는 발송 전용 메일함 감시
플랫폼의 일"*이라고 남겨 둔 그 자리다. 그 더미를 고치지 않고 **그 앞단**을
채운다 — 이 스크립트가 감지해서 h01 계약(stdin JSON)을 만들고, 그 뒤는
기존 경로가 그대로 받는다.

    [메일함]
       ↓ 이 스크립트(IMAP 폴링)          ← 지금까지 비어 있던 자리
    h01 계약 JSON
       ↓ hook_h01_reply_detected.sh 또는 --dispatch
    /g7-회신처리  (원문 보존·한국어 해석·8분류·번역 검증)
       ↓
    specs/replies/*.md → 웹 회신함(/replies)에 자동 표시

발송 API에서 dummy → resend로 갈아끼운 것과 같은 패턴이다. 도메인 인증이
필요한 Resend inbound 대신 IMAP을 쓰는 이유: 회신은 어차피 발신에 쓴 계정의
받은편지함으로 오므로, 도메인 없이 지금 동작한다(root `docs/91` 2026-08-13).

사용:
    python imap_reply_poller.py            # 감지·저장만 (기본, 안전)
    python imap_reply_poller.py --dispatch # 저장 + G7 실제 호출
    python imap_reply_poller.py --all      # 읽음 처리된 메일까지 다시 훑는다(재시연용)

설정(환경변수, .env — 값 자체는 이 파일에 쓰지 않는다):
    IMAP_USER    — 필수. 메일 계정(예: Gmail 주소)
    IMAP_PASS    — 필수. **앱 비밀번호**(Gmail 일반 비밀번호로는 IMAP이 안 된다)
    IMAP_HOST    — 선택, 기본 imap.gmail.com
    IMAP_PORT    — 선택, 기본 993 (SSL)
    IMAP_MAILBOX — 선택, 기본 INBOX
    G7_SKILL     — 선택, 기본 /g7-회신처리 (Harness 패키지에선 /g7-reply-processing)

IMAP_USER·IMAP_PASS 중 하나라도 없으면 **접속을 시도하지 않고** 종료한다 —
계정이 없는 환경에 연결해 둬도 무해하다(`resend_send_api.py`와 같은 세이프페일).
"""
import argparse
import datetime
import email
import email.header
import email.utils
import imaplib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
STAGING_DIR = REPO_ROOT / "specs" / "_수신함"
SENT_DIR = REPO_ROOT / "specs" / "발송기록"
REPLIES_DIR = REPO_ROOT / "specs" / "replies"


def _reply_record_exists(received_at: str) -> bool:
    """이 회신이 실제로 끝까지 처리됐는가 — G7 레코드 유무로만 판정한다.

    예전엔 "스테이징 파일이 있는가"로 판정했는데, 스테이징은 디스패치
    성공·실패와 무관하게 항상 먼저 생겨서, 디스패치가 중간에 실패해도
    스테이징 파일은 남아 **다음 회차부터 영원히 건너뛰어졌다**(2026-08-14,
    노트북 절전모드로 인한 API 연결 끊김이 실제로 이 상태를 만들었다).
    레코드 존재만이 "끝까지 됐다"는 진짜 증거다."""
    return any(REPLIES_DIR.glob(f"{received_at}-*.md"))


def _load_dotenv() -> None:
    """저장소 루트 .env에서 아직 설정되지 않은 값만 채운다. 값은 출력하지 않는다."""
    env_path = REPO_ROOT / ".env"
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
    return log_dir / "h01.log"


def _log(line: str) -> None:
    try:
        with open(_log_path(), "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass
    print(line)


def _decode_header(raw) -> str:
    """MIME 인코딩된 헤더를 사람이 읽는 문자열로. 일본어 제목은 대개 여기서 깨진다."""
    if not raw:
        return ""
    out = []
    for part, enc in email.header.decode_header(raw):
        if isinstance(part, bytes):
            out.append(part.decode(enc or "utf-8", errors="replace"))
        else:
            out.append(part)
    return "".join(out).strip()


def _plain_body(msg) -> str:
    """text/plain 본문을 뽑는다. 일본어 메일은 ISO-2022-JP인 경우가 흔하다."""
    candidates = []
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain" and not part.get_filename():
                candidates.append(part)
    elif msg.get_content_type() == "text/plain":
        candidates.append(msg)

    for part in candidates:
        payload = part.get_payload(decode=True)
        if not payload:
            continue
        charset = part.get_content_charset() or "utf-8"
        try:
            return payload.decode(charset, errors="replace").strip()
        except LookupError:
            return payload.decode("utf-8", errors="replace").strip()
    return ""


def _attachments(msg) -> list:
    names = []
    if msg.is_multipart():
        for part in msg.walk():
            fname = part.get_filename()
            if fname:
                names.append(_decode_header(fname))
    return names


def _normalize_subject(s: str) -> str:
    """Re:·Fwd: 접두어와 공백을 걷어내 발송 제목과 대조할 수 있게 만든다."""
    s = re.sub(r"^\s*(re|fwd|fw)\s*:\s*", "", s, flags=re.I)
    while re.match(r"^\s*(re|fwd|fw)\s*:\s*", s, flags=re.I):
        s = re.sub(r"^\s*(re|fwd|fw)\s*:\s*", "", s, flags=re.I)
    return re.sub(r"\s+", "", s).strip()


def _match_send_record(subject: str, sender: str) -> str:
    """어느 발송 건에 대한 회신인지 제목으로 대조한다.

    못 찾으면 빈 문자열을 돌려준다 — G7이 이미 쓰는 `-미확정` 관례로 이어진다
    (`specs/집계/2026-08-13.md` 0절이 그 경우를 세고 있다). 여기서 억지로
    기업을 추측하지 않는다."""
    if not SENT_DIR.is_dir():
        return ""
    target = _normalize_subject(subject)
    if not target:
        return ""
    for path in sorted(SENT_DIR.glob("*.md")):
        try:
            raw = path.read_text(encoding="utf-8")
        except OSError:
            continue
        m = re.search(r"###\s*제목\s*\n+([^\n]+)", raw) or re.search(r"\*\*제목\*\*[:：]?\s*([^\n]+)", raw)
        if m and _normalize_subject(m.group(1)) == target:
            return f"specs/발송기록/{path.name}"
    return ""


def _our_sent_subjects() -> set:
    """우리가 실제로 보낸 메일의 제목 집합(정규화).

    두 곳에서 모은다 — G5가 쓴 `specs/발송기록/`, 그리고 실제 발송 API가 남긴
    `Harness/data/hook로그/api-send.log`. 후자가 필요한 이유: 발송 스크립트를
    직접 호출한 건(시연·검증)은 발송기록 파일이 없어 앞의 것만으로는 자기 회신을
    못 알아본다."""
    subjects = set()

    if SENT_DIR.is_dir():
        for path in SENT_DIR.glob("*.md"):
            try:
                raw = path.read_text(encoding="utf-8")
            except OSError:
                continue
            m = re.search(r"###\s*제목\s*\n+([^\n]+)", raw) or re.search(r"\*\*제목\*\*[:：]?\s*([^\n]+)", raw)
            if m:
                subjects.add(_normalize_subject(m.group(1)))

    send_log = Path(__file__).resolve().parent.parent / "data" / "hook로그" / "api-send.log"
    if send_log.is_file():
        try:
            for line in send_log.read_text(encoding="utf-8").splitlines():
                m = re.search(r"subject=(.*?)\s+from=", line)
                if m:
                    subjects.add(_normalize_subject(m.group(1)))
        except OSError:
            pass

    subjects.discard("")
    return subjects


def _is_reply_to_us(msg, payload: dict, sent_subjects: set) -> str:
    """이 메일이 **우리가 보낸 메일에 대한 회신**인가. 아니면 빈 문자열.

    이 게이트가 없으면 받은편지함의 모든 안 읽은 메일을 무차별로 가져간다
    (2026-08-13 실제로 그렇게 동작해 개인 메일 80건을 건드렸다 — `docs/91`).
    판별은 두 축이고, 어느 하나라도 걸리면 회신으로 본다:
      ① 회신 헤더(In-Reply-To / References)가 존재한다 + 제목이 우리 발송 제목과 일치
      ② 헤더가 없어도 제목이 우리 발송 제목과 일치(웹메일이 헤더를 빠뜨리는 경우)
    제목 일치가 공통 필수 조건이다 — 그것 없이는 우리 것이라고 볼 근거가 없다."""
    norm = _normalize_subject(payload["subject"])
    if not norm or norm not in sent_subjects:
        return ""

    # 우리가 **보낸** 메일 자신은 회신이 아니다. 발신 주소가 받은편지함에도
    # 남는 구성(자기 계정으로 보내는 시연)에서 제목이 당연히 일치하므로
    # 그대로 두면 자기 발송분을 회신으로 잡는다(2026-08-13 실측).
    outbound = {
        (os.environ.get("RESEND_FROM_DEFAULT") or "").strip().lower(),
        "onboarding@resend.dev",
    }
    sender_addr = email.utils.parseaddr(payload["from"])[1].lower()
    if sender_addr and sender_addr in {a for a in outbound if a}:
        return ""

    if (msg.get("In-Reply-To") or "").strip() or (msg.get("References") or "").strip():
        return "회신 헤더 + 제목 일치"
    return "제목 일치(회신 헤더 없음)"


def _safe_name(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]", "-", s)[:60] or "unknown"


def _build_payload(msg) -> dict:
    """h01 계약(hook_h01_reply_detected.sh 기대 입력)을 그대로 만든다."""
    sender = _decode_header(msg.get("From"))
    subject = _decode_header(msg.get("Subject"))
    body = _plain_body(msg)

    received_at = ""
    date_hdr = msg.get("Date")
    if date_hdr:
        try:
            received_at = email.utils.parsedate_to_datetime(date_hdr).strftime("%Y-%m-%d-%H%M%S")
        except (TypeError, ValueError):
            received_at = ""
    if not received_at:
        received_at = datetime.datetime.now().strftime("%Y-%m-%d-%H%M%S")

    # G7은 원문 보존을 무관용 항목으로 요구한다 — 헤더를 본문 위에 붙여
    # "원문 1통"으로서 온전하게 넘긴다.
    mail_raw = (
        f"From: {sender}\n"
        f"Date: {date_hdr or ''}\n"
        f"Subject: {subject}\n"
        f"Message-ID: {msg.get('Message-ID', '')}\n"
        f"In-Reply-To: {msg.get('In-Reply-To', '')}\n"
        f"\n{body}"
    )

    # 시연 회신인가 — 발신자가 DEMO_RECIPIENT면 우리가 우리에게 보낸 것이다.
    # 실제 기업이 답한 것이 아니므로 데이터에 그 사실이 남아야 한다: 파일 목록만
    # 보면 진짜 회신처럼 읽히고, G11 반응 집계가 회신율을 부풀린다
    # (`specs/집계/2026-08-13.md`가 합성 데이터 경고를 굳이 반복하는 것과 같은 위험).
    demo_addr = (os.environ.get("DEMO_RECIPIENT") or "").strip().lower()
    sender_addr = email.utils.parseaddr(sender)[1].lower()
    is_demo = bool(demo_addr) and sender_addr == demo_addr

    return {
        "mail_raw": mail_raw,
        "from": sender,
        "received_at": received_at,
        "subject": subject,
        "thread_id": (msg.get("In-Reply-To") or msg.get("Message-ID") or "").strip(),
        "attachments": _attachments(msg),
        "matched_send_record": _match_send_record(subject, sender),
        "demo": is_demo,
    }


HEARTBEAT_PATH = REPO_ROOT / "specs" / "_watch.json"


def _write_heartbeat(args, last_result: str) -> None:
    """감시가 살아 있다는 신호를 남긴다.

    이게 없으면 웹은 "회신이 안 온 것"과 "감시가 죽은 것"을 구분하지 못한다 —
    사용자가 5분간 아무 반응 없는 화면을 보며 실패로 오해한 실제 사례가 있다
    (2026-08-13). 웹(`web/parsers.py:watch_status`)이 이 파일의 시각과 주기를
    비교해 살아 있는지 판정한다."""
    try:
        HEARTBEAT_PATH.parent.mkdir(parents=True, exist_ok=True)
        HEARTBEAT_PATH.write_text(json.dumps({
            "last_check": time.time(),
            "last_check_text": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "interval": args.interval if args.watch else 0,
            "watching": bool(args.watch),
            "dispatch": bool(args.dispatch),
            "mailbox": os.environ.get("IMAP_MAILBOX", "INBOX"),
            "last_result": last_result,
        }, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        pass


def _stage(payload: dict) -> Path:
    """감지 결과를 파일로 남긴다.

    `specs/replies/` 밑에 두지 않는다 — 거기는 G7이 만든 **완성 레코드**만
    있어야 하고, 웹 회신함(parsers.parse_replies)이 그 폴더를 통째로 읽기
    때문에 원시 캡처를 넣으면 해석·검증을 안 거친 것이 회신함에 섞인다."""
    STAGING_DIR.mkdir(parents=True, exist_ok=True)
    name = f"{payload['received_at']}-{_safe_name(payload['from'])}.json"
    path = STAGING_DIR / name
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _dispatch_g7(payload: dict) -> bool:
    """G7을 무인으로 호출하고, **레코드가 실제로 생긴 것을 확인한 뒤에만** 성공을 돌려준다.

    `--watch`로 돌 때 이 호출이 사람 승인을 요구하면 자동 연쇄가 거기서 멈춘다 —
    그래서 권한 모드를 붙인다. **발송 권한과는 무관하다**: G7은 회신을 읽고
    레코드를 쓸 뿐이고 발신 도구 권한이 없다(`specs/G7` 실행체 경계). 발송은
    여전히 사람 승인(U2)을 거치는 G5의 일이다.

    **2026-08-14 정정 — 예전엔 `Popen`으로 프로세스를 띄우기만 하면 성공으로
    쳤다.** 노트북 절전모드로 API 연결이 중간에 끊겨 G7이 미완료로 죽었는데도
    "성공"으로 보고돼 곧바로 읽음 처리됐고, 그 회신은 영원히 재시도되지 않았다
    (`_reply_record_exists`가 막던 재도전 경로 자체가 없었다). 지금은
    `subprocess.run`으로 **끝날 때까지 기다리고**, 그러고도 레코드 파일이
    실제로 생겼는지까지 확인한다 — exit code 0이 곧 "레코드가 생겼다"의
    보장은 아니기 때문이다(LLM 세션은 중간에 끊겨도 0으로 끝날 수 있다)."""
    skill = os.environ.get("G7_SKILL", "/g7-회신처리")
    args = payload["mail_raw"]
    if payload["matched_send_record"]:
        args += f"\n참조 발신 정보: {payload['matched_send_record']}"
    if payload.get("demo"):
        args += (
            "\n\n⚠ 시연 회신이다 — 실제 기업이 답한 것이 아니다."
            " 발송 시 수신자가 실제 주소 대신 시연 주소로 치환됐고, 회신도 그 시연 주소에서 왔다."
            " **레코드 파일명의 식별자에 `합성시연-` 접두어를 붙여라**"
            " (예: `합성시연-www-titivate-jp`) — 이 저장소는 합성 데이터를 `합성데모-*`처럼"
            " 식별자로 구분하는 관례가 있고, 표시가 없으면 파일 목록상 실제 회신과 구분되지 않아"
            " G11 반응 집계가 회신율을 부풀린다."
            " 같은 이유로 **수신 거부가 나와도 `발송금지.md`에는 실제 기업 주소를 올리지 말고**"
            " 시연 주소만 올리고 「시연」임을 근거 칸에 명시하라 — 시연 때문에 실제 발송이"
            " 영구히 막히면 안 된다."
        )
    # Windows에서 claude는 .CMD 셸 스크립트라 이름만으로는 Popen이 못 찾는다
    # (WinError 2). which로 실제 경로를 풀어 넘긴다 — 2026-08-13 실측.
    exe = shutil.which(os.environ.get("CLAUDE_BIN") or "claude")
    if not exe:
        _log("  -> FAILED to dispatch: claude CLI를 PATH에서 찾지 못했다(CLAUDE_BIN으로 경로 지정 가능)")
        return False
    cmd = [exe, "-p", f"{skill} {args}"]
    mode = os.environ.get("G7_PERMISSION_MODE", "acceptEdits")
    if mode:
        cmd[1:1] = ["--permission-mode", mode]
    # G7은 실측상 ~5분(재번역 1회까지 겹치면 더 걸린다) — 넉넉히 잡되 무한 대기는 안 한다.
    timeout = int(os.environ.get("G7_TIMEOUT", "900"))
    try:
        result = subprocess.run(
            cmd, cwd=str(REPO_ROOT), timeout=timeout,
            capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
    except subprocess.TimeoutExpired:
        _log(f"  -> FAILED: G7 처리 시간 초과({timeout}초) — 읽음 처리 보류, 재시도 대상으로 남긴다")
        return False
    except Exception as e:  # noqa: BLE001
        _log(f"  -> FAILED to dispatch: {e}")
        return False

    if _reply_record_exists(payload["received_at"]):
        return True

    tail = (result.stderr or result.stdout or "").strip()[-500:]
    _log(f"  -> FAILED: G7 프로세스는 끝났지만(exit={result.returncode}) 회신 레코드가 안 생겼다"
         f" — 읽음 처리 보류, 재시도 대상으로 남긴다. 마지막 출력: {tail}")
    return False


def _run_once(args) -> int:
    """1회 폴링. `--watch`는 이걸 주기적으로 부른다."""
    now = datetime.datetime.now().strftime("%Y-%m-%d-%H%M%S")

    user = (os.environ.get("IMAP_USER") or "").strip()
    # 구글은 앱 비밀번호를 보기 편하라고 4자리씩 띄워 보여주지만(`abcd efgh ...`)
    # 실제 값은 공백 없는 16자다. 화면에 보이는 대로 붙여넣는 것이 자연스러워
    # 여기서 걷어낸다 — 안 그러면 원인을 알기 어려운 인증 실패로만 나타난다.
    password = re.sub(r"\s+", "", os.environ.get("IMAP_PASS") or "")
    if not (user and password):
        _log(f"[{now}] BLOCKED h01-poller — IMAP 설정 없음(IMAP_USER/IMAP_PASS 필요), 접속 시도 안 함")
        return 1

    host = os.environ.get("IMAP_HOST", "imap.gmail.com")
    port = int(os.environ.get("IMAP_PORT", "993"))
    mailbox = os.environ.get("IMAP_MAILBOX", "INBOX")

    try:
        conn = imaplib.IMAP4_SSL(host, port)
        conn.login(user, password)
        conn.select(mailbox)
    except (imaplib.IMAP4.error, OSError) as e:
        _log(f"[{now}] FAILED h01-poller — IMAP 접속/로그인 실패: {e}")
        return 1

    try:
        since = (datetime.date.today() - datetime.timedelta(days=args.since_days)).strftime("%d-%b-%Y")
        parts = ["ALL" if args.all else "UNSEEN", "SINCE", since]
        criterion = "(" + " ".join(parts) + ")"
        typ, data = conn.search(None, criterion)
        if typ != "OK":
            _log(f"[{now}] FAILED h01-poller — 검색 실패: {typ}")
            return 1

        ids = data[0].split()
        sent_subjects = _our_sent_subjects()
        if not sent_subjects:
            _log(f"[{now}] ⚠ 우리가 보낸 제목을 하나도 못 찾았다 — 회신 판별 불가, 아무것도 처리하지 않는다")
            return 1

        processed = 0
        skipped = 0
        for num in ids:
            if processed >= args.max_items:
                _log(f"  -> STOP — 처리 상한 {args.max_items}건 도달(나머지는 다음 실행에서)")
                break

            # BODY.PEEK: 가져오는 것만으로 읽음 처리되지 않게 한다 —
            # 저장에 실패한 메일이 조용히 사라지면 회신 1건을 통째로 잃는다.
            typ, msg_data = conn.fetch(num, "(BODY.PEEK[])")
            if typ != "OK" or not msg_data or not msg_data[0]:
                continue

            msg = email.message_from_bytes(msg_data[0][1])
            payload = _build_payload(msg)
            if not payload["mail_raw"].strip():
                continue

            # ── 회신 게이트 ──────────────────────────────────────────────
            # 우리가 보낸 메일의 회신이 아니면 여기서 끝낸다. 저장하지도,
            # 읽음 표시를 하지도 않는다 — 남의 메일함을 건드리지 않는 것이
            # 이 스크립트가 지켜야 할 가장 중요한 경계다.
            why = _is_reply_to_us(msg, payload, sent_subjects)
            if not why:
                skipped += 1
                continue

            # 이미 **끝까지** 처리한 회신인가 — 레코드 존재로만 판정한다(스테이징
            # 파일 존재로 판정하면, 디스패치가 실패해도 스테이징은 이미 있어서
            # 다음 회차부터 영원히 건너뛰어진다 — 2026-08-14 실물로 겪은 문제).
            if _reply_record_exists(payload["received_at"]):
                skipped += 1
                continue

            staged = _stage(payload)
            _log(f"[{now}] MATCH ({why}) from={payload['from']}")
            _log(f"     subject={payload['subject']}")
            _log(f"     저장: {staged.relative_to(REPO_ROOT).as_posix()}")

            # --dispatch가 없으면(감지만 하는 기본 모드) 바로 읽음 처리해도 된다 —
            # 뒤에서 기다릴 처리 자체가 없다. --dispatch가 있으면 **레코드가 실제로
            # 생긴 것을 확인한 경우에만** 읽음 처리한다 — 그래야 중간에 끊겨도
            # 다음 감시 주기(또는 재실행)에 같은 메일이 다시 잡혀 자동 재시도된다.
            dispatched_ok = True
            if args.dispatch:
                _write_heartbeat(args, f"회신 처리 중 — {payload['from']} (최대 {os.environ.get('G7_TIMEOUT', '900')}초 대기)")
                dispatched_ok = _dispatch_g7(payload)
                if dispatched_ok:
                    _log("     DISPATCHED -> " + os.environ.get("G7_SKILL", "/g7-회신처리") + " (레코드 생성 확인됨)")
                else:
                    _log("     DISPATCH 실패 또는 레코드 미생성 — 읽음 처리 보류, 자동 재시도 대상으로 남음")

            if dispatched_ok and not args.keep_unread and not args.all:
                conn.store(num, "+FLAGS", "\\Seen")
            processed += 1

        if processed or not args.quiet:
            _log(f"[{now}] DONE h01-poller — {mailbox} {criterion}: 조회 {len(ids)}건, "
                 f"회신 {processed}건 처리, 회신 아님/기처리 {skipped}건 건너뜀")
        _write_heartbeat(args, f"조회 {len(ids)}건 · 새 회신 {processed}건")
        return 0
    finally:
        try:
            conn.close()
            conn.logout()
        except (imaplib.IMAP4.error, OSError):
            pass


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="IMAP으로 회신을 감지해 H1 계약으로 넘긴다")
    parser.add_argument("--dispatch", action="store_true", help="G7(/g7-회신처리)을 실제로 호출한다")
    parser.add_argument("--all", action="store_true", help="읽음 처리된 메일까지 다시 훑는다(재시연용)")
    parser.add_argument("--keep-unread", action="store_true", help="처리 후 읽음 표시를 하지 않는다")
    parser.add_argument("--since-days", type=int, default=14,
                        help="최근 N일 안에 온 메일만 본다(기본 14). 오래된 메일함을 통째로 훑지 않기 위한 안전장치")
    parser.add_argument("--max", type=int, default=20, dest="max_items",
                        help="한 번에 처리할 최대 건수(기본 20)")
    parser.add_argument("--watch", action="store_true",
                        help="주기적으로 계속 감시한다(H1 트리거 자리). 이게 있어야 회신 처리가 무인으로 돈다")
    parser.add_argument("--interval", type=int, default=60,
                        help="--watch 주기(초, 기본 60)")
    parser.add_argument("--quiet", action="store_true",
                        help="회신이 없는 회차는 로그를 남기지 않는다(--watch용)")
    args = parser.parse_args()

    _load_dotenv()

    if not args.watch:
        return _run_once(args)

    # ── H1 트리거 ────────────────────────────────────────────────────────
    # 이 루프가 없으면 감지는 되지만 **아무도 감지를 시작하지 않는다** —
    # 사람이 매번 손으로 돌려야 하고, 그건 이 프로젝트가 "승인 한 곳만
    # 사람"이라고 한 설계(브리프 요구 ③ 반자동, `docs/34` U2)와 어긋난다.
    _log(f"[WATCH] 회신 감시 시작 — {args.interval}초 간격"
         + (", G7 자동 호출 켜짐" if args.dispatch else ", 감지만(G7 호출 꺼짐: --dispatch 필요)"))
    try:
        while True:
            try:
                _run_once(args)
            except Exception as e:  # noqa: BLE001
                # 한 회차가 죽어도 감시는 계속돼야 한다 — 네트워크 순단으로
                # 트리거가 영구히 멎으면 회신이 조용히 쌓인다.
                _log(f"[WATCH] 이번 회차 실패(계속 감시): {e}")
            time.sleep(args.interval)
    except KeyboardInterrupt:
        _log("[WATCH] 감시 중단(사용자 종료)")
        return 0


if __name__ == "__main__":
    sys.exit(main())
