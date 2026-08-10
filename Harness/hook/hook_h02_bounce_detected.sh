#!/bin/bash
# H2 — 발송 결과(바운스) 감지. 명세: hook/h02-bounce-detected.md
#
# 더미 모듈이다 — 발송 서비스가 바운스를 반환했는지 감지하는 것은 팀원이
# 만드는 발송 인프라 연동의 일이다. 이 스크립트는 그 플랫폼이 이미 역조회로
# 특정한 발송 건과 바운스 코드를 받아서(stdin JSON) g6-delivery-status-judging를
# 호출하고 전달 로그만 남긴다.
#
# 기대 입력(stdin, JSON):
#   {"send_record": "<{기업식별자}-{발송일시} 또는 파일 경로>",
#    "bounce_code_raw": "<바운스 코드 원문>", "checked_at": "..."}
#
# 의존: jq. claude CLI.

input=$(cat)
log_dir="$(dirname "$0")/../data/hook로그"
mkdir -p "$log_dir"
log_file="${log_dir}/h02.log"

send_record=$(echo "$input" | jq -r '.send_record // empty')
bounce_code=$(echo "$input" | jq -r '.bounce_code_raw // empty')
checked_at=$(echo "$input" | jq -r '.checked_at // "(시각 미상)"')

echo "[$checked_at] RECEIVED h02 send_record=${send_record:-?} bounce_code=${bounce_code:-?}" >> "$log_file"

if [[ -z "$send_record" || -z "$bounce_code" ]]; then
  echo "[$checked_at] SKIP h02 — send_record 또는 bounce_code_raw 없음" >> "$log_file"
  exit 1
fi

args="${send_record} + 그 건의 메일 시스템 응답: 바운스 코드 원문 = ${bounce_code} / 회신 도착 여부 = 없음 / 조회 시점 = ${checked_at}"

claude -p "/g6-delivery-status-judging ${args}" >> "$log_file" 2>&1 &
echo "[$checked_at] DISPATCHED h02 -> /g6-delivery-status-judging" >> "$log_file"

exit 0
