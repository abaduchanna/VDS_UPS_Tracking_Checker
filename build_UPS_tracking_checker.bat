@echo off
setlocal enabledelayedexpansion
title Build UPS_tracking_checker.spec

set "SRCDIR=%~dp0"
set "OUTDIR=%USERPROFILE%\Downloads\GitHub"

echo.
echo  ============================================================
echo   Building: UPS_tracking_checker.spec
echo  ============================================================
echo.

REM ── Check prerequisites ──
python --version >nul 2>&1
if errorlevel 1 (
    echo    ERROR: Python not found in PATH.
    pause
    exit /b 1
)
python -m PyInstaller --version >nul 2>&1
if errorlevel 1 (
    echo    PyInstaller not found. Installing...
    python -m pip install --upgrade pyinstaller
)
git --version >nul 2>&1
if errorlevel 1 (
    echo    ERROR: Git not found in PATH.
    pause
    exit /b 1
)
echo    Prerequisites OK
echo.

REM ── Redirect PyInstaller workpath to system TEMP ──
set "WORKBASE=%TEMP%\pyi_build\UPS_tracking_checker"
if exist "%WORKBASE%" rmdir /s /q "%WORKBASE%"
mkdir "%WORKBASE%" 2>nul
echo    Workpath: %WORKBASE%
echo.

REM ── Enter folder + clean ──
pushd "%SRCDIR%"
if exist "build" rmdir /s /q "build"
if exist "dist"  rmdir /s /q "dist"
if exist "__pycache__" rmdir /s /q "__pycache__"
del /s /q *.pyc 2>nul

REM ── Install deps ──
if exist "requirements.txt" (
    echo  Installing requirements...
    python -m pip install -r requirements.txt --quiet 2>nul
)

REM ── Build ──
echo  Building UPS_tracking_checker.spec...
python -m PyInstaller "UPS_tracking_checker.spec" --noconfirm --clean --workpath "%WORKBASE%" 2>&1

if errorlevel 1 (
    echo    FAILED: UPS_tracking_checker.spec
    popd
    pause
    exit /b 1
)

echo    SUCCESS: UPS_tracking_checker.spec

REM ── Copy .exe to output ──
set "EXENAME=UPS_tracking_checker.exe"
if exist "dist\!EXENAME!" (
    if not exist "%OUTDIR%" mkdir "%OUTDIR%"
    copy /Y "dist\!EXENAME!" "%OUTDIR%\!EXENAME!" >nul
    echo    Collected: %OUTDIR%\!EXENAME!
) else (
    echo    WARNING: dist\!EXENAME! not found
)

popd

echo.
echo  ============================================================
echo   Done: UPS_tracking_checker.spec
echo  ============================================================
echo.
pause
endlocal
exit /b 0
