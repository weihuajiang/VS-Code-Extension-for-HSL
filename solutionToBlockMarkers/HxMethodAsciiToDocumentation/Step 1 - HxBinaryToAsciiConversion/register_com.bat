@echo off
REM Test script for HxCfgFileConverter COM Class

echo ================================================
echo HxCfgFileConverter COM Class Test
echo ================================================
echo.

REM Check if running as administrator
net session >nul 2>&1
if %errorLevel% == 0 (
    echo Running as Administrator: YES
) else (
    echo Running as Administrator: NO
    echo NOTE: COM registration requires administrator privileges
)
echo.

REM Set the path to the built DLL
set DLL_PATH=%~dp0bin\Debug\net48\HxCfgFilConverter.dll

REM Check if the DLL exists
if not exist "%DLL_PATH%" (
    echo ERROR: Unable to find HxCfgFilConverter.dll
    echo Expected location: %DLL_PATH%
    echo Please build the project first.
    pause
    exit /b 1
)

echo Found DLL: %DLL_PATH%
echo.

REM Register the COM class
echo Registering COM class...
"%SystemRoot%\Microsoft.NET\Framework\v4.0.30319\regasm.exe" /codebase "%DLL_PATH%"

if %errorLevel% == 0 (
    echo.
    echo ================================================
    echo COM Registration Successful!
    echo ================================================
    echo.
    echo You can now use the COM class with:
    echo   ProgID: HxCfgFilConverter.HxCfgFileConverterCOM
    echo.
    echo Test the COM class by running: test_com_class.ps1
    echo.
) else (
    echo.
    echo ERROR: COM registration failed
    echo Make sure you are running this script as Administrator
    echo.
)

pause
