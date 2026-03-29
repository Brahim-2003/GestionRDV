@echo off
setlocal EnableDelayedExpansion

cd /d "C:\Users\A1\Documents\Brahim\Mon Projet\GestionRDV"

set LOGFILE=git_logs.txt
set BACKUP_DIR=backups

:: Créer dossier backup si inexistant
if not exist "%BACKUP_DIR%" mkdir "%BACKUP_DIR%"

:menu
cls
echo ==========================
echo   🚀 Gestion Git PRO
echo ==========================
echo.
echo 1. 🔄 Pull
echo 2. 📤 Commit + Push
echo 3. 💾 Backup + Push AUTO
echo 4. 📜 Voir logs
echo 5. ❌ Quitter
echo.

set /p choix="Choix (1-5): "

if "%choix%"=="1" goto pull
if "%choix%"=="2" goto push
if "%choix%"=="3" goto autopush
if "%choix%"=="4" goto showlog
if "%choix%"=="5" exit /b

goto menu

:: ==========================
:pull
echo 🔄 Pull en cours...
git pull origin main --rebase --autostash

if errorlevel 1 (
    echo ❌ Erreur pull
    echo [%date% %time%] PULL FAILED >> %LOGFILE%
) else (
    echo ✅ Pull OK
    echo [%date% %time%] PULL OK >> %LOGFILE%
)

pause
goto menu

:: ==========================
:push
echo 📤 Commit + Push...

git add .

set /p commit_msg="Message commit (laisser vide = auto): "

if "%commit_msg%"=="" (
    set commit_msg=Update automatique %date% %time%
)

git commit -m "%commit_msg%"

if errorlevel 1 (
    echo ⚠️ Rien à commit
    pause
    goto menu
)

git push origin main

if errorlevel 1 (
    echo ❌ Push échoué
    echo [%date% %time%] PUSH FAILED >> %LOGFILE%
) else (
    echo ✅ Push OK
    echo [%date% %time%] PUSH OK - %commit_msg% >> %LOGFILE%
)

pause
goto menu

:: ==========================
:autopush
echo 💾 Backup + Push automatique...

:: Générer timestamp
set TIMESTAMP=%date:/=-%_%time::=-%
set TIMESTAMP=%TIMESTAMP: =%

:: Backup DB
if exist db.sqlite3 (
    copy db.sqlite3 "%BACKUP_DIR%\db_%TIMESTAMP%.sqlite3" >nul
)

:: Backup JSON Django (optionnel)
python manage.py dumpdata > "%BACKUP_DIR%\data_%TIMESTAMP%.json"

echo ✅ Backup terminé

:: Commit + Push auto
git add .

git commit -m "🔄 Backup auto %TIMESTAMP%" >nul 2>&1

git push origin main

if errorlevel 1 (
    echo ❌ Push échoué
    echo [%date% %time%] AUTO PUSH FAILED >> %LOGFILE%
) else (
    echo ✅ Backup + Push OK
    echo [%date% %time%] AUTO PUSH OK >> %LOGFILE%
)

pause
goto menu

:: ==========================
:showlog
cls
if exist "%LOGFILE%" (
    type "%LOGFILE%"
) else (
    echo Aucun log disponible
)
pause
goto menu