@echo off
REM Register Hamilton HxCfgFil COM object
REM Run this as Administrator

echo Registering Hamilton HxCfgFil.dll for COM...
echo.

set DLL_PATH=C:\Program Files (x86)\Hamilton\Bin\HxCfgFil.dll

if not exist "%DLL_PATH%" (
    echo ERROR: DLL not found at: %DLL_PATH%
    echo.
    echo Please verify Hamilton software is installed.
    pause
    exit /b 1
)

echo DLL found: %DLL_PATH%
echo.
echo Registering...
regsvr32 /s "%DLL_PATH%"

if %ERRORLEVEL% EQU 0 (
    echo.
    echo SUCCESS! Hamilton COM object registered.
    echo You can now use the Method to Documentation app.
) else (
    echo.
    echo FAILED! Error code: %ERRORLEVEL%
    echo.
    echo Make sure you are running this as Administrator:
    echo Right-click this file and select "Run as administrator"
)

echo.
pause
