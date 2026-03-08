#!/bin/bash
# OpenClaw Trading System 시작 스크립트

set -e

echo "🦅 OpenClaw Trading System 시작"
echo "=================================="

# .env 파일 확인
if [ ! -f ".env" ]; then
    echo "⚠️  .env 파일이 없습니다. env.example에서 복사합니다..."
    cp env.example .env
    echo "✅ .env 파일 생성 완료. 실제 값으로 수정해주세요!"
fi

# 백엔드 의존성 설치 및 실행
start_backend() {
    echo ""
    echo "🔧 백엔드 시작 중..."
    cd backend

    # 가상환경 생성 (없으면)
    if [ ! -d "venv" ]; then
        echo "   Python 가상환경 생성..."
        python3 -m venv venv
    fi

    # 가상환경 활성화
    source venv/bin/activate

    # 의존성 설치
    echo "   의존성 설치..."
    pip install -r requirements.txt -q

    echo "   백엔드 서버 시작 (http://localhost:8000)"
    python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload &
    BACKEND_PID=$!
    echo "   PID: $BACKEND_PID"
    cd ..
}

# 프론트엔드 의존성 설치 및 실행
start_frontend() {
    echo ""
    echo "🎨 프론트엔드 시작 중..."
    cd frontend

    if [ ! -d "node_modules" ]; then
        echo "   npm 패키지 설치..."
        npm install
    fi

    echo "   프론트엔드 서버 시작 (http://localhost:3000)"
    npm run dev &
    FRONTEND_PID=$!
    echo "   PID: $FRONTEND_PID"
    cd ..
}

# 시작
start_backend
sleep 3
start_frontend

echo ""
echo "=================================="
echo "✅ OpenClaw Trading System 실행 중!"
echo ""
echo "   🌐 대시보드:  http://localhost:3000"
echo "   📡 API:      http://localhost:8000"
echo "   📚 API 문서: http://localhost:8000/docs"
echo ""
echo "   ⚠️  페이퍼트레이딩 모드 (안전)"
echo ""
echo "   종료: Ctrl+C"
echo "=================================="

# 종료 시 자식 프로세스 정리
trap "echo '종료 중...'; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit 0" SIGINT SIGTERM

wait
