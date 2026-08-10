#!/bin/bash
# H5 — G1 재발굴 주기 실행(주 1회). 명세: hook/h05-g1-weekly-rediscovery.md
#
# 더미 모듈이다 — "이번 주 신규 후보를 어느 소스에서 뽑아올지"는 이 스크립트가
# 정하지 않는다(카드 비고 그대로 — 팀원이 만드는 명단 수집 소스 연동의 일).
# 이 스크립트는 이미 뽑힌 신규 목록을 받아서(stdin JSON 배열) 건별로
# g1-company-screening을 반복 호출하고, 건마다 전달 로그를 남긴다.
#
# 기대 입력(stdin, JSON 배열): [{"name": "<기업명 원어>", "urls": ["<URL>", ...]}, ...]
#
# 의존: jq. claude CLI.

input=$(cat)
log_dir="$(dirname "$0")/../data/hook로그"
mkdir -p "$log_dir"
log_file="${log_dir}/h05.log"
now=$(date -u +"%Y-%m-%dT%H:%M:%SZ" 2>/dev/null || echo "(시각 미상)")

count=$(echo "$input" | jq 'length' 2>/dev/null || echo 0)
echo "[$now] RECEIVED h05 신규후보=${count}건" >> "$log_file"

if [[ "$count" -eq 0 ]]; then
  echo "[$now] SKIP h05 — 이번 주 신규 후보 0건" >> "$log_file"
  exit 0
fi

echo "$input" | jq -c '.[]' | while read -r item; do
  name=$(echo "$item" | jq -r '.name // empty')
  urls=$(echo "$item" | jq -r '.urls // [] | join(" ")')
  if [[ -z "$name" || -z "$urls" ]]; then
    echo "[$now] SKIP h05 항목 — name 또는 urls 없음: ${item}" >> "$log_file"
    continue
  fi
  claude -p "/g1-company-screening ${name} ${urls}" >> "$log_file" 2>&1 &
  echo "[$now] DISPATCHED h05 -> /g1-company-screening ${name}" >> "$log_file"
done

exit 0
