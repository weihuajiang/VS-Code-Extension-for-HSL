@echo off
REM Setup Converter - Copy files from Step 1 build to converter_bin

echo =========================================
echo Method to Documentation - Converter Setup
echo =========================================
echo.

set SOURCE_DIR=..\Step 1 - HxBinaryToAsciiConversion\bin\Debug\net48
set DEST_DIR=.\converter_bin

echo Checking for source directory...
if not exist "%SOURCE_DIR%" (
    echo ERROR: Source directory not found!
    echo Expected: %SOURCE_DIR%
    echo.
    echo Please build the Step 1 project first:
    echo 1. Open: Step 1 - HxBinaryToAsciiConversion\config file extract.sln
    echo 2. Build the solution in Visual Studio
    echo 3. Run this script again
    echo.
    pause
    exit /b 1
)

echo Source directory found: %SOURCE_DIR%
echo.

echo Checking for HxCfgFilConverter.exe...
if not exist "%SOURCE_DIR%\HxCfgFilConverter.exe" (
    echo ERROR: HxCfgFilConverter.exe not found in source directory!
    echo Please build the project first.
    echo.
    pause
    exit /b 1
)

echo Converter executable found!
echo.

echo Creating destination directory...
if not exist "%DEST_DIR%" mkdir "%DEST_DIR%"

echo Copying files...
xcopy /Y /E /I "%SOURCE_DIR%\*.*" "%DEST_DIR%\"

if %ERRORLEVEL% equ 0 (
    echo.
    echo =========================================
    echo SUCCESS! Converter setup complete.
    echo =========================================
    echo.
    echo Files copied to: %DEST_DIR%
    echo.
    echo You can now run MethodToDocumentation.py
    echo.
) else (
    echo.
    echo ERROR: Failed to copy files!
    echo Please check permissions and try again.
    echo.
)

pause
