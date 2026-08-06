#!/bin/bash
# H9 — criteria/*.md 파일 수정을 감지해 g12-qna에 정합성 검토 질문을 넘긴다.
# 명세: hook/h09-criteria-consistency-review.md
#
# Claude Code PostToolUse 훅(settings.json 참조)으로 등록된다. Edit·Write·MultiEdit
# 도구가 끝날 때마다 이 스크립트가 stdin으로 그 호출의 tool_name·tool_input을 받는다.
# 이 스크립트는 (a) 그 파일이 criteria/ 안인지 (b) 맞다면 변경 전/후 값을 뽑아
# 정합성 검토 질문 하나로 조립해 g12-qna를 부르는 것까지만 한다 — 검토 결과를
# criteria 파일에 반영하는 것은 이 스크립트의 일이 아니다(사람 몫, U4).
#
# 의존: jq. 실행 계정에 claude CLI가 있어야 마지막 호출이 동작한다.

input=$(cat)
tool_name=$(echo "$input" | jq -r '.tool_name // empty')
file_path=$(echo "$input" | jq -r '.tool_input.file_path // empty')

# Edit류 도구가 아니거나 criteria/ 밖의 파일이면 이 훅이 할 일이 없다.
if [[ "$tool_name" != "Edit" && "$tool_name" != "Write" && "$tool_name" != "MultiEdit" ]]; then
  exit 0
fi
if [[ "$file_path" != *"/criteria/"* ]]; then
  exit 0
fi

file_name=$(basename "$file_path")
old_value=$(echo "$input" | jq -r '.tool_input.old_string // "(신규 작성 — 이전 값 없음)"')
new_value=$(echo "$input" | jq -r '.tool_input.new_string // .tool_input.content // "(확인 불가)"')

# 정합성 대조 질문만 만든다 — 효과 예측(회신율 개선 여부 등)은 묻지 않는다.
# (specs/g12-qna.md 「제약」·실행 형태 실패표 예외 범위, hook/h09 참조)
question="${file_name}의 내용이 다음과 같이 바뀌었다.
[변경 전]
${old_value}
[변경 후]
${new_value}
이 변경이 다른 기준·스펙과 충돌하는지 검토해줘."

log_dir="$(dirname "$0")/../data/질의응답로그"
mkdir -p "$log_dir"

# 실제 호출 — 세션 비용·권한 프롬프트가 발생할 수 있으니 무인 배치 환경에서는
# 미리 권한을 구성해 두거나, 아래를 "질문을 큐 파일에 적재"로 바꿔 사용해도 된다.
claude -p "/g12-qna ${question}" >> "${log_dir}/_h9_review.log" 2>&1 &

exit 0
