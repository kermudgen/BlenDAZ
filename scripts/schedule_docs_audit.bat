@echo off
REM BlenDAZ Documentation Audit - Scheduler Setup
REM
REM This script sets up Windows Task Scheduler to run the docs audit daily

echo ===============================================
echo BlenDAZ Documentation Audit - Setup
echo ===============================================
echo.

REM Set paths
set SCRIPT_DIR=%~dp0
set PYTHON_SCRIPT=%SCRIPT_DIR%..\scripts\audit_docs.py
set TASK_NAME=BlenDAZ_Docs_Audit

echo Script location: %PYTHON_SCRIPT%
echo.

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found in PATH
    echo Please install Python or add it to your PATH
    pause
    exit /b 1
)

echo Python found!
echo.

REM Create scheduled task
echo Creating scheduled task: %TASK_NAME%
echo This will run daily at 9:00 AM
echo.

schtasks /create /tn "%TASK_NAME%" /tr "python \"%PYTHON_SCRIPT%\"" /sc daily /st 09:00 /f

if errorlevel 1 (
    echo.
    echo ERROR: Failed to create scheduled task
    echo You may need to run this as Administrator
    pause
    exit /b 1
)

echo.
echo ===============================================
echo SUCCESS! Docs audit scheduled to run daily at 9:00 AM
echo ===============================================
echo.
echo To manage the task:
echo   - View: Task Scheduler ^> Task Scheduler Library
echo   - Run now: schtasks /run /tn "%TASK_NAME%"
echo   - Disable: schtasks /change /tn "%TASK_NAME%" /disable
echo   - Delete: schtasks /delete /tn "%TASK_NAME%" /f
echo.
echo To run manually: python "%PYTHON_SCRIPT%"
echo.

pause
