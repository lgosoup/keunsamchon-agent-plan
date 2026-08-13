#!/usr/bin/env python3
"""
라쿠텐·Qoo10 몰에서 여성 패션 카테고리 판매처(스토어) 목록을 수집하는 크롤러.

목적: H5(G1 주간 재발굴, .claude/hooks/weekly_h5_lead_crawl.sh가 매주 호출)가
소비할 "이번 주 신규 후보" 큐를 실제 데이터로 채운다. 여기서 나온 URL은
합성이 아니라 진짜이고, G1(g1-기업판정)이 이 URL을 실제로 WebFetch해서
진짜 판정을 낸다. "그 뒤 메일만 실제로 안 보내면 된다"는 사용자 결정에
따라 발굴 단계는 전부 실물로 한다.

사용법:
  pip install requests   # 최초 1회
  python scripts/crawl_leads.py

출력(stdout): JSON 배열 — hook_h05_g1_weekly_rediscovery.sh 기대 입력과 동일
  [{"name": "<기업명 원어>", "urls": ["<URL>", ...]}, ...]

2026-08-13 — 라쿠텐·Qoo10 원본 URL을 직접 열면 타임아웃/403(라쿠텐)·523
오리진 오류(Qoo10)로 막혔다(실측 확인, `docs/90` 리스크54와 같은 마켓플레이스
봇 차단). 멘토 제안으로 Jina AI Reader(`https://r.jina.ai/`)를 앞에 붙여
우회한다 — 실제 렌더링(JS 포함) 후 정리된 Markdown으로 돌려줘 차단과 JS
렌더링 문제를 동시에 해결한다. 그래도 0건이 나오면(예: 그 페이지 자체에
원하는 링크가 없는 경우) 지어내지 않고 정직하게 0건으로 끝낸다 — 그때는
브라우저로 직접 스토어 URL 몇 개를 확인해서 알려주면 그걸로 이어서 진행한다.
"""
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

try:
    import requests
except ImportError:
    print("pip install requests 먼저 실행하세요", file=sys.stderr)
    sys.exit(1)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
}

# 이미 specs/candidates/후보목록.md·보류목록.md에 있는 기업 — 대략적인 중복
# 방지용(완전한 매칭은 아니다, 최종 판단은 G1이 한다). 새 후보가 쌓이면
# 이 목록도 같이 갱신해서 다시 돌린다.
EXISTING_SLUGS = {
    "ingni", "honeys", "titivate", "junonline", "ropepicnic",
    "orbis", "sucrey", "cocacoca",
}


# 2026-08-13 — 라쿠텐·Qoo10 둘 다 원본 URL을 직접 requests로 열면 타임아웃/403
# (라쿠텐) 또는 523 오리진 오류 페이지(Qoo10)만 돌아왔다(실측 확인, `90` 리스크54
# 와 같은 마켓플레이스 봇 차단). 멘토 제안으로 Jina AI Reader(https://r.jina.ai/)를
# 앞에 붙여 우회한다 — Jina가 실제로 렌더링(JS 포함)해서 정리된 Markdown으로
# 돌려주므로 봇 차단과 "목록이 JS 렌더링" 문제를 동시에 해결한다. 대신 응답이
# HTML이 아니라 Markdown이라 파싱을 BeautifulSoup href 매칭에서 정규식 기반
# Markdown 링크(`[텍스트](URL)`) 매칭으로 바꿨다.
#
# API 키: 환경변수 JINA_API_KEY(값은 `.env`, CLAUDE.md 6절 — 이 파일엔 값을
# 쓰지 않는다). 무료 비인증 등급은 짧은 간격의 연속 요청에서 403(레이트리밋)
# 이 났다(실측 확인) — 키가 있으면 한도가 늘어나 그 문제가 줄어든다. 키가
# 없어도 그대로 동작한다(무인증 요청으로 폴백).
JINA_READER = "https://r.jina.ai/"
JINA_API_KEY = os.environ.get("JINA_API_KEY", "")


def fetch(url, retries=2):
    # Jina 무료 등급은 짧은 간격의 연속 요청에서 간헐적으로 403(레이트리밋)을
    # 낸다 — 실측으로 확인됨(같은 URL이 몇 초 뒤 재시도하면 200으로 돌아옴).
    # 이건 "0건"과 다른 신호라 한 번은 대기 후 재시도한다.
    import time
    headers = dict(HEADERS)
    if JINA_API_KEY:
        headers["Authorization"] = f"Bearer {JINA_API_KEY}"
    for attempt in range(retries + 1):
        try:
            r = requests.get(JINA_READER + url, headers=headers, timeout=30)
            r.raise_for_status()
            return r.text
        except requests.exceptions.HTTPError as e:
            if r.status_code == 403 and attempt < retries:
                print(f"[재시도] {url}: 403(레이트리밋 추정), {attempt + 1}번째 재시도 전 30초 대기", file=sys.stderr)
                time.sleep(30)
                continue
            print(f"[실패] {url}: {e}", file=sys.stderr)
            return None
        except Exception as e:
            print(f"[실패] {url}: {e}", file=sys.stderr)
            return None


def crawl_rakuten(limit=5):
    """라쿠텐 레디스패션 데일리 랭킹 페이지(Jina Reader 경유)에서 스토어명+URL 추출."""
    url = "https://ranking.rakuten.co.jp/daily/100371/"
    text = fetch(url)
    if not text:
        return []
    results = []
    seen = set()
    # Markdown 링크: [텍스트](https://item.rakuten.co.jp/{shop}/... 또는 https://www.rakuten.co.jp/{shop}/...)
    for m in re.finditer(r"\[([^\]]*)\]\((https://(?:item|www)\.rakuten\.co\.jp/([a-zA-Z0-9_-]+)/[^)\s]*)\)", text):
        raw_name, shop_id = m.group(1), m.group(3)
        if shop_id in ("category", "search", "ranking", "item", "event", "gold") or shop_id in seen:
            continue
        seen.add(shop_id)
        name = raw_name if raw_name and not raw_name.startswith("!") else shop_id
        results.append((name, f"https://www.rakuten.co.jp/{shop_id}/"))
    return _dedupe(results, limit)


def crawl_qoo10(limit=5):
    """Qoo10.jp 카테고리 페이지(Jina Reader 경유)에서 판매자명+URL 추출.

    ⚠ 2026-08-13 실측 — 이 카테고리 페이지(cate_shop_no=1) 자체는 차단은
    풀렸지만(Jina로 정상 수신) 개별 판매자 링크(SellerShopInfo·shop.qoo10)가
    이 페이지엔 없었다 — 상위 카테고리 트리만 있는 페이지였다. 이건 봇 차단이
    아니라 "이 URL이 판매자 목록이 아니다"라는 별개 문제라 이번엔 손대지
    않았다. 판매자 목록이 실제로 있는 URL로 바꾸는 것은 다음 확인 대상이다.
    """
    url = "https://www.qoo10.jp/gmkt.inc/Category/?cate_shop_no=1"
    text = fetch(url)
    if not text:
        return []
    results = []
    seen = set()
    for m in re.finditer(r"\[([^\]]*)\]\((https?://[^)\s]*(?:SellerShopInfo|shop\.qoo10)[^)\s]*)\)", text):
        raw_name, full = m.group(1), m.group(2)
        if not raw_name or full in seen:
            continue
        seen.add(full)
        results.append((raw_name, full))
    return _dedupe(results, limit)


def _dedupe(pairs, limit):
    seen, uniq = set(), []
    for name, u in pairs:
        if u in seen:
            continue
        seen.add(u)
        uniq.append((name, u))
        if len(uniq) >= limit:
            break
    return uniq


def main():
    rakuten = crawl_rakuten()
    print(f"[정보] 라쿠텐에서 {len(rakuten)}건 발견", file=sys.stderr)
    qoo10 = crawl_qoo10()
    print(f"[정보] Qoo10에서 {len(qoo10)}건 발견", file=sys.stderr)

    out = []
    for name, u in rakuten + qoo10:
        slug_guess = re.sub(r"[^a-z0-9]", "", name.lower())
        if any(existing in slug_guess for existing in EXISTING_SLUGS):
            print(f"[스킵] 기존 후보와 겹치는 듯 — {name}", file=sys.stderr)
            continue
        out.append({"name": name, "urls": [u]})

    if not out:
        print("[결과 0건] 정적 HTML에서 못 찾았다 — JS 렌더링이거나 봇 차단일 수 있다. "
              "지어내지 않는다. 브라우저로 직접 스토어 URL 1~2개를 확인해서 알려주면 "
              "그걸로 이어서 진행한다.", file=sys.stderr)

    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
