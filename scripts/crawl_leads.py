#!/usr/bin/env python3
"""
라쿠텐·Qoo10 몰에서 여성 패션 카테고리 판매처(스토어) 목록을 수집하는 크롤러.

목적: H5(G1 주간 재발굴) 더미 감지기(.claude/hooks/dummy_platform_poll.sh)가
소비할 "이번 주 신규 후보" 큐를 실제 데이터로 채운다 — 팀원이 나중에 만들
실제 리드소싱 플랫폼의 최소 대역. 여기서 나온 URL은 합성이 아니라 진짜이고,
G1(g1-기업판정)이 이 URL을 실제로 WebFetch해서 진짜 판정을 낸다. "그 뒤
메일만 실제로 안 보내면 된다"는 사용자 결정에 따라 발굴 단계는 전부 실물로
한다.

사용법:
  pip install requests beautifulsoup4   # 최초 1회
  python scripts/crawl_leads.py

출력(stdout): JSON 배열 — hook_h05_g1_weekly_rediscovery.sh 기대 입력과 동일
  [{"name": "<기업명 원어>", "urls": ["<URL>", ...]}, ...]

⚠ 라쿠텐·Qoo10 둘 다 봇 차단(WAF)이 있을 수 있다 — 이 User-Agent로도 막히면
403/523 에러가 stderr에 찍힌다. 또 두 사이트 모두 목록이 JavaScript로
렌더링되는 영역이 있어 정적 HTML만 받는 requests로는 안 잡힐 수 있다 —
그 경우 결과가 0건으로 나온다(지어내지 않고 정직하게 0건으로 끝낸다).
0건이면 브라우저 개발자도구로 직접 스토어 URL 몇 개를 확인해서 알려주면
그걸로 이어서 진행한다.
"""
import json
import re
import sys

try:
    import requests
except ImportError:
    print("pip install requests beautifulsoup4 먼저 실행하세요", file=sys.stderr)
    sys.exit(1)

try:
    from bs4 import BeautifulSoup
    HAS_BS4 = True
except ImportError:
    HAS_BS4 = False
    print("[경고] beautifulsoup4가 없어 추출을 못 한다 — pip install beautifulsoup4", file=sys.stderr)

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


def fetch(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        return r.text
    except Exception as e:
        print(f"[실패] {url}: {e}", file=sys.stderr)
        return None


def crawl_rakuten(limit=5):
    """라쿠텐 레디스패션 데일리 랭킹 페이지에서 스토어명+URL 추출."""
    url = "https://ranking.rakuten.co.jp/daily/100371/"
    html = fetch(url)
    if not html or not HAS_BS4:
        return []
    soup = BeautifulSoup(html, "html.parser")
    results = []
    for a in soup.find_all("a", href=re.compile(r"rakuten\.co\.jp/[a-zA-Z0-9_-]+/?(\?|$|#)")):
        href = a.get("href", "")
        m = re.search(r"rakuten\.co\.jp/([a-zA-Z0-9_-]+)/?", href)
        if not m:
            continue
        shop_id = m.group(1)
        if shop_id in ("category", "search", "ranking", "item", "event", "gold"):
            continue
        name = a.get_text(strip=True) or shop_id
        results.append((name, f"https://www.rakuten.co.jp/{shop_id}/"))
    return _dedupe(results, limit)


def crawl_qoo10(limit=5):
    """Qoo10.jp 카테고리 페이지에서 판매자명+URL 추출."""
    url = "https://www.qoo10.jp/gmkt.inc/Category/?cate_shop_no=1"
    html = fetch(url)
    if not html or not HAS_BS4:
        return []
    soup = BeautifulSoup(html, "html.parser")
    results = []
    for a in soup.find_all("a", href=re.compile(r"SellerShopInfo|shop\.qoo10")):
        href = a.get("href", "")
        name = a.get_text(strip=True)
        if not name:
            continue
        full = href if href.startswith("http") else f"https://www.qoo10.jp{href}"
        results.append((name, full))
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
