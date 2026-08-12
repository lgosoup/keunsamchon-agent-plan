#!/bin/bash
# H5 — G1 재발굴 주기 실행(주 1회). 명세: Harness/hook/h05-g1-weekly-rediscovery.md
#
# 2026-08-11 — Harness/hook/hook_h05_g1_weekly_rediscovery.sh를 이 저장소(라이브)에
# 맞게 이식. 영문 스킬명(/g1-company-screening) → 한글 스킬명(/g1-기업판정).
#
# 2026-08-12 — 실사용 중 실제 버그 발견·수정: `jq | while read` 파이프 안에서
# `claude -p ... &`를 stdin 리다이렉트 없이 백그라운드로 띄우면, 그 자식
# 프로세스가 파이프에 남은 나머지 JSON 바이트를 가로채 루프의 `read`가
# 조기 종료됐다(24건 중 5건만 처리되고 멈춤 — 실제 재현됨). ① 루프 입력을
# 프로세스 치환(`< <(...)`)으로 바꿔 같은 파이프를 공유하지 않게 하고
# ② `claude`에 `< /dev/null`을 명시해 이중으로 막았다.
#
# 더미 모듈이다 — "이번 주 신규 후보를 어느 소스에서 뽑아올지"는 이 스크립트가
# 정하지 않는다(카드 비고 그대로 — 팀원이 만드는 명단 수집 소스 연동의 일).
# 이 스크립트는 이미 뽑힌 신규 목록을 받아서(stdin JSON 배열) 건별로
# g1-기업판정을 반복 호출하고, 건마다 전달 로그를 남긴다.
#
# 기대 입력(stdin, JSON 배열): [{"name": "<기업명 원어>", "urls": ["<URL>", ...]}, ...]
#
# 의존: jq. claude CLI.

export MSYS_NO_PATHCONV=1  # Git Bash/MSYS가 "/스킬명 ..." 인자를 Windows 경로로 오인해 변형하는 것을 막는다(2026-08-13 실물 테스트로 발견 — claude -p 호출이 "C:/Program Files/Git/..."로 뒤바뀌는 버그, docs/90 리스크 확인)
input=$(cat)
log_dir="$(dirname "$0")/_logs"
mkdir -p "$log_dir"
log_file="${log_dir}/h05.log"
now=$(date -u +"%Y-%m-%dT%H:%M:%SZ" 2>/dev/null || echo "(시각 미상)")

count=$(echo "$input" | jq 'length' 2>/dev/null || echo 0)
echo "[$now] RECEIVED h05 신규후보=${count}건" >> "$log_file"

if [[ "$count" -eq 0 ]]; then
  echo "[$now] SKIP h05 — 이번 주 신규 후보 0건" >> "$log_file"
  exit 0
fi

while read -r item; do
  name=$(echo "$item" | jq -r '.name // empty')
  urls=$(echo "$item" | jq -r '.urls // [] | join(" ")')
  if [[ -z "$name" || -z "$urls" ]]; then
    echo "[$now] SKIP h05 항목 — name 또는 urls 없음: ${item}" >> "$log_file"
    continue
  fi
  claude -p "/g1-기업판정 ${name} ${urls}" < /dev/null >> "$log_file" 2>&1 &
  echo "[$now] DISPATCHED h05 -> /g1-기업판정 ${name}" >> "$log_file"
done < <(echo "$input" | jq -c '.[]')

exit 0
