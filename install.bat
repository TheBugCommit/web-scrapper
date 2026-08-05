@echo off
echo ===================================================
echo   Web Scrapper - Instal.lacio i Preparacio
echo ===================================================
echo.

:: Canviar al directori on esta aquest script
cd /d "%~dp0"

echo 1. Creant entorn virtual (.venv)...
python -m venv .venv
if %errorlevel% neq 0 (
    echo [ERROR] No s'ha pogut crear l'entorn virtual. Tens Python instal.lat i al PATH?
    pause
    exit /b %errorlevel%
)

echo.
echo 2. Activant entorn virtual i instal.lant dependencies...
call .venv\Scripts\activate.bat
pip install -e .
if %errorlevel% neq 0 (
    echo [ERROR] No s'han pogut instal.lar les dependencies.
    pause
    exit /b %errorlevel%
)

echo.
echo 3. Instal.lant Playwright (Navegadors)...
playwright install chromium
if %errorlevel% neq 0 (
    echo [ERROR] No s'ha pogut instal.lar Playwright.
    pause
    exit /b %errorlevel%
)

echo.
echo ===================================================
echo [OK] Instal.lacio completada amb exit!
echo ===================================================
pause
