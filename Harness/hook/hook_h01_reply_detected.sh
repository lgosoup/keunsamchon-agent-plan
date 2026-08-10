#!/bin/bash
# H1 — 회신 도착 감지. 명세: hook/h01-reply-detected.md
#
# 더미 모듈이다 — "메일함에 새 메일이 도착했다"는 감지 자체는 이 스크립트의
# 일이 아니다(팀원이 만드는 발송 전용 메일함 감시 플랫폼의 일). 이 스크립트는
# 그 플랫폼이 이미 감지한 신호를 정해진 인자 형식으로 받아서(stdin JSON)
# (a) 수신 로그 (b) g7-reply-processing 호출 (c) 전달 로그만 남긴다.
#
# 기대 입력(stdin, JSON):
#   {"mail_raw": "<메일 원문 전체>", "from": "...", "received_at": "...",
#    "subject": "...", "thread_id": "...", "attachments": ["..."],
#    "matched_send_record": "<data/발송기록/{기업식별자}-{발송일시}.md 또는 빈 문자열>"}
#
# 의존: jq. claude CLI.

input=$(cat)
log_dir="$(dirname "$0")/../data/hook로그"
mkdir -p "$log_dir"
log_file="${log_dir}/h01.log"
now=$(echo "$input" | jq -r '.received_at // "(시각 미상)"')

echo "[$now] RECEIVED h01 from=$(echo "$input" | jq -r '.from // "?"') subject=$(echo "$input" | jq -r '.subject // "?"')" >> "$log_file"

mail_raw=$(echo "$input" | jq -r '.mail_raw // empty')
matched=$(echo "$input" | jq -r '.matched_send_record // empty')
if [[ -z "$mail_raw" ]]; then
  echo "[$now] SKIP h01 — mail_raw 없음, 잘못된 호출" >> "$log_file"
  exit 1
fi

args="${mail_raw}"
if [[ -n "$matched" ]]; then
  args="${args}
참조 발신 정보: ${matched}"
fi

claude -p "/g7-reply-processing ${args}" >> "$log_file" 2>&1 &
echo "[$now] DISPATCHED h01 -> /g7-reply-processing" >> "$log_file"

exit 0
