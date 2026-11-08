@echo off
cd /d "%~dp0"
chcp 65001 > nul

echo ========================================================
echo   AI 주식 분석 에이전트 - 깃허브 안전 업로드
echo ========================================================
echo.
echo 현재 폴더: %cd%
echo 저장소 주소: https://github.com/ldkdream1/Stock_Note.git
echo.
set /p TOKEN="발급받으신 토큰(ghp_...)을 입력하세요: "

:: 따옴표 제거
set TOKEN=%TOKEN:"=%

if "%TOKEN%"=="" (
    echo [경고] 토큰이 입력되지 않았습니다.
    pause
    exit /b
)

echo.
echo [진행 중] 깃허브로 업로드하고 있습니다... 잠시만 기다려주세요.
echo.

git push https://%TOKEN%@github.com/ldkdream1/Stock_Note.git main

if %errorlevel% equ 0 (
    echo.
    echo ========================================================
    echo  [성공!] 깃허브에 코드가 성공적으로 업로드되었습니다!
    echo  확인: https://github.com/ldkdream1/Stock_Note
    echo ========================================================
) else (
    echo.
    echo --------------------------------------------------------
    echo [실패] 위 에러 내용을 확인해주세요.
    echo 토큰 값(ghp_...)이 정확한지 확인하시기 바랍니다.
    echo --------------------------------------------------------
)

echo.
pause
