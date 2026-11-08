@echo off
chcp 65001 > nul
echo ========================================================
echo   AI 주식 분석 에이전트 v1 (AI Stock Analysis Agent v1)
echo ========================================================
echo.
echo 서버를 시작합니다... (http://localhost:8000)
echo.
.venv\Scripts\python.exe run.py
pause
