#!/bin/bash
# H12 — 발송 승인 게이트. 명세: hook/h12-approval-send-gate.md
#
# H9와 같은 부류(이 실행 환경 자신이 관측 가능한 사건)라 **실제 구현**이다 —
# 나머지 10개(H1~H8·H10·H11)처럼 더미가 아니다. Claude Code PostToolUse
# 훅으로 등록되어(settings.json), `data/발송대기/*.md`(`_검증입력/` 제외)에
# Edit·Write·MultiEdit가 끝날 때마다 이 스크립트가 stdin으로 tool_name·
# tool_input을 받는다. 「승인 / 거부」 칸이 「승인」으로 바뀐 것을 감지하면
# 발송 모드를 트리거만 한다 — 실제 승인·무관용 재확인은 여전히
# g5-proposal-email-dispatch 발송 모드(+g5-approval-check)가 한다. 이
# 스크립트가 오탐해도 그 아래 게이트가 최종 방어선이다.
#
# 의존: jq. 실행 계정에 claude CLI가 있어야 마지막 호출이 동작한다.

input=$(cat)
tool_name=$(echo "$input" | jq -r '.tool_name // empty')
file_path=$(echo "$input" | jq -r '.tool_input.file_path // empty')

log_dir="$(dirname "$0")/../data/hook로그"
mkdir -p "$log_dir"
log_file="${log_dir}/h12.log"
now=$(date -u +"%Y-%m-%dT%H:%M:%SZ" 2>/dev/null || echo "(시각 미상)")

# Edit류 도구가 아니거나 발송대기/ 밖의 파일, 또는 _검증입력/(감사 기록) 안이면 할 일이 없다.
if [[ "$tool_name" != "Edit" && "$tool_name" != "Write" && "$tool_name" != "MultiEdit" ]]; then
  exit 0
fi
# 2026-08-11 라이브 실동작 테스트로 발견 — Windows에서 file_path는 백슬래시
# 경로로 온다("C:\...\발송대기\...md"). 슬래시만 보면 Windows에서 아예 안 걸린다.
if [[ "$file_path" != *"발송대기/"* && "$file_path" != *"발송대기\\"* ]]; then
  exit 0
fi
if [[ "$file_path" == *"_검증입력"* || "$file_path" != *.md ]]; then
  exit 0
fi

# 변경된 텍스트를 도구 종류별로 모은다 — Edit는 new_string, Write는 content,
# MultiEdit는 edits[].new_string 전부.
case "$tool_name" in
  Edit)
    changed=$(echo "$input" | jq -r '.tool_input.new_string // empty')
    ;;
  Write)
    changed=$(echo "$input" | jq -r '.tool_input.content // empty')
    ;;
  MultiEdit)
    changed=$(echo "$input" | jq -r '[.tool_input.edits[]?.new_string] | join("\n")')
    ;;
esac

echo "[$now] OBSERVED h12 file=${file_path} tool=${tool_name}" >> "$log_file"

# 「승인 / 거부」 칸이 「승인」으로 채워졌는지만 본다 — 「거부」·빈 칸·다른 값은 무시.
if ! echo "$changed" | grep -Eq '승인[[:space:]]*/[[:space:]]*거부[[:space:]]*\|[[:space:]]*승인[[:space:]]*\|'; then
  exit 0
fi

echo "[$now] APPROVAL DETECTED h12 file=${file_path}" >> "$log_file"

claude -p "/g5-proposal-email-dispatch 발송 ${file_path}" >> "$log_file" 2>&1 &
echo "[$now] DISPATCHED h12 -> /g5-proposal-email-dispatch 발송 ${file_path}" >> "$log_file"

exit 0
