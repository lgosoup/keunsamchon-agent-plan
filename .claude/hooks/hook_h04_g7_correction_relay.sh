#!/bin/bash
# H4 — G7 정정 신호를 G6로 전달(되돌림 간선). 명세: Harness/hook/h04-g7-correction-relay.md
#
# 2026-08-11 — Harness/hook/hook_h04_g7_correction_relay.sh를 이 저장소(라이브)에
# 맞게 이식. 영문 스킬명(/g6-delivery-status-judging) → 한글 스킬명(/g6-발송결과판정).
#
# 더미 모듈이다 — G7이 자동응답으로 판정했다는 사실 자체는 g7-회신처리 실행이
# 만든다(이 스크립트 밖). 이 스크립트는 그 판정 결과를 받아서(stdin JSON)
# g6-발송결과판정에 정정 신호로 전달하고 전달 로그만 남긴다. workflow.md가
# "이 간선을 빠뜨리면 안 된다"고 지목한 자리 — 이게 없으면 자동응답이
# 회신으로 영구히 남는다.
#
# 기대 입력(stdin, JSON):
#   {"send_record": "<{기업식별자}-{발송일시}>", "correction": "자동응답 판정됨"}
#
# 의존: jq. claude CLI.

export MSYS_NO_PATHCONV=1  # Git Bash/MSYS가 "/스킬명 ..." 인자를 Windows 경로로 오인해 변형하는 것을 막는다(2026-08-13 실물 테스트로 발견 — claude -p 호출이 "C:/Program Files/Git/..."로 뒤바뀌는 버그, docs/90 리스크 확인)
input=$(cat)
log_dir="$(dirname "$0")/_logs"
mkdir -p "$log_dir"
log_file="${log_dir}/h04.log"
now=$(date -u +"%Y-%m-%dT%H:%M:%SZ" 2>/dev/null || echo "(시각 미상)")

send_record=$(echo "$input" | jq -r '.send_record // empty')
correction=$(echo "$input" | jq -r '.correction // "자동응답 판정됨"')

echo "[$now] RECEIVED h04 send_record=${send_record:-?} correction=${correction}" >> "$log_file"

if [[ -z "$send_record" ]]; then
  echo "[$now] SKIP h04 — send_record 없음" >> "$log_file"
  exit 1
fi

args="${send_record} + G7 정정 신호: ${correction}"

claude -p "/g6-발송결과판정 ${args}" >> "$log_file" 2>&1 &
echo "[$now] DISPATCHED h04 -> /g6-발송결과판정" >> "$log_file"

exit 0
