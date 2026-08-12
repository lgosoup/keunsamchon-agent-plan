#!/bin/bash
# H1 — 회신 도착 감지. 명세: Harness/hook/h01-reply-detected.md
#
# 2026-08-11 — Harness/hook/hook_h01_reply_detected.sh를 이 저장소(라이브)에
# 맞게 이식한 것이다. 원본은 Harness 패키지 자신의 영문 스킬명(/g7-reply-processing)을
# 쓰는데, 이 저장소는 한글 스킬명(/g7-회신처리)을 쓴다 — 그대로 두면 이 세션에
# 등록되지 않은 명령이라 항상 "Unknown command"로 실패한다.
#
# 더미 모듈이다 — "메일함에 새 메일이 도착했다"는 감지 자체는 이 스크립트의
# 일이 아니다(팀원이 만드는 발송 전용 메일함 감시 플랫폼의 일). 이 스크립트는
# 그 플랫폼이 이미 감지한 신호를 정해진 인자 형식으로 받아서(stdin JSON)
# (a) 수신 로그 (b) g7-회신처리 호출 (c) 전달 로그만 남긴다.
#
# 기대 입력(stdin, JSON):
#   {"mail_raw": "<메일 원문 전체>", "from": "...", "received_at": "...",
#    "subject": "...", "thread_id": "...", "attachments": ["..."],
#    "matched_send_record": "<specs/발송기록/{기업식별자}-{발송일시}.md 또는 빈 문자열>"}
#
# 의존: jq. claude CLI.

export MSYS_NO_PATHCONV=1  # Git Bash/MSYS가 "/스킬명 ..." 인자를 Windows 경로로 오인해 변형하는 것을 막는다(2026-08-13 실물 테스트로 발견 — claude -p 호출이 "C:/Program Files/Git/..."로 뒤바뀌는 버그, docs/90 리스크 확인)
input=$(cat)
log_dir="$(dirname "$0")/_logs"
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

claude -p "/g7-회신처리 ${args}" >> "$log_file" 2>&1 &
echo "[$now] DISPATCHED h01 -> /g7-회신처리" >> "$log_file"

exit 0
