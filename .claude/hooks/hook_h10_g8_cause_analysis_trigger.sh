#!/bin/bash
# H10 — G8 원인분석 실행(G6 판정에 종속, H4와 같은 종류). 명세: Harness/hook/h10-g8-cause-analysis-trigger.md
#
# 2026-08-11 — Harness/hook/hook_h10_g8_cause_analysis_trigger.sh를 이 저장소(라이브)에
# 맞게 이식. 영문 스킬명(/g8-cause-analysis) → 한글 스킬명(/g8-원인분석).
#
# 더미 모듈이다 — G6이 [무응답]/[주소 오류]로 확정했다는 사실 자체는
# g6-발송결과판정 실행이 만든다(이 스크립트 밖). 이 스크립트는 그 판정
# 결과를 받아서(stdin JSON) g8-원인분석을 호출하고 전달 로그만 남긴다.
# 별도 스케줄이 아니라 G6 실행이 끝나는 그 자리에서 바로 이어 부르는 것이
# 원래 설계다 — 배치로 묶지 않는다(카드 비고).
#
# 기대 입력(stdin, JSON):
#   {"send_record": "<{기업식별자}-{발송일시}>", "g6_status": "무응답|주소오류",
#    "reason": "<G6 판정 근거>"}
#
# 의존: jq. claude CLI.

export MSYS_NO_PATHCONV=1  # Git Bash/MSYS가 "/스킬명 ..." 인자를 Windows 경로로 오인해 변형하는 것을 막는다(2026-08-13 실물 테스트로 발견 — claude -p 호출이 "C:/Program Files/Git/..."로 뒤바뀌는 버그, docs/90 리스크 확인)
input=$(cat)
log_dir="$(dirname "$0")/_logs"
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

claude -p "/g8-원인분석 ${args}" >> "$log_file" 2>&1 &
echo "[$now] DISPATCHED h10 -> /g8-원인분석" >> "$log_file"

exit 0
