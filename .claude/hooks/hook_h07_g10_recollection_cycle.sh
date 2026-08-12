#!/bin/bash
# H7 — G10 재수집 주기 실행(대상별 30일 지연 타이머). 명세: Harness/hook/h07-g10-recollection-cycle.md
#
# 2026-08-11 — Harness/hook/hook_h07_g10_recollection_cycle.sh를 이 저장소(라이브)에
# 맞게 이식. 영문 스킬명(/g10-recollection-judging) → 한글 스킬명(/g10-재수집판단).
#
# 더미 모듈이다 — "마지막 판정으로부터 30일 지났는가" 계산은 이 스크립트가
# 하지 않는다(팀원 플랫폼이 판단해 이미 조건이 맞을 때만 부른다). 이
# 스크립트는 유입 소스와 대상 기업 식별자만 받아서(stdin JSON)
# g10-재수집판단을 호출하고 전달 로그만 남긴다. 승격 조건(3회째 등) 판단은
# 이 스크립트가 아니라 그 스킬 자신이 한다(카드 비고 그대로).
#
# 기대 입력(stdin, JSON):
#   {"source": "<G4 미확보 | G1 판정불가·G2 미분류 | 외부 시간경과·트렌드>",
#    "company_id": "<기업 식별자>", "note": "<선택 — 외부 신호면 무엇이 바뀌었는지>"}
#
# 의존: jq. claude CLI.

export MSYS_NO_PATHCONV=1  # Git Bash/MSYS가 "/스킬명 ..." 인자를 Windows 경로로 오인해 변형하는 것을 막는다(2026-08-13 실물 테스트로 발견 — claude -p 호출이 "C:/Program Files/Git/..."로 뒤바뀌는 버그, docs/90 리스크 확인)
input=$(cat)
log_dir="$(dirname "$0")/_logs"
mkdir -p "$log_dir"
log_file="${log_dir}/h07.log"
now=$(date -u +"%Y-%m-%dT%H:%M:%SZ" 2>/dev/null || echo "(시각 미상)")

source_type=$(echo "$input" | jq -r '.source // empty')
company_id=$(echo "$input" | jq -r '.company_id // empty')
note=$(echo "$input" | jq -r '.note // empty')

echo "[$now] RECEIVED h07 source=${source_type:-?} company_id=${company_id:-?}" >> "$log_file"

if [[ -z "$source_type" || -z "$company_id" ]]; then
  echo "[$now] SKIP h07 — source 또는 company_id 없음" >> "$log_file"
  exit 1
fi

args="${source_type} ${company_id}"
if [[ -n "$note" ]]; then
  args="${args} ${note}"
fi

claude -p "/g10-재수집판단 ${args}" >> "$log_file" 2>&1 &
echo "[$now] DISPATCHED h07 -> /g10-재수집판단 ${company_id}" >> "$log_file"

exit 0
