"""각 산출물 파일에서 화면에 필요한 요약 필드만 뽑는다.
정확한 전체 내용은 항상 원문(raw)을 함께 돌려줘 상세 화면에서 렌더링한다 —
모든 뉘앙스를 스키마화하지 않는다(docs/35 6절 "가볍게 간다")."""
import re
from markdown_it import MarkdownIt

from data_source import read_text, list_md_files, data_root

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
        cid = lines[0].strip()
        if not cid or cid.startswith("---"):
            continue
        industry = _first(r"\*\*O5\*\*\s*업종:\s*\*\*([^*]+)\*\*", sec)
        verdict = _first(r"\*\*후보\s*판정:\s*([^*]+)\*\*", sec)
        items_count = _first(r"상품\s*개수:\s*([0-9?]+)", sec)
        channel_count = _first(r"판매채널\s*수:\s*([0-9?]+)", sec)
        items.append({
            "id": cid, "업종": industry, "판정": verdict,
            "상품개수": items_count, "채널수": channel_count,
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
    files = list_md_files("contacts")
    out = []
    for rel in files:
        raw = read_text(rel)
        cid = _first(r"^#\s*([^\s—]+)", raw)
        status = _first(r"##\s*상태:\s*\*\*\[([^\]]+)\]\*\*", raw, "미상")
        value = _first(r"\*\*연락처\s*값\*\*\s*\|\s*`([^`]+)`", raw)
        grade = _first(r"\*\*유효\s*등급\*\*\s*\|\s*\*\*([^*]+)\*\*", raw)
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
    — 참조 링크만 있고 본문이 안 보이던 실물 문제를 사용자가 지적해 추가)."""
    m = re.search(label_pattern + r"\s*\n+((?:>.*(?:\n|$))+)", body)
    return m.group(1).strip() if m else ""


def _sent_company_ids():
    """이미 발송 기록이 있는 기업 식별자 집합 — 승인 대기함에서 뺄 대상 판별용(2026-08-12 추가).
    파일명이 아니라 본문의 「기업 식별자」 항목으로 조인한다(G12 스킬과 같은 원칙 — 파일명을 쪼개 추측하지 않는다)."""
    ids = set()
    for rel in list_md_files("발송기록"):
        raw = read_text(rel)
        cid = _first(r"\*\*기업\s*식별자\*\*[:：]?\s*([^\n]+)", raw).strip()
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
            subject = (
                _first(r"###\s*일본어\s*제목\s*\n+件名[:：]\s*([^\n]+)", body)
                or _first(r"###\s*제목\s*\n+([^\n]+)", body)
                or _first(r"\*\*일본어\s*제목\*\*[:：]?\s*([^\n]+)", body)
                or _first(r"(?:^|\n)제목:\s*([^\n]+)", body)
            )
            jp_body_md = (
                _extract_blockquote_after(r"\*\*일본어\s*본문\*\*", body)
                or _extract_blockquote_after(r"###\s*일본어\s*본문", body)
            )
            kr_intent_md = (
                _extract_blockquote_after(r"\*\*한국어\s*발신\s*의도\s*전문\*\*[^\n]*", body)
                or _extract_blockquote_after(r"###\s*한국어\s*발신\s*의도\s*전문", body)
            )
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

def parse_sent():
    files = list_md_files("발송기록")
    status_files = {}
    for rel in list_md_files("상태"):
        raw = read_text(rel)
        cid = _first(r"^#\s*([^\s—]+)", raw)
        status = _first(r"##\s*상태:\s*\*\*\[([^\]]+)\]\*\*", raw, "대기중")
        status_files[cid] = status
    out = []
    for rel in files:
        raw = read_text(rel)
        cid = _first(r"^#\s*([^\s—]+)", raw)
        to_addr = _first(r"\*\*수신\s*주소\*\*:\s*(\S+)", raw)
        sent_at = _first(r"\*\*발송일시\*\*:\s*(\S+)", raw)
        subject = _first(r"###\s*제목\s*\n+([^\n]+)", raw)
        out.append({
            "id": cid, "file": rel, "수신주소": to_addr, "발송일시": sent_at,
            "제목": subject, "상태": status_files.get(cid, "대기중"),
        })
    return out


# ---------- G7 회신함 ----------

def parse_replies():
    # G7은 번역 검증용 추출본을 `replies/_검증입력/`에도 남긴다(감사 기록).
    # 그건 완성 레코드가 아니라 중간 산출물이라 회신함에 섞이면 안 된다 —
    # 발송대기에서 `_검증입력`을 빼는 것과 같은 이유(2026-08-13).
    files = list_md_files("replies", exclude_dirs=("_검증입력",))
    out = []
    for rel in files:
        raw = read_text(rel)
        title = _first(r"^#\s*([^\n]+)", raw)
        received_at = _first(r"\*\*수신일시\*\*:\s*(\S+)", raw)
        category = _first(r"\*\*회신\s*성격\*\*:\s*\*\*([^*]+)\*\*", raw)
        summary = _first(r"\*\*요지\*\*:\s*([^\n]+)", raw)
        ask = _first(r"\*\*상대의 요구·기한\*\*:\s*([^\n]+)", raw)
        out.append({
            "file": rel, "title": title, "수신일시": received_at,
            "분류": category, "요지": summary, "요구": ask,
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
