@echo off
REM Launch the Method to Documentation application

echo Starting Method to Documentation Generator...
echo.

REM Check if Python is available
python --version >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.8 or higher
    echo Download from: https://www.python.org/downloads/
    pause
    exit /b 1
)

REM Check if the main script exists
if not exist "MethodToDocumentation.py" (
    echo ERROR: MethodToDocumentation.py not found
    echo Make sure you're running this from the correct directory
    pause
    exit /b 1
)

REM Launch the application
python MethodToDocumentation.py

pause
