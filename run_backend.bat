@echo off
chcp 65001 > nul
echo ========================================================
echo [GrassToucher] Khoi chay Backend FastAPI (Uvicorn Server)
echo 100% Ma nguon mo (Open Source / Apache-2.0 License)
echo ========================================================
echo Swagger UI: http://localhost:8000/docs
echo Health Check: http://localhost:8000/api/health
echo ========================================================
if exist venv\Scripts\python.exe (
    venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
) else if exist ..\venv\Scripts\python.exe (
    ..\venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
) else (
    python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
)
pause
