#!/bin/bash

# ==========================================
# AntiGravity ITSM Agent - Local Stop Script
# ==========================================

echo "🛑 Stopping AIBC Local Processes..."

# 1. Stop Backend
if [ -f "backend/backend.pid" ]; then
    BACKEND_PID=$(cat backend/backend.pid)
    echo "⏹️ Killing Backend (PID: $BACKEND_PID)..."
    kill $BACKEND_PID 2>/dev/null || echo "⚠️ Backend process ($BACKEND_PID) is already dead."
    rm backend/backend.pid
else
    echo "⚠️ Backend PID file not found. Is it running?"
fi

# 2. Stop Frontend
if [ -f "frontend/frontend.pid" ]; then
    FRONTEND_PID=$(cat frontend/frontend.pid)
    echo "⏹️ Killing Frontend (PID: $FRONTEND_PID)..."
    # npm run dev를 통해 실행된 자식 프로세스(Vite)까지 모두 종료하기 위해 pkill 사용을 권장할 수 있으나 기본 kill 시도
    kill $FRONTEND_PID 2>/dev/null || echo "⚠️ Frontend process ($FRONTEND_PID) is already dead."
    rm frontend/frontend.pid
    
    # npm 스크립트로 실행 시 백그라운드에 남아있는 vite 프로세스를 강제 정리
    pkill -f "vite" 2>/dev/null
else
    echo "⚠️ Frontend PID file not found. Is it running?"
fi

echo "✅ All local processes stopped!"
