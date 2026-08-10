#!/bin/bash
# H3 — 무응답 판정 시점 도래. 명세: hook/h03-no-response-deadline.md
#
# 더미 모듈이다 — "발송일시로부터 며칠 지났는가"를 재는 스케줄 계산 자체는
# 팀원이 만드는 플랫폼의 일이다(카드가 지목하는 잠정값 10영업일은
# criteria/g6-delivery-status-judging.md 1절에서 매번 다시 읽어야 하며,
# 이 스크립트가 그 값을 하드코딩하지 않는다 — 애초에 언제 부를지 결정하는
# 것 자체가 이 스크립트 밖의 일이기 때문이다). 이 스크립트는 "그 시점이
# 됐다"는 판단이 이미 끝난 뒤 대상 발송 건 식별자만 받아서(stdin JSON)
# g6-delivery-status-judging를 호출하고 전달 로그만 남긴다.
#
# 기대 입력(stdin, JSON): {"send_record": "<{기업식별자}-{발송일시}>"}
#
# 의존: jq. claude CLI.

input=$(cat)
log_dir="$(dirname "$0")/../data/hook로그"
mkdir -p "$log_dir"
log_file="${log_dir}/h03.log"
now=$(date -u +"%Y-%m-%dT%H:%M:%SZ" 2>/dev/null || echo "(시각 미상)")

send_record=$(echo "$input" | jq -r '.send_record // empty')
echo "[$now] RECEIVED h03 send_record=${send_record:-?}" >> "$log_file"

if [[ -z "$send_record" ]]; then
  echo "[$now] SKIP h03 — send_record 없음" >> "$log_file"
  exit 1
fi

args="${send_record} + 회신 도착 여부: 없음, 조회 시점: ${now}"

claude -p "/g6-delivery-status-judging ${args}" >> "$log_file" 2>&1 &
echo "[$now] DISPATCHED h03 -> /g6-delivery-status-judging" >> "$log_file"

exit 0
