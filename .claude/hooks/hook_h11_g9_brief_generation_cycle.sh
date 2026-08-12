#!/bin/bash
# H11 — G9 위임 브리프 생성(주 1회). 명세: Harness/hook/h11-g9-brief-generation-cycle.md
#
# 2026-08-11 — Harness/hook/hook_h11_g9_brief_generation_cycle.sh를 이 저장소(라이브)에
# 맞게 이식. 영문 스킬명(/g9-handoff-brief) → 한글 스킬명(/g9-위임브리프).
#
# 2026-08-12 — H5에서 실사용 중 발견된 것과 같은 버그를 예방 차원에서 미리
# 고침: `jq | while read` 파이프 안에서 `claude -p ... &`를 stdin 리다이렉트
# 없이 백그라운드로 띄우면 그 자식이 파이프의 나머지 JSON을 가로채 루프가
# 조기 종료된다(H5에서 24건 중 5건만 처리되고 멈춘 것으로 실제 확인됨).
# ① 루프 입력을 프로세스 치환으로 바꾸고 ② `claude`에 `< /dev/null`을 명시.
#
# 더미 모듈이다 — "이번 주 새로 쌓인 G4 [미확보]·G8 재시도가치 高 건"을
# 모으는 것은 이 스크립트가 하지 않는다(팀원 플랫폼이 specs/를 대조해 목록을
# 만들어 이 스크립트를 부른다). 이 스크립트는 그 목록을 받아서(stdin JSON
# 배열) 건별로 g9-위임브리프를 반복 호출하고 전달 로그만 남긴다. 그 주
# 0건이면 실행을 건너뛴다(카드 비고 — G11의 "0건이면 파일을 만들지 않는다"
# 게이트와 같은 처리).
#
# 인자 형식은 .claude/skills/g9-위임브리프/SKILL.md 「인자」 절이 정본이다 —
# `/g9-위임브리프 경로1|경로2 <기업식별자> [경로2면 G8 근거를 이어서]`
# 순서이며, "G4 미확보"·"G8 재시도高" 같은 서술형 라벨이 아니라 **"경로1"·
# "경로2"라는 리터럴 토큰**을 받는다.
#
# 기대 입력(stdin, JSON 배열):
#   [{"company_id": "<기업 식별자>", "path": "경로1|경로2",
#     "extra": "<선택 — 경로2인데 G8 원인분석 파일이 없을 때 이어붙일 근거>"}, ...]
#
# 의존: jq. claude CLI.

export MSYS_NO_PATHCONV=1  # Git Bash/MSYS가 "/스킬명 ..." 인자를 Windows 경로로 오인해 변형하는 것을 막는다(2026-08-13 실물 테스트로 발견 — claude -p 호출이 "C:/Program Files/Git/..."로 뒤바뀌는 버그, docs/90 리스크 확인)
input=$(cat)
log_dir="$(dirname "$0")/_logs"
mkdir -p "$log_dir"
log_file="${log_dir}/h11.log"
now=$(date -u +"%Y-%m-%dT%H:%M:%SZ" 2>/dev/null || echo "(시각 미상)")

count=$(echo "$input" | jq 'length' 2>/dev/null || echo 0)
echo "[$now] RECEIVED h11 대상=${count}건" >> "$log_file"

if [[ "$count" -eq 0 ]]; then
  echo "[$now] SKIP h11 — 이번 주 대상 0건, 실행 건너뜀" >> "$log_file"
  exit 0
fi

while read -r item; do
  company_id=$(echo "$item" | jq -r '.company_id // empty')
  path=$(echo "$item" | jq -r '.path // empty')
  extra=$(echo "$item" | jq -r '.extra // empty')

  if [[ -z "$company_id" || ( "$path" != "경로1" && "$path" != "경로2" ) ]]; then
    echo "[$now] SKIP h11 항목 — company_id 없음 또는 path가 경로1/경로2가 아님: ${item}" >> "$log_file"
    continue
  fi

  args="${path} ${company_id}"
  if [[ -n "$extra" ]]; then
    args="${args} ${extra}"
  fi

  claude -p "/g9-위임브리프 ${args}" < /dev/null >> "$log_file" 2>&1 &
  echo "[$now] DISPATCHED h11 -> /g9-위임브리프 ${path} ${company_id}" >> "$log_file"
done < <(echo "$input" | jq -c '.[]')

exit 0
