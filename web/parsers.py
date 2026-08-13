"""각 산출물 파일에서 화면에 필요한 요약 필드만 뽑는다.
정확한 전체 내용은 항상 원문(raw)을 함께 돌려줘 상세 화면에서 렌더링한다 —
모든 뉘앙스를 스키마화하지 않는다(docs/35 6절 "가볍게 간다")."""
import re
from datetime import date, datetime
from markdown_it import MarkdownIt

from data_source import read_text, list_md_files, data_root, read_criteria, list_criteria_md_files

# commonmark 프리셋엔 표(GFM table)가 없다 — 원문 상세 화면에 표가 아주 많아(승인란 등)
# gfm-like로 켜되, linkify-it이 없어 linkify 규칙만 끈다.
_md = MarkdownIt("gfm-like", {"breaks": True, "html": False})
_md.disable("linkify")



def render_markdown(text: str) -> str:
    return _md.render(text)


def _strip_md(s: str) -> str:
    """표 칸 안의 굵게(**)·코드(`) 마크다운 기호만 제거 — 화면에 별표가 그대로 보이지 않게."""
    s = re.sub(r"\*\*([^*]*)\*\*", r"\1", s)
    s = re.sub(r"`([^`]*)`", r"\1", s)
    return s


def _table_rows(text: str):
    """`| a | b |` 형태의 마크다운 표 하나를 리스트[dict]로. 첫 표만 본다."""
    lines = [l for l in text.splitlines() if l.strip().startswith("|")]
    if len(lines) < 2:
        return []
    header = [_strip_md(c.strip()) for c in lines[0].strip("|").split("|")]
    rows = []
    for line in lines[2:]:
        cells = [_strip_md(c.strip()) for c in line.strip("|").split("|")]
        if len(cells) != len(header):
            continue
        rows.append(dict(zip(header, cells)))
    return rows


def _first(pattern, text, default=""):
    m = re.search(pattern, text)
    return m.group(1).strip() if m else default


# ---------- G1 후보 목록 ----------

def parse_candidates():
    raw = read_text("candidates/후보목록.md")
    sections = re.split(r"(?m)^## (?!.*목록)", raw)[1:]
    items = []
    for sec in sections:
        lines = sec.splitlines()
        # 헤딩이 "## {id}"뿐 아니라 "## {id} (2026-08-12 신규 실행)"처럼 주석이
        # 붙은 경우가 46건 중 43건이다(2026-08-13 실물 대조) — 뒤 " (" 이후를
        # 잘라야 진짜 식별자다. 안 자르면 contacts/segments와 id로 조인할 때
        # 대부분 매치가 안 된다(leadtime 계산이 3건만 잡히던 원인이 이것이었다).
        cid = lines[0].strip().split(" (")[0].strip()
        if not cid or cid.startswith("---"):
            continue
        verdict = _first(r"\*\*후보\s*판정:\s*([^*]+)\*\*", sec)
        if not verdict:
            continue  # "## 종합 — ..." 요약 섹션 등 실제 후보가 아닌 절 — 2026-08-13 발견
            # (실물 파일에 재판정 종합 섹션이 끼어 있어 총 조사 건수가 실제보다 2건 많게 셌었다)
        industry = _first(r"\*\*O5\*\*\s*업종:\s*\*\*([^*]+)\*\*", sec)
        items_count = _first(r"상품\s*개수:\s*([0-9?]+)", sec)
        channel_count = _first(r"판매채널\s*수:\s*([0-9?]+)", sec)
        collected_at = _first(r"수집일:\s*(\d{4}-\d{2}-\d{2})", sec)
        items.append({
            "id": cid, "업종": industry, "판정": verdict,
            "상품개수": items_count, "채널수": channel_count, "수집일": collected_at,
        })
    return items


def parse_holdlist():
    raw = read_text("candidates/보류목록.md")
    return _table_rows(raw)


# ---------- G2 세그먼트 ----------

def parse_segments():
    files = list_md_files("segments")
    out = []
    for rel in files:
        raw = read_text(rel)
        title = _first(r"^#\s*([^\n]+)", raw)
        is_trial = "확정 사용" not in raw and ("시험 실행" in raw)
        m = re.search(r"## 1절 무리 정의\n(.*?)\n##", raw, re.S)
        definitions = _table_rows(m.group(1)) if m else []
        m2 = re.search(r"## 2절 배정\n(.*?)(?:\n## |\Z)", raw, re.S)
        assignments = _table_rows(m2.group(1)) if m2 else []
        m3 = re.search(r"## 3절 미분류\n(.*?)(?:\n## |\Z)", raw, re.S)
        unassigned = _table_rows(m3.group(1)) if m3 else []
        out.append({
            "file": rel, "title": title, "is_trial": is_trial,
            "definitions": definitions, "assignments": assignments,
            "unassigned": unassigned,
        })
    return out


# ---------- G4 연락처 ----------

def parse_contacts():
    """세 필드 모두 두 표기 관례를 다 받는다 — `web/test-fixtures`(초기 관례: "# {id} — ...",
    볼드 상태·표 형식)와 `g4-연락처확보` 실제 산출(2026-08-13 실물 22건 대조로 드러남: "# 연락처
    확보 — {id}", 볼드 없는 상태, 목록 형식 등급·값)이 서로 달라 기존 정규식은 실물 22건 중
    20건에서 id·등급·연락처값을 전부 놓치고 있었다(`_split_approval_items`·`parse_aggregation`이
    이미 같은 이유로 두 관례를 다 받고 있는 것과 같은 패턴)."""
    files = list_md_files("contacts")
    out = []
    for rel in files:
        raw = read_text(rel)
        # 파일명·헤딩을 쪼개 추측하지 않는다 — 본문의 「기업 식별자」로 조인한다
        # (`_sent_company_ids`와 같은 원칙). 헤딩 관례가 "# {id} — ..."/"# ... — {id}"로
        # 갈려 헤딩 파싱으로는 어느 쪽이든 절반은 틀린다.
        cid = _first(r"\*\*기업\s*식별자\*\*[:：]\s*([^\n]+)", raw).strip()
        status = _first(r"##\s*상태:\s*\**\[([^\]]+)\]\**", raw, "미상")
        value = (
            _first(r"\*\*연락처\s*값\*\*\s*\|\s*`([^`]+)`", raw)  # 표 형식(초기 관례)
            or _first(r"\*\*연락처\s*값\*\*[:：]\s*([^\n]+)", raw)  # 목록 형식(실제 산출)
        )
        value = _strip_md(value).strip()
        grade_line = (
            _first(r"\*\*유효\s*등급\*\*[:：]\s*([^\n]+)", raw)  # 목록 형식(실제 산출) — 먼저 시도
            or _first(r"\*\*유효\s*등급\*\*\s*\|\s*([^\|]+)\|", raw)  # 표 형식(초기 관례)
        )
        grade = _strip_md(grade_line).split("—")[0].strip()
        out.append({"id": cid, "file": rel, "상태": status, "연락처값": value, "등급": grade})
    return out


# ---------- G5 승인 대기함 ----------

_APPROVAL_HEADER_RE = re.compile(r"(?m)^##\s*(?:\d+절\s*승인\s*대기\s*건.*|건\s*\d+\s*—.*)$")


def _split_approval_items(raw: str):
    """발송대기 파일을 회사(항목) 단위로 쪼갠다.

    표기 관례가 둘 있다 — '## N절 승인 대기 건 — #N id'(초기 관례, `web/test-fixtures`)와
    '## 건 N — id (역할)'(실제 g5-제안메일제작발송 스킬이 실제로 내는 표기, 2026-08-12
    실물 파일에서 파서가 0건을 잡는 것으로 이 불일치가 드러났다). 둘 다 받는다."""
    parts = _APPROVAL_HEADER_RE.split(raw)
    headers = _APPROVAL_HEADER_RE.findall(raw)
    items = []
    for h, body in zip(headers, parts[1:]):
        cid = _first(r"#\d+\s+(\S+)", h) or _first(r"건\s*\d+\s*—\s*(\S+)", h)
        items.append({"header": h, "body": body, "id": cid})
    return items


def _extract_blockquote_after(label_pattern: str, body: str) -> str:
    """`**라벨**` 다음에 오는 `>`로 시작하는 인용구 블록 전체를 뽑아 렌더링용 마크다운으로 돌려준다.
    승인 화면에 실제 메일 본문이 인라인돼 있어야 사람이 내용을 보고 판단할 수 있다(2026-08-12
    — 참조 링크만 있고 본문이 안 보이던 실물 문제를 사용자가 지적해 추가).

    라벨과 인용구 사이에 다른 줄(예: "일본어 제목: ..." 한 줄)이 끼어 있어도 찾는다
    (2026-08-14 — 실제 S2 배치에서 대표 문안이 라벨 바로 다음 줄에 제목을 얹어 놓아
    옛 "라벨 다음 줄이 바로 인용구여야 한다" 가정이 9건 중 1건에서 깨진 것을 실물로 확인)."""
    m = re.search(label_pattern + r"[\s\S]*?\n((?:>.*(?:\n|$))+)", body)
    return m.group(1).strip() if m else ""


# 일본어 본문/문안 라벨 — "본문"과 "문안"이 실제로 혼용되고(2026-08-14 실물 확인),
# 라벨 뒤에 "— N회차 (...)" 처럼 `**` 안쪽에 붙는 꼬리나 "(전문 원본: ...)" 처럼
# `**` 바깥쪽에 붙는 꼬리가 둘 다 나타난다 — 어느 쪽이든 라벨 자체(핵심 두 글자)만
# 확인하고 나머지는 [^\n*]*(안쪽 꼬리)·[^\n]*(바깥쪽 꼬리)로 흡수한다.
_JP_BODY_LABEL = r"\*\*일본어\s*(?:본문|문안)[^\n*]*\*\*[^\n]*"
_KR_INTENT_LABEL = r"\*\*한국어\s*발신\s*의도\s*전문[^\n*]*\*\*[^\n]*"


def extract_jp_body_md(body: str) -> str:
    return _extract_blockquote_after(_JP_BODY_LABEL, body) or _extract_blockquote_after(r"###\s*일본어\s*본문", body)


def extract_kr_intent_md(body: str) -> str:
    return _extract_blockquote_after(_KR_INTENT_LABEL, body) or _extract_blockquote_after(r"###\s*한국어\s*발신\s*의도\s*전문", body)


def extract_subject(body: str) -> str:
    return (
        _first(r"###\s*일본어\s*제목\s*\n+件名[:：]\s*([^\n]+)", body)
        or _first(r"###\s*제목\s*\n+([^\n]+)", body)
        or _first(r"\*\*일본어\s*제목\*\*[:：]?\s*([^\n]+)", body)
        # 라벨이 볼드·헤딩 없이 평문 한 줄("일본어 제목: ...")로만 있는 경우
        # (2026-08-14 S2 배치 실물 확인) — 줄 시작을 요구하지 않는다.
        or _first(r"일본어\s*제목[:：]\s*([^\n]+)", body)
        or _first(r"(?:^|\n)제목:\s*([^\n]+)", body)
    )


def _sent_company_ids():
    """이미 발송 기록이 있는 기업 식별자 집합 — 승인 대기함에서 뺄 대상 판별용(2026-08-12 추가).
    파일명이 아니라 본문의 「기업 식별자」 항목으로 조인한다(G12 스킬과 같은 원칙 — 파일명을 쪼개 추측하지 않는다).

    2026-08-14 — 실제 `g5-제안메일제작발송` 발송 모드를 처음 실행해 보니 이
    필드가 표 형식(`| 기업 식별자 | ... |`)으로 나와, 목록형만 보던 옛 정규식이
    실제 발송 기록에서는 전부 매치 실패하고 있었다(합성 데모 7건만 목록형이라
    우연히 통과했었다). 매치 실패가 조용히 "그 기업은 발송 이력 없음"으로
    읽혀 **중복 발송 방지 게이트가 실제 산출물에서는 작동하지 않는** 상태였다
    — `send_record_field`로 두 표기 다 받게 고쳤다."""
    ids = set()
    for rel in list_md_files("발송기록"):
        raw = read_text(rel)
        cid = send_record_field(raw, "기업\\s*식별자")
        if cid:
            ids.add(cid)
    return ids


def parse_approvals():
    files = list_md_files("발송대기", exclude_dirs=("_검증입력",))
    sent_ids = _sent_company_ids()
    out = []
    for rel in files:
        raw = read_text(rel)
        for item in _split_approval_items(raw):
            if item["id"] in sent_ids:
                continue  # 이미 발송 완료 — 승인 대기함에는 더 이상 표시하지 않는다(/sent에서 확인)
            body = item["body"]
            subject = extract_subject(body)
            jp_body_md = extract_jp_body_md(body)
            kr_intent_md = extract_kr_intent_md(body)
            decision = _first(r"\|\s*승인\s*/\s*거부\s*\|\s*([^\|]*)\|", body).strip()
            approver = _first(r"\|\s*승인자\s*\|\s*([^\|]*)\|", body).strip()
            approved_at = _first(r"\|\s*승인일시\s*\|\s*([^\|]*)\|", body).strip()
            out.append({
                "file": rel, "company_id": item["id"], "제목": subject,
                "일본어본문_html": render_markdown(jp_body_md) if jp_body_md else "",
                "한국어원안_html": render_markdown(kr_intent_md) if kr_intent_md else "",
                "결정": decision or "미승인", "승인자": approver, "승인일시": approved_at,
                "blocked": "발송되지 않는다" in body or "미확인" in body,
            })
    return out


# ---------- G5 발송기록 + G6 상태 ----------

def send_record_field(raw: str, label: str) -> str:
    """발송기록 한 필드를 두 표기 관례로 뽑는다 — 목록형("- **라벨**: 값",
    G11 시연용 합성 입력이 손으로 쓴 관례)과 표형("| 라벨 | 값 |", 실제
    `g5-제안메일제작발송` 발송 모드가 실제로 내는 관례, 2026-08-14 실물
    실행으로 처음 확인됐다 — 헤딩도 "# {id} — 발송 기록"으로 id가 헤딩
    **뒤쪽**에 와, id를 헤딩에서 뽑던 옛 방식(`^#\\s*([^\\s—]+)`)이
    "발송"이라는 글자를 id로 잘못 뽑고 있었다). 둘 다 받는다."""
    return (
        _first(rf"\*\*{label}\*\*[:：]?\s*([^\n]+)", raw)  # 목록형
        or _first(rf"\|\s*{label}\s*\|\s*([^\|\n]+)\|", raw)  # 표형(실제 산출)
    ).strip()


def send_record_body_md(raw: str) -> str:
    """발송기록의 본문 인용구 — 실제 산출은 `**본문**`(일본어 접두어 없음) 뒤
    바로 인용구가 온다(2026-08-14 실물 확인). 옛 헤딩형(`### 본문`)도 받는다."""
    return _extract_blockquote_after(r"\*\*본문\*\*[^\n]*", raw) or _extract_blockquote_after(r"###\s*본문", raw)


def parse_sent():
    files = list_md_files("발송기록")
    status_files = {}
    for rel in list_md_files("상태"):
        raw = read_text(rel)
        cid = send_record_field(raw, "기업\\s*식별자") or _first(r"^#\s*([^\s—]+)", raw)
        status = _first(r"##\s*상태:\s*\*\*\[([^\]]+)\]\*\*", raw, "대기중")
        status_files[cid] = status
    out = []
    for rel in files:
        raw = read_text(rel)
        cid = send_record_field(raw, "기업\\s*식별자")
        to_addr = send_record_field(raw, "수신\\s*주소")
        sent_at = send_record_field(raw, "발송일시")
        subject = send_record_field(raw, "제목") or _first(r"###\s*제목\s*\n+([^\n]+)", raw)
        out.append({
            "id": cid, "file": rel, "수신주소": to_addr, "발송일시": sent_at,
            "제목": subject, "상태": status_files.get(cid, "대기중"),
        })
    return out


# ---------- G7 회신함 ----------

_REPLY_FILENAME_RE = re.compile(r"^\d{4}-\d{2}-\d{2}-\d{6}-(.+)\.md$")


def parse_replies():
    """실물 회신 5건을 보면 표기가 두 갈래다 — 목록형("- **수신일시**: ...", G11
    합성 데모용)과 표+헤딩형("| 수신일시 | ... |" + "### 회신 성격\n**C1 — ...**",
    실제 발송·회신 흐름으로 만들어진 시연건). 둘 다 받는다(2026-08-13 실물 대조).
    기업 식별자는 본문에 전용 필드가 없어 **레코드 파일명 규칙**({수신일시}-{식별자}.md,
    Spec 정본)으로 뽑는다 — 헤딩 관례도 두 갈래(id 먼저/나중)라 헤딩 파싱은 못 믿는다."""
    # G7은 번역 검증용 추출본을 `replies/_검증입력/`에도 남긴다(감사 기록).
    # 그건 완성 레코드가 아니라 중간 산출물이라 회신함에 섞이면 안 된다 —
    # 발송대기에서 `_검증입력`을 빼는 것과 같은 이유(2026-08-13).
    files = list_md_files("replies", exclude_dirs=("_검증입력",))
    out = []
    for rel in files:
        raw = read_text(rel)
        title = _first(r"^#\s*([^\n]+)", raw)
        fname = rel.rsplit("/", 1)[-1]
        m = _REPLY_FILENAME_RE.match(fname)
        cid = m.group(1) if m else ""
        received_at = (
            _first(r"\*\*수신일시\*\*:\s*(\S+)", raw)  # 목록형
            or _first(r"\|\s*수신일시\s*\|\s*(\S+?)\s*\|", raw)  # 표형
        )
        category = (
            _first(r"\*\*회신\s*성격\*\*:\s*\*\*([^*]+)\*\*", raw)  # 목록형
            or _first(r"###\s*회신\s*성격\s*\n+\*\*([^*\n]+)\*\*", raw)  # 표+헤딩형
        )
        summary = _first(r"\*\*요지\*\*:\s*([^\n]+)", raw)  # 목록형
        if not summary:
            m = re.search(r"###\s*요지[^\n]*\n((?:\d+\.\s*[^\n]+\n?)+)", raw)  # 표+헤딩형(번호 목록)
            if m:
                summary = " ".join(re.findall(r"\d+\.\s*([^\n]+)", m.group(1)))
        ask = _first(r"\*\*상대의 요구·기한\*\*:\s*([^\n]+)", raw)
        out.append({
            "file": rel, "id": cid, "title": title, "수신일시": received_at,
            "분류": category.strip(), "요지": summary, "요구": ask,
            "synthetic": "합성" in cid or "합성" in fname,
        })
    return out


# ---------- 회신 자동 감시 상태 (H1 폴러) ----------

def watch_status():
    """회신 감시 루프가 살아 있는가 — `Harness/hook/imap_reply_poller.py`의 하트비트.

    "회신이 안 온 것"과 "감시가 죽은 것"은 화면에서 같아 보인다. 그 둘을 구분
    못 해 사용자가 정상 동작을 실패로 오해한 적이 있어(2026-08-13) 상태를
    명시한다."""
    import json
    import time
    raw = read_text("_watch.json")
    if not raw:
        return {"active": False}
    try:
        data = json.loads(raw)
    except ValueError:
        return {"active": False}

    interval = data.get("interval") or 60
    age = time.time() - (data.get("last_check") or 0)
    # 한 주기를 놓치는 건 흔하다(네트워크 순단). 두 주기를 넘기면 죽은 것으로 본다.
    alive = age < max(interval * 2 + 30, 150)
    return {
        "active": True,
        "alive": alive,
        "watching": data.get("watching", False),
        "dispatch": data.get("dispatch", False),
        "last_check_text": data.get("last_check_text", "?"),
        "interval": interval,
        "age_sec": int(age),
        "last_result": data.get("last_result", ""),
    }


def pending_replies():
    """캡처는 됐지만 아직 G7 레코드가 안 만들어진 회신 — "해석 중" 표시용.

    상관 규칙: 스테이징 파일명의 `{수신일시}`로 시작하는 레코드가
    `replies/`에 있으면 처리 완료로 본다(Spec의 레코드 파일명 규칙
    `{수신일시}-{식별자}.md`가 그 대응을 보장한다)."""
    import json
    base = data_root() / "_수신함"
    if not base.is_dir():
        return []

    done_prefixes = set()
    for rel in list_md_files("replies", exclude_dirs=("_검증입력",)):
        name = rel.rsplit("/", 1)[-1]
        done_prefixes.add(name[:17])  # YYYY-MM-DD-HHMMSS 길이

    out = []
    for p in sorted(base.glob("*.json")):
        if p.name.startswith("_"):
            continue  # _watch.json 등 상태 파일
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        received = d.get("received_at", "")
        if received and received[:17] in done_prefixes:
            continue  # 레코드가 이미 나왔다
        out.append({
            "received_at": received,
            "from": d.get("from", ""),
            "subject": d.get("subject", ""),
            "file": f"_수신함/{p.name}",
        })
    return sorted(out, key=lambda x: x["received_at"], reverse=True)


# ---------- G3 순위표(부가) ----------

def parse_scores():
    files = list_md_files("scores")
    ranking_file = next((f for f in files if "순위표" in f), None)
    rows = []
    if ranking_file:
        raw = read_text(ranking_file)
        m = re.search(r"(순위[\s\S]*)", raw)
        rows = _table_rows(m.group(1)) if m else []
    individual = [f for f in files if "순위표" not in f]
    return {"ranking": rows, "individual_files": individual}


# ---------- 부가 큐: G8/G9/G10 ----------

def parse_queue():
    causes = []
    for rel in list_md_files("원인분석"):
        raw = read_text(rel)
        cid = _first(r"^#\s*([^\s—]+)", raw)
        hypothesis = _first(r"##\s*원인\s*가설\s*\n+\*\*([^*]+)\*\*", raw)
        retry = _first(r"##\s*재시도\s*가치\s*\n+\*\*([^*]+)\*\*", raw)
        causes.append({"id": cid, "file": rel, "가설": hypothesis, "재시도가치": retry})

    briefs = []
    for rel in list_md_files("위임브리프"):
        raw = read_text(rel)
        cid = _first(r"^#\s*([^\s—]+)", raw)
        route = _first(r"\*\*유입\s*경로\*\*:\s*([^\n]+)", raw)
        briefs.append({"id": cid, "file": rel, "유입경로": route})

    recollections = []
    for rel in list_md_files("재수집대상"):
        raw = read_text(rel)
        cid = _first(r"^#\s*([^\s—]+)", raw)
        source = _first(r"\*\*유입\s*소스\*\*:\s*\*\*([^*]+)\*\*", raw)
        recollections.append({"id": cid, "file": rel, "유입소스": source})

    return {"원인분석": causes, "위임브리프": briefs, "재수집대상": recollections}


# ---------- G11 집계(부가) ----------

def parse_aggregation():
    files = list_md_files("집계")
    out = []
    for rel in files:
        raw = read_text(rel)
        # 두 표기 관례를 다 받는다 — parsers.py의 _APPROVAL_HEADER_RE와 동일한 이유:
        # web/test-fixtures(옛 관례) "## 1절 ..."과 실제 g11-반응집계 스킬이 내는
        # "## 1. ..."(아라비아 숫자 + 마침표) 표기가 서로 달라 실물 파일에서 파서가
        # 0건을 잡는 것으로 이 불일치가 드러났다(2026-08-13).
        m = re.search(r"## (?:1절|1\.)[\s\S]*?\n(.*?)(?:\n## |\Z)", raw, re.S)
        table = _table_rows(m.group(1)) if m else []
        m2 = re.search(r"## (?:2절|2\.)[\s\S]*?\n(.*?)(?:\n## |\Z)", raw, re.S)
        proposals = m2.group(1).strip() if m2 else ""
        out.append({"file": rel, "table": table, "proposals": proposals})
    return out


# ---------- G12 질의응답로그 — H9(기준 정합성 검토) 자동 검토 구분 (2026-08-14 신설) ----------
# docs/35 6절 설계: H9가 만드는 질문은 hook_h9_criteria_review.sh가 조립하는 고정 템플릿
# ("{파일명}의 내용이 다음과 같이 바뀌었다. ... 이 변경이 다른 기준·스펙과 충돌하는지
# 검토해줘.")이라 그 시작·끝 문구로 판별한다 — 로그 형식에 새 출처 필드를 추가하지 않는다.
_H9_QUESTION_RE = re.compile(
    r"의\s*내용이\s*다음과\s*같이\s*바뀌었다\..*이\s*변경이\s*다른\s*기준[·\-]스펙과\s*충돌하는지\s*검토해줘\.?",
    re.S,
)


def qna_question(raw: str) -> str:
    """목록형("- **질문 원문**: ...", 한 줄)과 헤딩+인용구형("## 질문 원문\n> ...",
    여러 줄 인용구) 둘 다 받는다 — 실물 로그 6건 대조 결과 H9 기원 로그 중 하나가
    후자 형식이었다(2026-08-14, `specs/질의응답로그/2026-08-11-150000-2.md`)."""
    one_line = _first(r"\*\*질문\s*원문\*\*[:：]\s*([^\n]+)", raw)
    if one_line:
        return one_line
    m = re.search(r"##\s*질문\s*원문\s*\n+((?:>.*(?:\n|$))+)", raw)
    if not m:
        return ""
    return "\n".join(line.lstrip(">").strip() for line in m.group(1).splitlines())


def is_h9_origin(raw: str) -> bool:
    return bool(_H9_QUESTION_RE.search(qna_question(raw)))


def h9_target_file(raw: str) -> str:
    """H9 질문이 어느 `기준/*.md` 파일을 대상으로 했는지 — 템플릿이 항상
    "{파일명}의 내용이 다음과 같이 바뀌었다"로 시작하므로 그 파일명만 뽑는다.
    질문이 코드 서식(`` `G2_...` ``)으로 감싸져 있는 실물 사례가 있어 백틱도 벗긴다."""
    q = qna_question(raw)
    m = re.search(r"`?([\w가-힣]+\.md)`?의\s*내용이\s*다음과\s*같이\s*바뀌었다", q)
    return m.group(1) if m else ""


def qna_answer_preview(raw: str, length: int = 180) -> str:
    """`## 답변` 절 본문을 마크다운 기호 없이 앞부분만 — 기준 카드 화면의
    "간결한 검토 칸"용(도 35 6-2절). 전체 내용은 여전히 로그 원문(상세 화면)에 있다."""
    m = re.search(r"##\s*답변\s*\n+([\s\S]*?)(?:\n##\s|\Z)", raw)
    body = m.group(1) if m else ""
    text = re.sub(r"[*`_>#]", "", body)
    text = re.sub(r"\s+", " ", text).strip()
    return (text[: length].rstrip() + "…") if len(text) > length else text


def latest_h9_review_by_file():
    """기준 파일명 → 그 파일을 대상으로 한 가장 최근 H9 로그 요약.
    로그 파일명이 `{일시}.md`(초 단위, 사전순=시간순)라 정렬로 최신을 가른다."""
    out = {}
    for rel in list_md_files("질의응답로그"):
        raw = read_text(rel)
        if not is_h9_origin(raw):
            continue
        target = h9_target_file(raw)
        if not target:
            continue
        prior = out.get(target)
        if prior and prior["file"] >= rel:
            continue
        out[target] = {"file": rel, "preview": qna_answer_preview(raw)}
    return out


# ---------- 기준 카드 (2026-08-14 신설, docs/35 6절 — H9 자동 검토) ----------

def _criteria_g_badge(name: str) -> str:
    """파일명에서 G번호만 뽑는다 — `G4_연락처유효성기준.md` → `G4`,
    `판정시트_G1.md`처럼 접두어가 아니어도 찾는다. 다른 화면들이 전부
    `<span class="badge">G4</span>` 식으로 기능 번호를 눈에 띄게 붙이는데
    이 화면만 제목 텍스트 안에 섞여 있었다(2026-08-14 사용자 지적)."""
    m = re.match(r"(G\d+)_", name) or re.search(r"(G\d+)", name)
    return m.group(1) if m else ""


def parse_criteria_cards():
    """`html`(카드 본문 전체 렌더링)을 포함한다 — 2026-08-14 추가.
    사용자가 "뭐가 있는지 알아야 뭘 수정할지 안다"고 지적: 검토 결과만 보여주고
    정작 지금 카드에 뭐가 적혀 있는지는 안 보였다. 접었다 펼 수 있게(`<details>`)
    보여준다 — 승인 화면의 "한국어 원안 보기"(`kr-intent`)와 같은 기존 패턴 재사용."""
    reviews = latest_h9_review_by_file()
    out = []
    for name in list_criteria_md_files():
        raw = read_criteria(name)
        title = _first(r"^#\s*([^\n]+)", raw) or name
        out.append({
            "name": name, "title": title, "review": reviews.get(name),
            "html": render_markdown(raw), "g_badge": _criteria_g_badge(name),
        })
    return out


# ---------- 개요(홈) 성과 지표 (2026-08-13 신설) ----------

def _pct(n, denom):
    return round(n / denom * 100) if denom else 0


def pipeline_stats():
    """"할 일"이 아니라 "지금까지 파이프라인이 실제로 만든 것" — 브리프 3대 요구(탐색·
    목록화 / 맞춤 메일 / 반자동 발송, `CLAUDE.md` 2절 ①)가 홈 화면에서 눈에 띄게
    보이도록 `docs/35` 2절에 추가된 화면 0 하단 섹션의 데이터다. 새 계산·새 산출물이
    아니다 — 다른 화면이 이미 세는 값을 그대로 재사용한다(`33` D20)."""
    candidates = parse_candidates()
    g1_verdict = {"포함": 0, "판정 불가": 0, "제외": 0}
    for c in candidates:
        v = c["판정"].strip()
        if v in g1_verdict:
            g1_verdict[v] += 1
    g1_total = len(candidates)

    segs = parse_segments()
    seg_count = sum(len(s["definitions"]) for s in segs)
    assigned = sum(len(s["assignments"]) for s in segs)
    unassigned = sum(len(s["unassigned"]) for s in segs)

    contacts = parse_contacts()
    g4_total = len(contacts)
    g4_status = {"확보": 0, "메일 없음": 0, "발송 금지": 0, "미확보": 0}
    for c in contacts:
        s = c["상태"].strip()
        if s in g4_status:
            g4_status[s] += 1
    grade = {"직통": 0, "일반": 0}
    for c in contacts:
        gd = c["등급"].strip()
        if gd in grade:
            grade[gd] += 1
    secured = g4_status["확보"]

    approvals = parse_approvals()
    pending = sum(1 for a in approvals if a["결정"] not in ("승인", "거부"))
    approved = sum(1 for a in approvals if a["결정"] == "승인")
    rejected = sum(1 for a in approvals if a["결정"] == "거부")
    sent_count = len(parse_sent())

    return {
        "g1": {"total": g1_total, **g1_verdict},
        "g2": {"segments": seg_count, "assigned": assigned, "unassigned": unassigned},
        "g4": {"total": g4_total, "secured": secured, "secure_rate": _pct(secured, g4_total),
                "grade": grade, **g4_status},
        "g5": {"pending": pending, "approved": approved, "rejected": rejected, "sent": sent_count},
    }


# ---------- 성과 시각화 5종 (2026-08-13 신설, "파이프라인 현황" 대체) ----------
# 사용자 지시로 퍼널 막대를 걷어내고, 이 5개(추이·리드타임·업종 분포·연락처
# 교차·회신 관련)로 바꿨다. 전부 실측 파일에서 뽑고, 회신 관련 2개만 현재
# 표본이 합성/시연뿐이라 화면에서 그 사실을 같이 표시한다(숨기지 않는다).

# dataviz 스킬 palette.md의 검증된 8슬롯 중 all-pairs 안전한 앞 3슬롯을 추이에,
# 뒤에서 3슬롯 + 무채색 1을 업종에 썼다(같은 화면에 떠도 두 차트가 헷갈리지 않게
# 계열을 분리) — 실제 색상값은 `web/static/css/style.css` :root 토큰(--cat-*)에
# 있고, 여기서는 클래스명만 낸다.
_CAT_TREND = ["cat-trend-1", "cat-trend-2", "cat-trend-3"]
_CAT_INDUSTRY = ["cat-ind-1", "cat-ind-2", "cat-ind-3", "cat-ind-4"]


def _date_only(s):
    m = re.match(r"(\d{4}-\d{2}-\d{2})", s or "")
    return m.group(1) if m else None


def daily_trend():
    """일별 처리량 추이 — G1 판정 통과·G4 연락처 확보·G5 발송 승인 3계열.
    전부 실측이다(합성 데이터 없음 — G5는 발송기록이 아니라 실제 사람이 누른
    승인일시를 쓴다, 발송기록 7건은 전부 합성 데모라 트렌드에서 뺐다)."""
    g1_days, g4_days, g5_days = {}, {}, {}

    for c in parse_candidates():
        if c["판정"] != "포함":
            continue
        d = _date_only(c["수집일"])
        if d:
            g1_days[d] = g1_days.get(d, 0) + 1

    for c in parse_contacts():
        if c["상태"] != "확보":
            continue
        d = _date_only(_first(r"\*\*탐색일\*\*:\s*(\d{4}-\d{2}-\d{2})", read_text(c["file"])))
        if d:
            g4_days[d] = g4_days.get(d, 0) + 1

    for a in parse_approvals():
        if a["결정"] != "승인":
            continue
        d = _date_only(a["승인일시"])
        if d:
            g5_days[d] = g5_days.get(d, 0) + 1

    all_days = sorted(set(g1_days) | set(g4_days) | set(g5_days))
    if not all_days:
        return {"has_data": False, "days": [], "series": []}

    W, H, PAD_L, PAD_R, PAD_T, PAD_B = 640, 180, 6, 6, 14, 22
    n = len(all_days)
    plot_w, plot_h = W - PAD_L - PAD_R, H - PAD_T - PAD_B
    max_v = max([1] + list(g1_days.values()) + list(g4_days.values()) + list(g5_days.values()))

    def xpos(i):
        return PAD_L + (i * plot_w / (n - 1) if n > 1 else plot_w / 2)

    def ypos(v):
        return PAD_T + plot_h - (v / max_v) * plot_h

    def build(days_dict, label, code, color_cls):
        pts = " ".join(f"{xpos(i):.1f},{ypos(days_dict.get(d, 0)):.1f}" for i, d in enumerate(all_days))
        dots = [{"x": round(xpos(i), 1), "y": round(ypos(days_dict.get(d, 0)), 1),
                 "v": days_dict.get(d, 0), "date": d} for i, d in enumerate(all_days)]
        return {"label": label, "code": code, "points": pts, "dots": dots,
                "color_cls": color_cls, "total": sum(days_dict.values())}

    return {
        "has_data": True, "width": W, "height": H, "max": max_v,
        "first_day": all_days[0], "last_day": all_days[-1],
        "series": [
            build(g1_days, "판정 통과", "G1", _CAT_TREND[0]),
            build(g4_days, "연락처 확보", "G4", _CAT_TREND[1]),
            build(g5_days, "발송 승인", "G5", _CAT_TREND[2]),
        ],
    }


def industry_distribution():
    """업종별 후보 분포 — G1 판정 대상 전체(포함/판정불가/제외 무관) O5 업종 분포.

    O5가 `?`(관찰 불가)이거나 빈값인 건(주로 판정불가 후보)은 "다른 업종"이 아니라
    "업종 자체를 모른다"는 뜻이라 **별도로 센다** — 2026-08-13 실물 대조 결과
    이 값이 17건(+ 빈값 4건)으로 가장 큰 축에 맞먹어, 이걸 이름 없는 "기타"에
    합치면 실제로는 없는 업종처럼 보인다. 상위 3개 실제 업종 외 나머지는
    "기타"(진짜 다른 업종, 드묾)와 "미확인"(O5 관찰 불가)을 하나의 회색 슬라이스로
    합치되, 안에 무엇이 몇 건인지는 라벨에 그대로 남긴다."""
    known_counts = {}
    known_order = []
    unknown = 0
    for c in parse_candidates():
        ind = (c["업종"] or "").strip()
        if not ind or ind == "?":
            unknown += 1
            continue
        if ind not in known_counts:
            known_order.append(ind)
        known_counts[ind] = known_counts.get(ind, 0) + 1

    total = sum(known_counts.values()) + unknown
    top3 = known_order[:3]
    other_known = sum(known_counts[k] for k in known_order[3:])

    rows = []
    cum = 0
    for i, name in enumerate(top3):
        v = known_counts[name]
        pct = _pct(v, total)
        rows.append({"name": name, "value": v, "pct": pct, "from": _pct(cum, total), "color_cls": _CAT_INDUSTRY[i]})
        cum += v
    if other_known or unknown:
        v = other_known + unknown
        pct = _pct(v, total)
        detail = []
        if other_known:
            detail.append(f"기타 업종 {other_known}건")
        if unknown:
            detail.append(f"업종 판정 불가 {unknown}건")
        rows.append({"name": "기타/미확인", "value": v, "pct": pct, "from": _pct(cum, total),
                     "color_cls": _CAT_INDUSTRY[3], "detail": " · ".join(detail)})
    return {"total": total, "rows": rows}


def industry_contact_heatmap():
    """업종 × 연락처 확보 상태 교차표 — 업종에 따라 확보 성공률이 달라지는지 보여준다.
    O5가 `?`(관찰 불가)·빈값이면 "미상"으로 묶는다(`_candidate_industry_map`이 정규화)."""
    cand_industry = _candidate_industry_map()
    statuses = ["확보", "메일 없음", "미확보"]
    grid = {}
    industries = []
    for ct in parse_contacts():
        ind = cand_industry.get(ct["id"], "미상")
        if ind not in industries:
            industries.append(ind)
        s = ct["상태"] if ct["상태"] in statuses else "미확보"
        grid[(ind, s)] = grid.get((ind, s), 0) + 1
    max_v = max([1] + list(grid.values()))
    rows = []
    for ind in industries:
        cells = []
        for s in statuses:
            v = grid.get((ind, s), 0)
            ratio = v / max_v if max_v else 0
            cells.append({"status": s, "value": v, "ratio": round(ratio, 2), "light_text": ratio > 0.55})
        rows.append({"industry": ind, "cells": cells})
    return {"statuses": statuses, "rows": rows}


def _candidate_industry_map():
    """기업 식별자 → 정규화된 업종(O5가 `?`·빈값이면 "미상"). `industry_distribution`·
    `industry_contact_heatmap`·`lead_time_g1_to_g4`가 같은 정규화를 공유한다."""
    m = {}
    for c in parse_candidates():
        ind = (c["업종"] or "").strip()
        m[c["id"]] = "미상" if (not ind or ind == "?") else ind
    return m


def lead_time_g1_to_g4():
    """리드타임 — G1 판정일(수집일) → G4 탐색일. 실측(두 실제 날짜의 차)이다.
    G1→G5(발송)는 지금 실 발송 건이 0건이라(발송기록 전부 합성) 계산하지 않는다."""
    g1_dates = {c["id"]: _date_only(c["수집일"]) for c in parse_candidates() if c["수집일"]}
    industry_map = _candidate_industry_map()

    # 화면 표시명은 도메인 식별자(ingni-store-com 등) 대신 "{업종}회사{번호}"로 보여준다
    # (2026-08-13 사용자 지시 — 심사위원이 도메인만 보고는 무슨 회사인지 가늠하기 어렵다).
    # 번호는 후보 목록에 등장한 순서로 매겨 안정적이다(리드타임 표시 대상이 바뀌어도 안 흔들림).
    industry_seq = {}
    counters = {}
    for c in parse_candidates():
        ind = industry_map.get(c["id"], "미상")
        counters[ind] = counters.get(ind, 0) + 1
        industry_seq[c["id"]] = counters[ind]

    rows = []
    for c in parse_contacts():
        g1d = g1_dates.get(c["id"])
        g4d = _date_only(_first(r"\*\*탐색일\*\*:\s*(\d{4}-\d{2}-\d{2})", read_text(c["file"])))
        if g1d and g4d:
            days = (date.fromisoformat(g4d) - date.fromisoformat(g1d)).days
            if days >= 0:
                ind = industry_map.get(c["id"], "미상")
                label = f"{ind}회사{industry_seq.get(c['id'], '')}"
                rows.append({"id": c["id"], "label": label, "days": days})
    rows.sort(key=lambda r: r["days"], reverse=True)
    max_days = max([1] + [r["days"] for r in rows])
    for r in rows:
        r["pct"] = _pct(r["days"], max_days) or (2 if r["days"] == 0 else 0)
    return {"rows": rows, "max_days": max_days}


_SYNTHETIC_INDUSTRY_KO = {"fashion": "패션", "beauty": "뷰티", "food": "푸드"}


def _friendly_label(cid):
    """화면에 보이는 이름만 다듬는다 — 조인용 식별자(cid) 자체는 그대로 둔다.
    "합성데모-fashion-01" 같은 내부 식별자를 심사위원이 한눈에 읽을 "기업1(패션)"
    형태로 바꾼다(2026-08-13 사용자 지시). 매칭 안 되면 원래 id를 그대로 쓴다."""
    m = re.match(r"합성데모-([a-z]+)-0*(\d+)$", cid or "")
    if m:
        industry = _SYNTHETIC_INDUSTRY_KO.get(m.group(1), m.group(1))
        return f"기업{m.group(2)}({industry})"
    return cid


def _normalize_reply_category(cat):
    """"C1(관심·진행 의향)"과 "C1 — 관심·진행 의향"을 같은 라벨로 합친다 — 목록형·
    표+헤딩형 두 관례가 코드와 설명을 잇는 구두점만 다르다(2026-08-13 발견)."""
    cat = (cat or "").strip()
    m = re.match(r"(C\d+)\s*[—\-(]\s*([^)]+?)\)?$", cat)
    return f"{m.group(1)}({m.group(2).strip()})" if m else cat


def reply_insights():
    """회신 8분류 분포 + 회신까지 걸린 시간. 지금 존재하는 회신 5건 전부
    합성 데모/시연이라(`replies/*.md` 머리에 명시) 그 사실을 함께 반환한다 —
    감춘 채 보여주면 실제 성과처럼 읽힌다."""
    sent_at = {}
    for rel in list_md_files("발송기록"):
        raw = read_text(rel)
        cid = send_record_field(raw, "기업\\s*식별자")
        s = send_record_field(raw, "발송일시")
        if cid and s:
            sent_at[cid] = s

    replies = parse_replies()
    class_counts = {}
    latency_rows = []
    any_synthetic = False
    for r in replies:
        if r["synthetic"]:
            any_synthetic = True
        # "C1(관심·진행 의향)"(목록형)과 "C1 — 관심·진행 의향"(표+헤딩형)이 같은
        # 분류인데 구두점이 달라 따로 집계되던 것을 정규화한다(2026-08-13 실물 대조).
        label = _normalize_reply_category(r["분류"]) or "미분류"
        class_counts[label] = class_counts.get(label, 0) + 1
        s = sent_at.get(r["id"])
        if s and r["수신일시"]:
            try:
                fmt = "%Y-%m-%d-%H%M%S"
                hours = (datetime.strptime(r["수신일시"], fmt) - datetime.strptime(s, fmt)).total_seconds() / 3600
                if hours >= 0:
                    latency_rows.append({"id": r["id"], "label": _friendly_label(r["id"]),
                                          "hours": round(hours, 1), "synthetic": r["synthetic"]})
            except ValueError:
                pass

    class_rows = sorted(class_counts.items(), key=lambda kv: kv[1], reverse=True)
    max_class = max([1] + [v for _, v in class_rows])
    max_hours = max([1] + [r["hours"] for r in latency_rows])
    return {
        "total_replies": len(replies), "any_synthetic": any_synthetic,
        "classification": [{"label": k, "value": v, "pct": _pct(v, max_class)} for k, v in class_rows],
        "latency": [{**r, "pct": _pct(r["hours"], max_hours) or 2} for r in latency_rows],
    }


# ---------- 기대 효과 (2026-08-13 신설) — 실측이 아니라 가정치 ----------

def expected_effects():
    """`docs/50_실사용_도입설계.md`에 이미 근거·가정을 붙여 문서화된 값을 그대로
    시각화한다 — 여기서 새 추정을 만들지 않는다(운영 변수 단일 출처, `CLAUDE.md`
    5절). 근거 없이 지어낸 수치(예: 매출 추정)는 이 프로젝트에 데이터 소스 자체가
    없어 넣지 않았다 — 넣을 수 있는 값만 넣었다. 막대 위치(pct_low/high)는 카드
    안에서만 비교 가능하게 카드별 최댓값 기준으로 스케일한다."""
    proc_rows = [
        {"label": "후보 100건", "cold": 15.0, "warm": 7.5},
        {"label": "후보 300건", "cold": 45.0, "warm": 22.5},
    ]
    proc_max = max(r["cold"] for r in proc_rows)
    for r in proc_rows:
        r["pct_low"] = round(r["warm"] / proc_max * 100)
        r["pct_high"] = round(r["cold"] / proc_max * 100)

    appr_rows = [
        {"label": "발송 대기 10건/일", "low": 10, "high": 30},
        {"label": "발송 대기 30건/일", "low": 30, "high": 90},
    ]
    appr_max = max(r["high"] for r in appr_rows)
    for r in appr_rows:
        r["pct_low"] = round(r["low"] / appr_max * 100)
        r["pct_high"] = round(r["high"] / appr_max * 100)

    return {
        "processing_scale": {
            "source": "docs/50 2절 — G1 실측(기업당 4~9분) 기반 외삽, 가정",
            "unit": "시간", "rows": proc_rows,
        },
        "approval_burden": {
            "source": "docs/50 1-2절 — 승인 1건당 1~3분(가정) × 발송 대기 건수",
            "unit": "분/일", "rows": appr_rows,
        },
    }


# ---------- 개요(홈) 카드 ----------

def overview_counts():
    approvals = parse_approvals()
    pending_approval = sum(1 for a in approvals if a["결정"] not in ("승인", "거부"))
    replies = parse_replies()
    holdlist = parse_holdlist()
    queue = parse_queue()
    return {
        "승인대기": pending_approval,
        "새회신": len(replies),
        "연락처미확보": len(holdlist),
        "위임필요": len(queue["위임브리프"]),
    }
