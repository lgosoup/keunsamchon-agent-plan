#!/bin/bash
# H9 — 기준/*.md 파일 수정을 감지해 g12-질의응답에 정합성 검토 질문을 넘긴다.
# 명세: Harness/hook/h09-criteria-consistency-review.md
#
# 2026-08-11 — Harness/hook/hook_h9_criteria_review.sh를 **이 저장소(라이브)**에
# 맞게 이식한 것이다. 원본은 Harness 패키지 자신의 영문 경로(criteria/)·영문
# 스킬명(/g12-qna)을 쓰는데, 이 저장소는 한글 경로(기준/)·한글 스킬명
# (/g12-질의응답)을 쓴다 — 그대로 복사하면 조건이 하나도 안 걸린다.
#
# Claude Code PostToolUse 훅(settings.json 참조)으로 등록된다. Edit·Write·MultiEdit
# 도구가 끝날 때마다 이 스크립트가 stdin으로 그 호출의 tool_name·tool_input을 받는다.
#
# 의존: jq. 실행 계정에 claude CLI가 있어야 마지막 호출이 동작한다.

export MSYS_NO_PATHCONV=1  # Git Bash/MSYS가 "/스킬명 ..." 인자를 Windows 경로로 오인해 변형하는 것을 막는다(2026-08-13 실물 테스트로 발견 — claude -p 호출이 "C:/Program Files/Git/..."로 뒤바뀌는 버그, docs/90 리스크 확인)
input=$(cat)
tool_name=$(echo "$input" | jq -r '.tool_name // empty')
file_path=$(echo "$input" | jq -r '.tool_input.file_path // empty')

log_dir="$(dirname "$0")/_logs"
mkdir -p "$log_dir"
log_file="${log_dir}/h9.log"
now=$(date -u +"%Y-%m-%dT%H:%M:%SZ" 2>/dev/null || echo "(시각 미상)")

if [[ "$tool_name" != "Edit" && "$tool_name" != "Write" && "$tool_name" != "MultiEdit" ]]; then
  exit 0
fi
if [[ "$file_path" != *"기준/"* && "$file_path" != *"기준\\"* ]]; then
  exit 0
fi

echo "[$now] OBSERVED h9 file=${file_path}" >> "$log_file"

file_name=$(basename "$file_path")
old_value=$(echo "$input" | jq -r '.tool_input.old_string // "(신규 작성 — 이전 값 없음)"')
new_value=$(echo "$input" | jq -r '.tool_input.new_string // .tool_input.content // "(확인 불가)"')

question="${file_name}의 내용이 다음과 같이 바뀌었다.
[변경 전]
${old_value}
[변경 후]
${new_value}
이 변경이 다른 기준·스펙과 충돌하는지 검토해줘."

echo "[$now] DISPATCHED h9 -> /g12-질의응답 (질문 길이 ${#question}자)" >> "$log_file"

claude -p "/g12-질의응답 ${question}" >> "${log_dir}/h9_review_output.log" 2>&1 &

exit 0
