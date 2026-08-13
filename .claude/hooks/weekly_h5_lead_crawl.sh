#!/bin/bash
# H5 — G1 주간 재발굴, 신규 후보 소스 연결 래퍼.
#
# 2026-08-13 신설. scripts/crawl_leads.py(라쿠텐·Qoo10에서 신규 판매처를
# 실제로 크롤링, 2026-08-13 커밋에 이미 있던 것을 재발견)의 출력을 그대로
# hook_h05_g1_weekly_rediscovery.sh의 기대 입력(stdin JSON 배열)으로 넘긴다 —
# 둘 다 이미 있던 조각을 잇기만 했다, 새 로직을 추가하지 않았다.
#
# crawl_leads.py의 stderr(크롤링 진행 로그·0건 사유)는 h05_crawl.log에 남긴다.
# 크롤링 결과가 0건이면 hook_h05 자신의 0건 게이트가 조용히 종료한다.
#
# 실행: bash .claude/hooks/weekly_h5_lead_crawl.sh
# (Windows 작업 스케줄러가 주 1회 이 스크립트를 직접 호출한다)

HOOKS_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "$HOOKS_DIR/../.." && pwd)"
LOG_DIR="$HOOKS_DIR/_logs"
mkdir -p "$LOG_DIR"
CRAWL_LOG="$LOG_DIR/h05_crawl.log"
now=$(date -u +"%Y-%m-%dT%H:%M:%SZ" 2>/dev/null || echo "(시각 미상)")

echo "[$now] === H5 주간 재발굴 크롤링 시작 ===" >> "$CRAWL_LOG"
cd "$ROOT_DIR"
# .env가 있으면 값을 읽지 않고 그대로 환경변수로만 로드한다(CLAUDE.md 6절) —
# JINA_API_KEY가 여기 있으면 crawl_leads.py가 자동으로 집어 쓴다.
[[ -f "$ROOT_DIR/.env" ]] && set -a && . "$ROOT_DIR/.env" && set +a
python scripts/crawl_leads.py 2>>"$CRAWL_LOG" | bash "$HOOKS_DIR/hook_h05_g1_weekly_rediscovery.sh"
echo "[$now] === H5 주간 재발굴 크롤링 종료 ===" >> "$CRAWL_LOG"
