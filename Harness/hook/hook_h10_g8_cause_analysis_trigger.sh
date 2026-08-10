#!/bin/bash
# H10 — G8 원인분석 실행(G6 판정에 종속, H4와 같은 종류). 명세: hook/h10-g8-cause-analysis-trigger.md
#
# 더미 모듈이다 — G6이 [무응답]/[주소 오류]로 확정했다는 사실 자체는
# g6-delivery-status-judging 실행이 만든다(이 스크립트 밖). 이 스크립트는
# 그 판정 결과를 받아서(stdin JSON) g8-cause-analysis를 호출하고 전달
# 로그만 남긴다. 별도 스케줄이 아니라 G6 실행이 끝나는 그 자리에서 바로
# 이어 부르는 것이 원래 설계다 — 배치로 묶지 않는다(카드 비고).
#
# 기대 입력(stdin, JSON):
#   {"send_record": "<{기업식별자}-{발송일시}>", "g6_status": "무응답|주소오류",
#    "reason": "<G6 판정 근거>"}
#
# 의존: jq. claude CLI.

input=$(cat)
log_dir="$(dirname "$0")/../data/hook로그"
mkdir -p "$log_dir"
log_file="${log_dir}/h10.log"
now=$(date -u +"%Y-%m-%dT%H:%M:%SZ" 2>/dev/null || echo "(시각 미상)")

send_record=$(echo "$input" | jq -r '.send_record // empty')
status=$(echo "$input" | jq -r '.g6_status // empty')
reason=$(echo "$input" | jq -r '.reason // empty')

echo "[$now] RECEIVED h10 send_record=${send_record:-?} status=${status:-?}" >> "$log_file"

if [[ -z "$send_record" || -z "$status" ]]; then
  echo "[$now] SKIP h10 — send_record 또는 g6_status 없음" >> "$log_file"
  exit 1
fi

args="${send_record} + G6 상태(${status}) + 판정 근거: ${reason}"

claude -p "/g8-cause-analysis ${args}" >> "$log_file" 2>&1 &
echo "[$now] DISPATCHED h10 -> /g8-cause-analysis" >> "$log_file"

exit 0
