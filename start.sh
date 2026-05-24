#!/bin/bash

# .env 파일이 없으면 .env.example을 복사해서 생성 안내
if [ ! -f .env ]; then
    echo "⚠️ .env 파일이 없습니다. .env.example을 복사하여 .env 파일을 생성합니다."
    cp .env.example .env
    echo "👉 .env 파일을 열어 AZURE_OPENAI_API_KEY와 ENDPOINT를 실제 값으로 수정해주세요!"
    exit 1
fi

echo "🚀 AIBC Agent 컨테이너 빌드 및 백그라운드 실행을 시작합니다..."
docker-compose up --build -d

echo "✅ 실행 완료!"
echo "🌐 Frontend (UI) 접속: http://localhost"
echo "🔌 Backend (API) 접속: http://localhost:8000"
echo "로그를 보시려면 'docker-compose logs -f' 를 입력하세요."
