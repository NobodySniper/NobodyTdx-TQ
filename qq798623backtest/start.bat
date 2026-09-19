@echo off
chcp 65001 >nul 2>&1
title 宁尚拙回测系统 V0.0.1

REM Adaptive path: bat in qq798623backtest/, cd up to user/ for tqcenter
set ROOT=%~dp0..
cd /d %ROOT%

REM Portable Python first
set PYTHON=%~dp0python\python.exe
if exist %PYTHON% goto :found

REM Fallback: system python
where python >nul 2>&1
if %errorlevel%==0 (
    set PYTHON=python
    goto :found
)

echo [ERROR] Python interpreter not found
echo Please install Python 3.12+ or add to PATH
pause
exit /b 1

:found
set PYTHONNOUSERSITE=1
echo.
echo  ============================================
echo    宁尚拙回测系统 V0.0.1 (test)
echo    Portable Edition - No Python Install Needed
echo  ============================================
echo.

%PYTHON% -m qq798623backtest.webapp.app

echo.
echo  Service stopped. Press any key to exit.
pause >nul
