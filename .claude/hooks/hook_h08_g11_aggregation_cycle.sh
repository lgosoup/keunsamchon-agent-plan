#!/bin/bash
# H8 — G11 반응 집계 주기 실행(조건부 이벤트). 명세: Harness/hook/h08-g11-aggregation-cycle.md
#
# 2026-08-11 — Harness/hook/hook_h08_g11_aggregation_cycle.sh를 이 저장소(라이브)에
# 맞게 이식. 영문 스킬명(/g11-response-aggregation) → 한글 스킬명(/g11-반응집계).
#
# 더미 모듈이다 — "세그먼트×조건 조합 중 하나라도 5건(기준/G11 최소 표본 크기)
# 이상 새로 채워졌는지"를 specs/발송기록·specs/집계와 대조해 판단하는 것은
# 이 스크립트가 하지 않는다(팀원 플랫폼이 그 대조를 하고, 조건이 맞을 때만
# 이 스크립트를 부른다). 이 스크립트는 호출되면 그대로 g11-반응집계를
# 실행하고 전달 로그만 남긴다.
#
# 기대 입력(stdin, JSON, 둘 다 선택): {"date": "YYYY-MM-DD"}
#
# 의존: jq. claude CLI.

export MSYS_NO_PATHCONV=1  # Git Bash/MSYS가 "/스킬명 ..." 인자를 Windows 경로로 오인해 변형하는 것을 막는다(2026-08-13 실물 테스트로 발견 — claude -p 호출이 "C:/Program Files/Git/..."로 뒤바뀌는 버그, docs/90 리스크 확인)
input=$(cat)
log_dir="$(dirname "$0")/_logs"
mkdir -p "$log_dir"
log_file="${log_dir}/h08.log"
now=$(date -u +"%Y-%m-%dT%H:%M:%SZ" 2>/dev/null || echo "(시각 미상)")

date_arg=$(echo "$input" | jq -r '.date // empty' 2>/dev/null)
echo "[$now] RECEIVED h08 date=${date_arg:-(오늘)}" >> "$log_file"

if [[ -n "$date_arg" ]]; then
  claude -p "/g11-반응집계 ${date_arg}" >> "$log_file" 2>&1 &
else
  claude -p "/g11-반응집계" >> "$log_file" 2>&1 &
fi
echo "[$now] DISPATCHED h08 -> /g11-반응집계" >> "$log_file"

exit 0
