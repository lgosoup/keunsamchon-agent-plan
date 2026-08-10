#!/bin/bash
# 발송 API 더미 — 실제 메일 발송 인프라(팀원이 연동 중)가 붙기 전까지
# g5-proposal-email-dispatch의 발송 호출 자리를 대신한다.
#
# 실제 자리: skills/g5-proposal-email-dispatch/SKILL.md 발송 모드 "4. 발송한다"
# — 발송 기록 파일(data/발송기록/{기업식별자}-{발송일시}.md)을 쓰기 직전.
# 지금은 그 발송 기록 파일 쓰기 자체가 "발송"의 대역이고(specs/README.md
# "발송 도메인 준비" 절), 이 스크립트는 그 앞 단계 — 실제 메일 발송
# API/서비스 호출 하나가 들어갈 자리 — 를 흉내만 낸다. 실제 발송·수신 결과를
# 만들지 않는다. 실제 API가 붙으면 이 스크립트를 그 API 호출로 그대로
# 바꿔치기하면 된다 — 입출력 계약(아래)만 지키면 호출부는 안 바뀐다.
#
# 입력(stdin, JSON): {"to": "<수신 주소>", "subject": "<제목>", "body": "<본문>",
#                     "from": "<발신 주소, 미확보면 빈 문자열>"}
# 출력(stdout, JSON): {"status": "sent", "message_id": "dummy-<타임스탬프>",
#                      "sent_at": "<ISO 8601>"}
#
# 의존: jq.

input=$(cat)
log_dir="$(dirname "$0")/../data/hook로그"
mkdir -p "$log_dir"
log_file="${log_dir}/api-send.log"
now=$(date -u +"%Y-%m-%dT%H:%M:%SZ" 2>/dev/null || echo "(시각 미상)")

to=$(echo "$input" | jq -r '.to // empty')
subject=$(echo "$input" | jq -r '.subject // empty')
from=$(echo "$input" | jq -r '.from // empty')

echo "[$now] RECEIVED send-request to=${to:-?} subject=${subject:-?} from=${from:-(미확보)}" >> "$log_file"

if [[ -z "$to" || -z "$subject" ]]; then
  echo "[$now] REJECTED — to 또는 subject 없음" >> "$log_file"
  echo '{"status":"error","reason":"to 또는 subject 누락"}'
  exit 1
fi

message_id="dummy-$(date +%s 2>/dev/null || echo 0)"
echo "[$now] SENT(dummy) to=${to} message_id=${message_id}" >> "$log_file"

echo "{\"status\":\"sent\",\"message_id\":\"${message_id}\",\"sent_at\":\"${now}\"}"
exit 0
