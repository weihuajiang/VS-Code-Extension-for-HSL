@echo off
REM Check if COM dependencies are available

echo.
echo ========================================
echo COM Availability Check
echo ========================================
echo.

echo Checking Python installation...
python --version
if %ERRORLEVEL% neq 0 (
    echo ERROR: Python not found!
    pause
    exit /b 1
)

echo.
echo Checking pywin32 installation...
python -c "import win32com.client; print('✓ pywin32 is installed')" 2>nul
if %ERRORLEVEL% neq 0 (
    echo ✗ pywin32 is NOT installed
    echo.
    echo Install it with:
    echo   pip install pywin32
    echo.
    pause
    exit /b 1
)

echo.
echo Checking Hamilton COM object...
python -c "import win32com.client; win32com.client.GetObject('new:{F4B19511-207B-11D1-8C7D-004095E12BC7}'); print('✓ Hamilton COM object is available')" 2>nul
if %ERRORLEVEL% neq 0 (
    echo ⚠ Hamilton COM object not found
    echo.
    echo Possible solutions:
    echo 1. Install Hamilton software
    echo 2. Register COM components
    echo.
    echo The application may still work if Hamilton is installed.
    echo.
)

echo.
echo ========================================
echo All checks complete!
echo ========================================
echo.

pause
