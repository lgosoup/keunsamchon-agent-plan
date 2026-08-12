#!/bin/bash
# 더미 플랫폼 폴러 — "팀원이 만들 외부 감지 플랫폼"의 최소 대역 구현.
#
# 2026-08-12 신설. 사용자 지시: 훅 스크립트(dispatch)만 더미로 두지 말고
# 그 앞의 "언제 부를지 감지하는" 자리도 더미로 채워서 지금 이 저장소
# 상태만으로 전체가 실제로 자동 연쇄되게 하라 — 입출력 관계(계약)만 맞추면
# 나중에 진짜 API/플랫폼으로 바꿔치기했을 때 "연결 문제"인지 "구조 문제"인지
# 가릴 수 있다는 것이 그 이유다.
#
# 이 스크립트가 하는 일: specs/ 안의 실제 파일 상태(합성 데모 데이터 포함)를
# 훑어서 각 Hook(H2·H3·H4·H6·H7·H8·H10·H11)의 발동 조건이 "지금 참인가"를
# 판정하고, 참이면 그 Hook이 요구하는 정확한 JSON을 만들어 같은 디렉터리의
# hook_hXX.sh를 직접 호출한다. **감지 로직 자체는 전부 잠정(더미)이다** —
# 각 함수 위 주석에 "실제로 이 자리를 대체할 것"을 적어 뒀다. 값(10영업일,
# 30일, 5건, 7일)은 전부 `기준/`·`docs/92`·`docs/93`이 이미 정본으로 갖고
# 있는 임의값을 그대로 재사용한다 — 여기서 새 숫자를 짓지 않는다.
#
# H1(회신 도착 감지)·H5(G1 주간 재발굴)는 이 폴러가 다루지 않는다 — 아래
# "다루지 않는 것" 절 참조. 감지할 실제 원천 데이터(수신 메일함, 신규 리드
# 소스)가 이 저장소 어디에도 없어서, 없는 데이터를 있는 척 지어내는 대신
# 정직하게 건너뛴다.
#
# 실행: bash .claude/hooks/dummy_platform_poll.sh
# (Bash가 없는 에이전트 세션 대신 사용자가 `!` 접두어로 직접 돌린다)
#
# 의존: jq, GNU date(coreutils, Git Bash 기본 포함).

HOOKS_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "$HOOKS_DIR/../.." && pwd)"
SPECS_DIR="$ROOT_DIR/specs"
KIJUN_DIR="$ROOT_DIR/기준"
LOG_DIR="$HOOKS_DIR/_logs"
mkdir -p "$LOG_DIR"
POLL_LOG="$LOG_DIR/poll.log"
now_iso=$(date -u +"%Y-%m-%dT%H:%M:%SZ" 2>/dev/null || echo "(시각 미상)")
today=$(date +%F)

log() { echo "[$now_iso] $1" >> "$POLL_LOG"; }

log "=== 폴링 시작 (오늘: ${today}) ==="

# 두 날짜(YYYY-MM-DD) 사이의 영업일 수(월~금만 센다, 공휴일은 안 본다 — 잠정)
business_days_between() {
  local d="$1" end="$2" count=0
  while [[ "$d" < "$end" ]]; do
    d=$(date -d "$d + 1 day" +%F)
    wd=$(date -d "$d" +%u)
    if [[ "$wd" -lt 6 ]]; then
      count=$((count + 1))
    fi
  done
  echo "$count"
}

field() { # field <파일> <라벨> — "- **라벨**: 값" 또는 "**라벨**: 값" 한 줄에서 값만 뽑는다
  grep -m1 -- "$2" "$1" 2>/dev/null | sed -E 's/^[^:]*: *//; s/`//g'
}

# ============================================================
# H3 — 무응답 판정 시점 도래 (실제 자리: 팀원 플랫폼의 스케줄 타이머.
# 여기서는 그 대신 발송기록×상태를 매 폴링마다 직접 비교한다.)
# 기준: 기준/G6_판정기준.md 3절 — 잠정 10영업일, 아직 [회신]/[주소 오류]/
# [무응답]으로 확정 안 된 건만 대상.
# ============================================================
poll_h3() {
  log "-- H3 무응답기한 점검 --"
  local sf id ts send_date status_file bdays payload
  for sf in "$SPECS_DIR"/발송기록/*.md; do
    [[ -f "$sf" ]] || continue
    id=$(field "$sf" "기업 식별자")
    ts=$(field "$sf" "발송일시")
    [[ -z "$id" || -z "$ts" ]] && continue
    status_file="$SPECS_DIR/상태/${id}-${ts}.md"
    [[ -f "$status_file" ]] || { log "H3 스킵 — 상태 파일 없음: ${id}-${ts}"; continue; }
    if grep -qE '상태: \*\*\[(회신|주소 오류|무응답)\]\*\*' "$status_file"; then
      continue
    fi
    send_date=$(echo "$ts" | cut -d- -f1-3)
    bdays=$(business_days_between "$send_date" "$today")
    if [[ "$bdays" -ge 10 ]]; then
      payload=$(jq -n --arg sr "${id}-${ts}" '{send_record: $sr}')
      log "H3 조건 충족 — ${id}-${ts} (영업일 ${bdays}일 경과) -> dispatch"
      echo "$payload" | bash "$HOOKS_DIR/hook_h03_no_response_deadline.sh"
    fi
  done
}

# ============================================================
# H4 — G7 정정 신호를 G6로 전달 (실제 자리: g7-회신처리 실행이 끝나는 순간
# 바로 이어 불러야 하는 이벤트. 여기서는 폴링으로 대신한다 — replies/에
# C6(자동응답) 판정이 있는데 대응 상태 파일이 아직 정정 안 된 경우를 찾는다.)
# ============================================================
poll_h4() {
  log "-- H4 자동응답 정정 릴레이 점검 --"
  local rf send_ref id ts status_file payload
  for rf in "$SPECS_DIR"/replies/*.md; do
    [[ -f "$rf" ]] || continue
    grep -q '회신 성격.*C6' "$rf" || continue
    send_ref=$(grep -m1 '어느 발송 건에 대한 답인가' "$rf" | grep -oE '발송기록/[^`) ]+\.md')
    [[ -z "$send_ref" ]] && { log "H4 스킵 — 발송 건 참조 못 찾음: $rf"; continue; }
    id=$(field "$SPECS_DIR/${send_ref}" "기업 식별자")
    ts=$(field "$SPECS_DIR/${send_ref}" "발송일시")
    [[ -z "$id" || -z "$ts" ]] && continue
    status_file="$SPECS_DIR/상태/${id}-${ts}.md"
    [[ -f "$status_file" ]] || continue
    if grep -q '정정 이력.*자동응답' "$status_file"; then
      continue
    fi
    payload=$(jq -n --arg sr "${id}-${ts}" '{send_record: $sr, correction: "자동응답 판정됨"}')
    log "H4 조건 충족 — ${id}-${ts} (C6 미정정) -> dispatch"
    echo "$payload" | bash "$HOOKS_DIR/hook_h04_g7_correction_relay.sh"
  done
}

# ============================================================
# H2 — 바운스 감지 (실제 자리: 발송 인프라의 바운스 웹훅. 여기서는
# dummy_send_api.sh의 로그(api-send.log)에서 아직 상태에 안 반영된
# BOUNCED 항목을 찾는다 — "reflected=아니오"로 남긴 것만 대상)
# ============================================================
poll_h2() {
  log "-- H2 바운스 감지 점검 --"
  local api_log="$LOG_DIR/api-send.log"
  [[ -f "$api_log" ]] || { log "H2 스킵 — api-send.log 없음(아직 더미 발송 API 호출된 적 없음)"; return; }
  log "H2 — api-send.log를 확인하되, 이 폴러는 어느 발송기록에 대응하는지(수신 주소 조인)까지는 자동화하지 않는다. 실제 발송 기록과 API 응답을 잇는 것은 g5-제안메일제작발송 발송 모드 자신의 일이다(specs/G5 「출력 형식」) — 이 폴러가 그 경계를 넘지 않는다."
}

# ============================================================
# H6 — G5 제작 트리거 (실제 자리: 세그먼트별 신규 컨택 누적/경과일 감시.
# 임의값 출처: docs/92_기업답변_대기_임의값.md 2절 — 5건 누적 또는 7일 경과)
# 여기서는 "세그먼트 소속 중 [확보] 상태인데 오늘까지 어느 발송대기 파일에도
# 없는 기업 수"만 센다 — 7일 경과 축은 발송대기 파일의 마지막 작성일 비교가
# 필요해 이 잠정 폴러에서는 생략한다(아래 로그에 그대로 밝힌다).
# ============================================================
poll_h6() {
  log "-- H6 제작 트리거 점검(5건 누적 축만, 7일 경과 축은 생략) --"
  # 주의: 파일 레벨 ID(예: SEG-A)와 클러스터 ID(예: S1)는 다르다 — 발송대기/
  # 발송기록의 세그먼트 참조는 클러스터 ID(S1)를 쓰므로 그것을 기준으로 판다.
  local segf seg_ids seg_id id status_file drafted count payload
  for segf in "$SPECS_DIR"/segments/*.md; do
    [[ -f "$segf" ]] || continue
    seg_ids=$(grep -oE '^\| \*\*[A-Z][0-9]+\*\*' "$segf" | grep -oE '[A-Z][0-9]+' | sort -u)
    for seg_id in $seg_ids; do
      count=0
      while IFS= read -r id; do
        [[ -z "$id" ]] && continue
        status_file="$SPECS_DIR/contacts/${id}.md"
        [[ -f "$status_file" ]] || continue
        grep -qE '상태: \[확보\]' "$status_file" || continue
        drafted="아니오"
        if ls "$SPECS_DIR"/발송대기/"${seg_id}"-*.md >/dev/null 2>&1; then
          drafted="예"
        fi
        [[ "$drafted" == "아니오" ]] && count=$((count + 1))
      done < <(grep -E "^\| [a-zA-Z0-9.-]+ \| \*\*${seg_id}\*\* \|" "$segf" | awk -F'|' '{gsub(/ /,"",$2); print $2}')
      if [[ "$count" -ge 5 ]]; then
        payload=$(jq -n --arg s "$seg_id" '{segment_id: $s}')
        log "H6 조건 충족 — ${seg_id} (미제작 [확보] ${count}건) -> dispatch"
        echo "$payload" | bash "$HOOKS_DIR/hook_h06_g5_production_trigger.sh"
      else
        log "H6 미충족 — ${seg_id} (미제작 [확보] ${count}건 < 5)"
      fi
    done
  done
}

# ============================================================
# H7 — G10 재수집 주기 (실제 자리: 대상별 30일 지연 타이머.
# 임의값 출처: docs/93 #17 — 30일. 여기서는 contacts/*.md의 [미확보]·
# [메일 없음] 중 탐색일로부터 30일 지났고, 아직 재수집대상 파일이 없는
# 건을 찾는다.)
# ============================================================
poll_h7() {
  log "-- H7 재수집 주기 점검 --"
  local cf id searched_date days_since payload
  for cf in "$SPECS_DIR"/contacts/*.md; do
    [[ -f "$cf" ]] || continue
    grep -qE '상태: \[(미확보|메일 없음)\]' "$cf" || continue
    id=$(field "$cf" "기업 식별자")
    searched_date=$(field "$cf" "탐색일")
    [[ -z "$id" || -z "$searched_date" ]] && continue
    searched_date=$(echo "$searched_date" | grep -oE '[0-9]{4}-[0-9]{2}-[0-9]{2}' | head -1)
    [[ -z "$searched_date" ]] && continue
    if ls "$SPECS_DIR"/재수집대상/"${id}"-*.md >/dev/null 2>&1; then
      continue
    fi
    days_since=$(( ($(date -d "$today" +%s) - $(date -d "$searched_date" +%s)) / 86400 ))
    if [[ "$days_since" -ge 30 ]]; then
      payload=$(jq -n --arg c "$id" '{source: "G4 미확보", company_id: $c}')
      log "H7 조건 충족 — ${id} (탐색 후 ${days_since}일 경과) -> dispatch"
      echo "$payload" | bash "$HOOKS_DIR/hook_h07_g10_recollection_cycle.sh"
    fi
  done
}

# ============================================================
# H8 — G11 집계 주기 (실제 자리: 세그먼트×조건 조합당 5건 누적 감시.
# 여기서는 오늘 날짜 집계 파일이 이미 있는지만 먼저 확인한다 — 있으면
# g11-반응집계 스킬 자신의 "같은 집계일 덮어쓰지 않는다" 게이트가 막을
# 것이므로 굳이 다시 세지 않고 스킵 로그만 남긴다.)
# ============================================================
poll_h8() {
  log "-- H8 집계 주기 점검 --"
  if [[ -f "$SPECS_DIR/집계/${today}.md" ]]; then
    log "H8 스킵 — 오늘(${today}) 집계 파일이 이미 있음(specs/집계/${today}.md) — g11-반응집계 자체 게이트가 중복을 막는다"
    return
  fi
  local total
  total=$(ls "$SPECS_DIR"/발송기록/*.md 2>/dev/null | wc -l)
  if [[ "$total" -ge 5 ]]; then
    log "H8 조건 충족 — 발송기록 ${total}건(오늘자 집계 없음) -> dispatch"
    echo '{}' | bash "$HOOKS_DIR/hook_h08_g11_aggregation_cycle.sh"
  else
    log "H8 미충족 — 발송기록 ${total}건 < 5"
  fi
}

# ============================================================
# H10 — G8 원인분석 실행 (실제 자리: G6 실행이 끝나는 그 자리에서 바로
# 이어 불러야 하는 이벤트. 여기서는 상태/*.md 중 [무응답]·[주소 오류]인데
# 대응 원인분석 파일이 아직 없는 건을 찾는다.)
# ============================================================
poll_h10() {
  log "-- H10 원인분석 트리거 점검 --"
  local sf id ts status reason payload
  for sf in "$SPECS_DIR"/상태/*.md; do
    [[ -f "$sf" ]] || continue
    if grep -q '상태: \*\*\[무응답\]\*\*' "$sf"; then
      status="무응답"
    elif grep -q '상태: \*\*\[주소 오류\]\*\*' "$sf"; then
      status="주소오류"
    else
      continue
    fi
    id=$(field "$sf" "기업 식별자")
    ts=$(field "$sf" "발송일시")
    [[ -z "$id" || -z "$ts" ]] && continue
    if ls "$SPECS_DIR"/원인분석/"${id}-${ts}"*.md >/dev/null 2>&1; then
      continue
    fi
    # "판정 근거" 열은 표 헤더에도 나오므로 헤더가 아니라 회차 번호로 시작하는
    # 마지막 데이터 행(가장 최근 회차)에서 4번째 칸만 뽑는다.
    reason=$(grep -E '^\| [0-9]+ \|' "$sf" | tail -1 | awk -F'|' '{gsub(/^ +| +$/,"",$5); print $5}')
    payload=$(jq -n --arg sr "${id}-${ts}" --arg st "$status" --arg r "${reason:-판정 근거 미상}" \
      '{send_record: $sr, g6_status: $st, reason: $r}')
    log "H10 조건 충족 — ${id}-${ts} (${status}, 원인분석 미실행) -> dispatch"
    echo "$payload" | bash "$HOOKS_DIR/hook_h10_g8_cause_analysis_trigger.sh"
  done
}

# ============================================================
# H11 — G9 위임 브리프 생성 (실제 자리: 주 1회 배치. 여기서는 contacts/*.md
# 중 [미확보]인데 대응 위임브리프 파일이 아직 없는 건을 모아 한 번에 부른다.
# G8 재시도가치 高(경로2)는 이 폴러가 판정하지 않는다 — G8 산출물을 그대로
# 읽어야 하는데, 지금 저장소엔 재시도가치 高로 확정된 원인분석 파일이 아직
# 없어 대상이 없다.)
# ============================================================
poll_h11() {
  log "-- H11 위임 브리프 생성 점검(경로1만, 경로2는 대상 없음) --"
  local cf id items="[]" item
  for cf in "$SPECS_DIR"/contacts/*.md; do
    [[ -f "$cf" ]] || continue
    grep -qE '상태: \[미확보\]' "$cf" || continue
    id=$(field "$cf" "기업 식별자")
    [[ -z "$id" ]] && continue
    [[ -f "$SPECS_DIR/위임브리프/${id}.md" ]] && continue
    if [[ ! -f "$SPECS_DIR/scores/${id}.md" ]]; then
      log "H11 스킵 — ${id} (G3 채점 파일 없음 — g9-위임브리프 2번 게이트에서 어차피 되돌아간다)"
      continue
    fi
    item=$(jq -n --arg c "$id" '{company_id: $c, path: "경로1"}')
    items=$(echo "$items" | jq --argjson it "$item" '. + [$it]')
  done
  count=$(echo "$items" | jq 'length')
  if [[ "$count" -gt 0 ]]; then
    log "H11 조건 충족 — 대상 ${count}건 -> dispatch"
  else
    log "H11 — 대상 0건(스크립트 자체가 0건이면 건너뛴다)"
  fi
  echo "$items" | bash "$HOOKS_DIR/hook_h11_g9_brief_generation_cycle.sh"
}

# ============================================================
# 다루지 않는 것 — H1, H5
# H1(회신 도착 감지): 원문 메일이 도착하는 실제 수신함이 이 저장소 어디에도
#   없다(specs/replies/는 이미 G7이 처리한 "이후" 산출물이다). 없는 수신함을
#   있는 척 지어내지 않는다 — 실제 메일 인프라가 붙기 전까지 정직하게 대상 없음.
# H5(G1 주간 재발굴): "이번 주 신규 후보 소스"(어느 사이트를 볼지)는 실제
#   리드 발굴 활동의 결과물이라 파일 상태 스캔으로 대신할 수 없다. 빈 리드
#   큐를 사람이 채워 주면 그 다음부터는 hook_h05.sh 자체가 0건 게이트를 이미
#   갖고 있다.
# ============================================================
log "-- H1·H5는 이 폴러가 감지하지 않음(실제 원천 데이터 없음, 위 주석 참조) --"

poll_h3
poll_h4
poll_h2
poll_h6
poll_h7
poll_h8
poll_h10
poll_h11

log "=== 폴링 종료 ==="
echo "폴링 완료 — 로그: ${POLL_LOG}"
