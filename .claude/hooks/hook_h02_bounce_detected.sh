#!/bin/bash
# H2 — 발송 결과(바운스) 감지. 명세: Harness/hook/h02-bounce-detected.md
#
# 2026-08-11 — Harness/hook/hook_h02_bounce_detected.sh를 이 저장소(라이브)에
# 맞게 이식. 원본의 영문 스킬명(/g6-delivery-status-judging)을 한글
# 스킬명(/g6-발송결과판정)으로 교체 — 그대로 두면 이 세션에 등록되지 않은
# 명령이라 항상 "Unknown command"로 실패한다.
#
# 더미 모듈이다 — 발송 서비스가 바운스를 반환했는지 감지하는 것은 팀원이
# 만드는 발송 인프라 연동의 일이다. 이 스크립트는 그 플랫폼이 이미 역조회로
# 특정한 발송 건과 바운스 코드를 받아서(stdin JSON) g6-발송결과판정을
# 호출하고 전달 로그만 남긴다.
#
# 기대 입력(stdin, JSON):
#   {"send_record": "<{기업식별자}-{발송일시} 또는 파일 경로>",
#    "bounce_code_raw": "<바운스 코드 원문>", "checked_at": "..."}
#
# 의존: jq. claude CLI.

export MSYS_NO_PATHCONV=1  # Git Bash/MSYS가 "/스킬명 ..." 인자를 Windows 경로로 오인해 변형하는 것을 막는다(2026-08-13 실물 테스트로 발견 — claude -p 호출이 "C:/Program Files/Git/..."로 뒤바뀌는 버그, docs/90 리스크 확인)
input=$(cat)
log_dir="$(dirname "$0")/_logs"
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

claude -p "/g6-발송결과판정 ${args}" >> "$log_file" 2>&1 &
echo "[$checked_at] DISPATCHED h02 -> /g6-발송결과판정" >> "$log_file"

exit 0
