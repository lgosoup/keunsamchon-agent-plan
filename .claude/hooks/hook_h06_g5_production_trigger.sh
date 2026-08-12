#!/bin/bash
# H6 — G5 제작 모드 트리거(하이브리드: 이벤트+안전장치 스케줄). 명세: Harness/hook/h06-g5-production-trigger.md
#
# 2026-08-11 — Harness/hook/hook_h06_g5_production_trigger.sh를 이 저장소(라이브)에
# 맞게 이식. 영문 스킬명(/g5-proposal-email-dispatch) → 한글 스킬명(/g5-제안메일제작발송).
#
# 더미 모듈이다 — "세그먼트에 신규 컨택이 5건 누적됐는지" 또는 "마지막 제작
# 이후 7일 지났는지" 계산은 이 스크립트가 하지 않는다(팀원 플랫폼이 판단해
# 이미 조건이 맞을 때만 이 스크립트를 부른다). 이 스크립트는 세그먼트 ID만
# 받아서(stdin JSON) g5-제안메일제작발송을 제작 모드로 호출하고 전달
# 로그만 남긴다.
#
# 비고(카드 원문, 이 스크립트가 구현하지 않음): 세그먼트에 이미 오늘 날짜의
# 발송대기 파일이 있으면 중복 트리거하지 않는 것이 맞다 — 그 중복 판정은
# g5-제안메일제작발송 스킬 자신의 실행 절차(제작 모드)가 맡는다.
#
# 기대 입력(stdin, JSON): {"segment_id": "S1"}
#
# 의존: jq. claude CLI.

export MSYS_NO_PATHCONV=1  # Git Bash/MSYS가 "/스킬명 ..." 인자를 Windows 경로로 오인해 변형하는 것을 막는다(2026-08-13 실물 테스트로 발견 — claude -p 호출이 "C:/Program Files/Git/..."로 뒤바뀌는 버그, docs/90 리스크 확인)
input=$(cat)
log_dir="$(dirname "$0")/_logs"
mkdir -p "$log_dir"
log_file="${log_dir}/h06.log"
now=$(date -u +"%Y-%m-%dT%H:%M:%SZ" 2>/dev/null || echo "(시각 미상)")

segment_id=$(echo "$input" | jq -r '.segment_id // empty')
echo "[$now] RECEIVED h06 segment_id=${segment_id:-?}" >> "$log_file"

if [[ -z "$segment_id" ]]; then
  echo "[$now] SKIP h06 — segment_id 없음" >> "$log_file"
  exit 1
fi

claude -p "/g5-제안메일제작발송 제작 ${segment_id}" >> "$log_file" 2>&1 &
echo "[$now] DISPATCHED h06 -> /g5-제안메일제작발송 제작 ${segment_id}" >> "$log_file"

exit 0
