#!/usr/bin/env python3
"""
라쿠텐 공식 상품검색 API(Ichiba Item Search)로 패션·뷰티·푸드 장르의
판매점(기업) 후보를 대량으로 뽑는 스크립트 — G1 단위 L(명단 수집)의 실제 실행체.

기존 scripts/crawl_leads.py는 Jina AI Reader로 랭킹/카테고리 "페이지"를 긁어
링크를 정규식으로 뽑는 방식이었다. 이 스크립트는 그 대신 라쿠텐이 직접 제공하는
공식 API를 쓴다 — 스크래핑이 아니라 승인된 접근 경로이고, 응답이 처음부터
구조화된 JSON(매장명·매장URL·상품명·이미지·가격)이라 파싱이 필요 없다.

인증: 2026-08 시점 라쿠텐 웹서비스가 신규 발급하는 애플리케이션은 하나가 아니라
둘(Application ID + Access Key)을 함께 요구한다(레거시 문서에 흔한 "applicationId
단독" 안내와 다르다 — 실측으로 확인, 400 "specify valid applicationId"가 accessKey
누락 시 뜨는 오류였다). 엔드포인트 도메인도 레거시(app.rakuten.co.jp)가 아니라
신규(openapi.rakuten.co.jp)다. 앱 등록 시 지정한 허용 IP와 실제 호출 IP가 다르면
403 CLIENT_IP_NOT_ALLOWED가 난다 — 유동 IP 환경이면 IP가 바뀔 때마다 라쿠텐 앱
설정의 허용 IP를 갱신해야 한다.

환경변수(.env, 값은 이 파일에 안 씀 — CLAUDE.md 6절):
  RAKUTEN_APP_ID     — 라쿠텐 웹서비스 "Application ID"
  RAKUTEN_ACCESS_KEY — 라쿠텐 웹서비스 "Access ID"(API 파라미터명은 accessKey)

사용법:
  python scripts/rakuten_api_discover.py [--genre fashion|beauty|food|all] [--pages N] [--hits N]

출력(stdout): JSON 배열 — scripts/crawl_leads.py와 같은 형식
  [{"name": "<매장명>", "urls": ["<매장 URL>"], "genre": "<패션|뷰티|푸드>", "sample_item": "<대표 상품명>"}, ...]

이미 `specs/candidates/후보목록.md`에 있는 라쿠텐 매장 코드는 실행 시점에 그
파일에서 직접 읽어 걸러낸다(정적 목록을 하드코딩하지 않는다 — 파일이 계속
늘어나므로 최신 상태를 매번 다시 읽어야 한다).
"""
import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

API_BASE = "https://openapi.rakuten.co.jp/ichibams/api/IchibaItem/Search/20260701"

# 2026-08-13 실측으로 확인한 상위 장르 ID(IchibaGenre/Search genreId=0 응답에서 확인).
# 기준/G1_기업판정기준.json의 업종 매핑(패션=衣類・服装雑貨等, 뷰티=化粧品,
# 푸드=食品飲料酒類)에 맞춰 골랐다 — 값이 바뀌면(라쿠텐이 장르 트리를 개편하면)
# 이 목록만 갱신하면 된다.
GENRES = {
    "패션": [100371, 551177, 100433, 216131, 558885],  # 레이디스/멘즈패션, 이너, 가방/잡화, 신발
    "뷰티": [100939],  # 美容・コスメ・香水
    "푸드": [100227, 551167],  # 食品, スイーツ・お菓子
}

CANDIDATES_FILE = os.path.join(
    os.path.dirname(__file__), "..", "specs", "candidates", "후보목록.md"
)


def load_existing_shop_codes():
    """specs/candidates/후보목록.md에서 이미 다룬 라쿠텐 shopCode를 뽑는다.

    Spec 「단위 L」의 "이미 수집된 명단(중복 제거용)"을 실제로 구현한 부분이다.
    파일 전체를 컨텍스트에 들고 있을 필요 없이 정규식으로 코드만 뽑는다.
    """
    try:
        with open(CANDIDATES_FILE, "r", encoding="utf-8") as f:
            text = f.read()
    except FileNotFoundError:
        return set()
    return set(re.findall(r"rakuten\.co\.jp/([a-zA-Z0-9_-]+)/", text))


def call_api(app_id, access_key, genre_id, page, hits):
    params = {
        "applicationId": app_id,
        "accessKey": access_key,
        "genreId": genre_id,
        "page": page,
        "hits": hits,
        "sort": "-reviewCount",  # 리뷰 많은 순 — 실제 운영 중인 매장 위주로 잡힘
    }
    url = API_BASE + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "keunsamchon-g1-discover/1.0"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r)


def discover(app_id, access_key, genre_label, genre_ids, pages, hits, seen_codes, seen_this_run):
    results = []
    for genre_id in genre_ids:
        for page in range(1, pages + 1):
            try:
                data = call_api(app_id, access_key, genre_id, page, hits)
            except urllib.error.HTTPError as e:
                body = e.read().decode("utf-8", "ignore")
                print(f"[실패] genre={genre_id} page={page}: HTTP {e.code} {body[:200]}", file=sys.stderr)
                break
            except Exception as e:
                print(f"[실패] genre={genre_id} page={page}: {e!r}", file=sys.stderr)
                break

            items = data.get("Items", [])
            if not items:
                break

            for wrapper in items:
                item = wrapper.get("Item", {})
                shop_url = item.get("shopUrl", "").split("?")[0]
                m = re.search(r"rakuten\.co\.jp/([a-zA-Z0-9_-]+)/", shop_url)
                if not m:
                    continue
                code = m.group(1)
                if code in seen_codes or code in seen_this_run:
                    continue
                seen_this_run.add(code)
                results.append({
                    "name": item.get("shopName", code),
                    "urls": [shop_url],
                    "genre": genre_label,
                    "sample_item": item.get("itemName", "")[:60],
                })

            print(f"[정보] genre={genre_id} page={page}: {len(items)}건 중 신규 매장 누적 {len(results)}", file=sys.stderr)
            time.sleep(1.1)  # 라쿠텐 웹서비스 자체 요청 빈도 가이드 준수(등록 폼에 신고한 QPS=1과 일치)

            if page >= data.get("pageCount", page):
                break
    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--genre", choices=["패션", "뷰티", "푸드", "all"], default="all")
    parser.add_argument("--pages", type=int, default=2, help="장르당 페이지 수(페이지당 매장 최대 hits개)")
    parser.add_argument("--hits", type=int, default=30, help="페이지당 상품 수(라쿠텐 API 상한 30)")
    args = parser.parse_args()

    app_id = os.environ.get("RAKUTEN_APP_ID", "")
    access_key = os.environ.get("RAKUTEN_ACCESS_KEY", "")
    if not app_id or not access_key:
        print("RAKUTEN_APP_ID·RAKUTEN_ACCESS_KEY가 .env에 없습니다", file=sys.stderr)
        sys.exit(1)

    seen_codes = load_existing_shop_codes()
    print(f"[정보] 기존 후보목록에서 확인된 라쿠텐 매장 코드 {len(seen_codes)}개는 제외합니다", file=sys.stderr)

    targets = GENRES.items() if args.genre == "all" else [(args.genre, GENRES[args.genre])]

    seen_this_run = set()
    all_results = []
    for label, ids in targets:
        r = discover(app_id, access_key, label, ids, args.pages, args.hits, seen_codes, seen_this_run)
        print(f"[정보] {label}: 신규 매장 {len(r)}건", file=sys.stderr)
        all_results.extend(r)

    print(json.dumps(all_results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
