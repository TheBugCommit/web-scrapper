@echo off
echo ===================================================
echo   Web Scrapper - Execucio Diaria
echo ===================================================
echo.

:: Canviar al directori on esta aquest script
cd /d "%~dp0"

:: Definir l'entorn com a produccio per defecte quan s'executa via .bat
set APP_ENV=prod

:: Comprovar que existeix l'entorn virtual
if not exist ".venv\Scripts\activate.bat" (
    echo [ERROR] No s'ha trobat l'entorn virtual. Executa install.bat primer.
    pause
    exit /b 1
)

:: Activar entorn virtual
call .venv\Scripts\activate.bat

:: Executar l'scraper de tots els portals i redirigir sortida a log
echo [%date% %time%] Iniciant execucio de portals...
echo [%date% %time%] Iniciant execucio de portals... >> scraper_cron.log

:: Executa l'script, stdout i stderr van al fitxer de log
python portals/run.py --all >> scraper_cron.log 2>&1

if %errorlevel% neq 0 (
    echo [%date% %time%] [ERROR] Hi ha hagut problemes durant l'execucio. Revisa scraper_cron.log
    echo [%date% %time%] [ERROR] Execucio finalitzada amb errors. >> scraper_cron.log
) else (
    echo [%date% %time%] [OK] Execucio completada amb exit.
    echo [%date% %time%] [OK] Execucio completada amb exit. >> scraper_cron.log
)

:: Desactivar entorn virtual
deactivate
