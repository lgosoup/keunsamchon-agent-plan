"""각 산출물 파일에서 화면에 필요한 요약 필드만 뽑는다.
정확한 전체 내용은 항상 원문(raw)을 함께 돌려줘 상세 화면에서 렌더링한다 —
모든 뉘앙스를 스키마화하지 않는다(docs/35 6절 "가볍게 간다")."""
import re
from markdown_it import MarkdownIt

from data_source import read_text, list_md_files

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
    files = list_md_files("replies")
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
        m = re.search(r"## 1절[\s\S]*?\n(.*?)(?:\n## |\Z)", raw, re.S)
        table = _table_rows(m.group(1)) if m else []
        m2 = re.search(r"## 2절[\s\S]*?\n(.*?)(?:\n## |\Z)", raw, re.S)
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
