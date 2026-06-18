#!/bin/bash

# ==========================================
# AntiGravity ITSM Agent - API Test Script (cURL)
# ==========================================

API_URL="http://localhost:8000/api/v1/analyze-incident"
IMAGE_API_URL="http://localhost:8000/api/v1/graph-image"
INCIDENT_MSG="요청 등록 후 조회 시 500 에러 발생"

# 실행 시 인자를 넘기면 해당 메시지로 테스트 가능
if [ ! -z "$1" ]; then
  INCIDENT_MSG="$1"
fi

echo "🚀 1. 인시던트 분석 API 테스트 시작..."
echo "▶️ 요청 주소: $API_URL"
echo "▶️ 요청 데이터: {\"incident_report\": \"$INCIDENT_MSG\"}"
echo "------------------------------------------------"

# curl 실행
RESPONSE=$(curl -s -X POST "$API_URL" \
  -H "Content-Type: application/json" \
  -d "{\"incident_report\": \"$INCIDENT_MSG\", \"thread_id\": \"test-session-1\"}")

echo "📥 분석 결과:"
# 시스템에 jq가 설치되어 있다면 JSON을 예쁘게 포맷팅하여 출력
if command -v jq &> /dev/null; then
    echo "$RESPONSE" | jq .
else
    echo "$RESPONSE"
fi
echo "------------------------------------------------"

echo ""
echo "🚀 2. 워크플로우 이미지 서빙 API 상태 확인..."
echo "▶️ 요청 주소: $IMAGE_API_URL"
# -I 옵션으로 헤더만 가져와서 HTTP 상태 코드 확인
HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$IMAGE_API_URL")

if [ "$HTTP_STATUS" -eq 200 ]; then
    echo "✅ 이미지 응답 정상 (HTTP 200 OK)"
else
    echo "⚠️ 이미지 응답 오류 (HTTP $HTTP_STATUS)"
fi
echo "------------------------------------------------"
echo "🎉 모든 테스트 완료!"
