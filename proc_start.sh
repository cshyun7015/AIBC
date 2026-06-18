#!/bin/bash

# ==========================================
# AntiGravity ITSM Agent - Local Start Script
# ==========================================

echo "🚀 Starting AIBC Local Processes..."

# 1. Start Backend (FastAPI)
echo "▶️ Starting Backend..."
cd backend || exit

echo "📦 Installing backend dependencies..."
pip install --no-cache-dir -r requirements.txt

# 백그라운드 실행 및 로그 저장
nohup uvicorn app.main:app --host 0.0.0.0 --port 8000 > backend.log 2>&1 &
echo $! > backend.pid
echo "✅ Backend started (PID: $(cat backend.pid), Log: backend/backend.log)"
cd ..

# 2. Start Frontend (Vite/React)
echo "▶️ Starting Frontend..."
cd frontend || exit
# 백그라운드 실행 및 로그 저장
nohup npm run dev > frontend.log 2>&1 &
echo $! > frontend.pid
echo "✅ Frontend started (PID: $(cat frontend.pid), Log: frontend/frontend.log)"
cd ..

echo ""
echo "🎉 All processes have been started locally!"
echo "- Backend API: http://localhost:8000"
echo "- Frontend UI: http://localhost:5173 (기본 설정 시)"
echo "종료하려면 ./proc_stop.sh 를 실행하세요."
