@echo off
:: ============================================================
::  BUILD SCRIPT — AutomationApp.exe
::  Double-click this file OR run it in Command Prompt.
:: ============================================================

title AutomationApp — EXE Builder
color 0A
echo.
echo  ============================================================
echo   AutomationApp EXE Builder
echo  ============================================================
echo.

:: ── 1. Check Python is installed ────────────────────────────
python --version >nul 2>&1
if errorlevel 1 (
    echo  [ERROR] Python is NOT installed or not on PATH.
    echo  Please install Python 3.9+ from https://www.python.org/downloads/
    echo  Make sure to check "Add Python to PATH" during installation.
    echo.
    pause
    exit /b 1
)

for /f "tokens=*" %%i in ('python --version') do set PYVER=%%i
echo  [OK] Found %PYVER%
echo.

:: ── 2. Upgrade pip ───────────────────────────────────────────
echo  [1/6] Upgrading pip...
python -m pip install --upgrade pip --quiet
echo  [OK] pip is up to date.
echo.

:: ── 3. Install dependencies ──────────────────────────────────
echo  [2/6] Installing dependencies from requirements.txt...
pip install -r requirements.txt --quiet
if errorlevel 1 (
    echo  [ERROR] Failed to install dependencies.
    pause
    exit /b 1
)
echo  [OK] Dependencies installed.
echo.

:: ── 4. Install PyInstaller ───────────────────────────────────
echo  [3/6] Installing PyInstaller...
pip install pyinstaller --quiet
echo  [OK] PyInstaller ready.
echo.

:: ── 5. Clean previous build ──────────────────────────────────
echo  [4/6] Cleaning previous build...
if exist "build"  rmdir /s /q "build"
if exist "dist"   rmdir /s /q "dist"
echo  [OK] Clean done.
echo.

:: ── 6. Build the EXE ────────────────────────────────────────
echo  [5/6] Building AutomationApp.exe — this may take 1-3 minutes...
echo.
pyinstaller automation_app.spec --noconfirm --clean
echo.

if errorlevel 1 (
    echo  ============================================================
    echo  [FAILED] Build encountered errors. See output above.
    echo  ============================================================
    pause
    exit /b 1
)

:: ── 7. Copy JSON files beside the EXE ───────────────────────
echo  [6/6] Copying config files into dist\...
copy /Y "config.json"          "dist\config.json"          >nul
copy /Y "custom_patterns.json" "dist\custom_patterns.json" >nul
echo  [OK] JSON files copied.
echo.

:: ── 8. Done ─────────────────────────────────────────────────
echo  ============================================================
echo  [SUCCESS] Build complete!
echo.
echo  dist\ folder contains:
echo    AutomationApp.exe
echo    config.json
echo    custom_patterns.json
echo.
echo  Share the entire dist\ folder with end users.
echo  They can edit the JSON files freely — changes are permanent.
echo  ============================================================
echo.

explorer dist
pause