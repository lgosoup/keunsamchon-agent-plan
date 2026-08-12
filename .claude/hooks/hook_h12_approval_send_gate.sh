#!/bin/bash
# H12 — 발송 승인 게이트. 명세: Harness/hook/h12-approval-send-gate.md
# 2026-08-11 — 이 저장소(라이브)에 실제로 등록해 쓰는 사본. 로직은
# Harness/hook/hook_h12_approval_send_gate.sh와 동일(그쪽은 이미 한글 경로·
# 한글 스킬명 기준으로 짜여 있어 이식 시 고칠 게 없었다) — 로그 위치만
# `.claude/hooks/_logs/`로 통일했다(Harness는 자기 데이터 폴더 안에 남긴다).
#
# Claude Code PostToolUse 훅으로 등록되어, `발송대기/*.md`(`_검증입력/` 제외)에
# Edit·Write·MultiEdit가 끝날 때마다 「승인 / 거부」 칸이 「승인」으로 바뀌었는지
# 본다. 바뀌었으면 발송 모드를 트리거만 한다 — 실제 승인·무관용 재확인은
# g5-제안메일제작발송 발송 모드(+g5-승인확인)가 한다.
#
# 의존: jq. claude CLI.

export MSYS_NO_PATHCONV=1  # Git Bash/MSYS가 "/스킬명 ..." 인자를 Windows 경로로 오인해 변형하는 것을 막는다(2026-08-13 실물 테스트로 발견 — claude -p 호출이 "C:/Program Files/Git/..."로 뒤바뀌는 버그, docs/90 리스크 확인)
input=$(cat)
tool_name=$(echo "$input" | jq -r '.tool_name // empty')
file_path=$(echo "$input" | jq -r '.tool_input.file_path // empty')

log_dir="$(dirname "$0")/_logs"
mkdir -p "$log_dir"
log_file="${log_dir}/h12.log"
now=$(date -u +"%Y-%m-%dT%H:%M:%SZ" 2>/dev/null || echo "(시각 미상)")

if [[ "$tool_name" != "Edit" && "$tool_name" != "Write" && "$tool_name" != "MultiEdit" ]]; then
  exit 0
fi
# 2026-08-11 실동작 테스트로 발견 — Windows에서 Claude Code가 넘기는 file_path는
# 백슬래시 경로다("C:\...\발송대기\...md"). 슬래시만 보면 아예 안 걸린다.
if [[ "$file_path" != *"발송대기/"* && "$file_path" != *"발송대기\\"* ]]; then
  exit 0
fi
if [[ "$file_path" == *"_검증입력"* || "$file_path" != *.md ]]; then
  exit 0
fi

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

if ! echo "$changed" | grep -Eq '승인[[:space:]]*/[[:space:]]*거부[[:space:]]*\|[[:space:]]*승인[[:space:]]*\|'; then
  exit 0
fi

echo "[$now] APPROVAL DETECTED h12 file=${file_path}" >> "$log_file"

claude -p "/g5-제안메일제작발송 발송 ${file_path}" >> "${log_dir}/h12_dispatch_output.log" 2>&1 &
echo "[$now] DISPATCHED h12 -> /g5-제안메일제작발송 발송 ${file_path}" >> "$log_file"

exit 0
