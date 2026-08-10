#!/bin/bash
# H8 — G11 반응 집계 주기 실행(조건부 이벤트). 명세: hook/h08-g11-aggregation-cycle.md
#
# 더미 모듈이다 — "세그먼트×조건 조합 중 하나라도 5건(criteria/
# g11-response-aggregation.md 1절 최소 표본 크기) 이상 새로 채워졌는지"를
# data/발송기록·data/집계와 대조해 판단하는 것은 이 스크립트가 하지 않는다
# (팀원 플랫폼이 그 대조를 하고, 조건이 맞을 때만 이 스크립트를 부른다).
# 이 스크립트는 호출되면 그대로 g11-response-aggregation을 실행하고 전달
# 로그만 남긴다.
#
# 기대 입력(stdin, JSON, 둘 다 선택): {"date": "YYYY-MM-DD"}
#
# 의존: jq. claude CLI.

input=$(cat)
log_dir="$(dirname "$0")/../data/hook로그"
mkdir -p "$log_dir"
log_file="${log_dir}/h08.log"
now=$(date -u +"%Y-%m-%dT%H:%M:%SZ" 2>/dev/null || echo "(시각 미상)")

date_arg=$(echo "$input" | jq -r '.date // empty' 2>/dev/null)
echo "[$now] RECEIVED h08 date=${date_arg:-(오늘)}" >> "$log_file"

if [[ -n "$date_arg" ]]; then
  claude -p "/g11-response-aggregation ${date_arg}" >> "$log_file" 2>&1 &
else
  claude -p "/g11-response-aggregation" >> "$log_file" 2>&1 &
fi
echo "[$now] DISPATCHED h08 -> /g11-response-aggregation" >> "$log_file"

exit 0
