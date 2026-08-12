#!/bin/bash
# 발송 API 더미 — 이 저장소(라이브) 사본. 원본: Harness/api/dummy_send_api.sh
#
# 2026-08-12 — 원본과 계약은 동일하되, **바운스를 흉내낼 수 있는 입력 필드
# 하나를 추가**했다(`simulate_bounce_code`). 원본은 항상 "sent"만 반환해
# H2(바운스 감지)가 실제로 감지할 신호가 이 저장소 어디에도 없었다 — 사용자
# 지시("api 관련은 더미모듈로, 입출력 관계 맞춰서")에 따라 이 자리도 더미로
# 닫는다. 필드를 안 주면 원본과 완전히 같게 동작한다(하위 호환).
#
# 입력(stdin, JSON): {"to": "<수신 주소>", "subject": "<제목>", "body": "<본문>",
#                     "from": "<발신 주소, 미확보면 빈 문자열>",
#                     "simulate_bounce_code": "<선택 — 5xx/4xx 코드, 없으면 정상 발송>"}
# 출력(stdout, JSON):
#   정상: {"status": "sent", "message_id": "dummy-<타임스탬프>", "sent_at": "<ISO 8601>"}
#   바운스: {"status": "bounced", "bounce_code": "<코드>", "message_id": "dummy-<타임스탬프>", "sent_at": "<ISO 8601>"}
#
# 실제 API가 붙으면 이 스크립트를 그 API 호출로 바꿔치기하면 된다 — 이
# 입출력 계약만 지키면 g5-제안메일제작발송·dummy_platform_poll.sh의 호출부는
# 안 바뀐다(연결 문제인지 구조 문제인지 이 계약으로 가른다).
#
# 의존: jq.

input=$(cat)
log_dir="$(dirname "$0")/_logs"
mkdir -p "$log_dir"
log_file="${log_dir}/api-send.log"
now=$(date -u +"%Y-%m-%dT%H:%M:%SZ" 2>/dev/null || echo "(시각 미상)")

to=$(echo "$input" | jq -r '.to // empty')
subject=$(echo "$input" | jq -r '.subject // empty')
from=$(echo "$input" | jq -r '.from // empty')
bounce_code=$(echo "$input" | jq -r '.simulate_bounce_code // empty')

echo "[$now] RECEIVED send-request to=${to:-?} subject=${subject:-?} from=${from:-(미확보)} simulate_bounce_code=${bounce_code:-(없음)}" >> "$log_file"

if [[ -z "$to" || -z "$subject" ]]; then
  echo "[$now] REJECTED — to 또는 subject 없음" >> "$log_file"
  echo '{"status":"error","reason":"to 또는 subject 누락"}'
  exit 1
fi

message_id="dummy-$(date +%s 2>/dev/null || echo 0)"

if [[ -n "$bounce_code" ]]; then
  echo "[$now] BOUNCED(dummy) to=${to} message_id=${message_id} bounce_code=${bounce_code} reflected=아니오" >> "$log_file"
  echo "{\"status\":\"bounced\",\"bounce_code\":\"${bounce_code}\",\"message_id\":\"${message_id}\",\"sent_at\":\"${now}\"}"
  exit 0
fi

echo "[$now] SENT(dummy) to=${to} message_id=${message_id}" >> "$log_file"
echo "{\"status\":\"sent\",\"message_id\":\"${message_id}\",\"sent_at\":\"${now}\"}"
exit 0
