@echo off
REM === Gestion GitHub pour le projet Django avec logs ===

cd /d C:\Users\A1\Documents\Brahim\Mon Projet\GestionRDV

set LOGFILE=git_logs.txt

:menu
cls
echo ==========================
echo   Gestion GitHub - Projet
echo ==========================
echo.
echo 1. Pull (récupérer les changements distants)
echo 2. Commit + Push (envoyer mes changements)
echo 3. Voir le journal Git local
echo 4. Quitter
echo.
set /p choix="Choix (1/2/3/4): "

if "%choix%"=="1" goto pull
if "%choix%"=="2" goto push
if "%choix%"=="3" goto showlog
if "%choix%"=="4" exit
goto menu

:pull
echo ==========================
echo   🔄 Pull depuis GitHub
echo ==========================
git pull origin main --rebase
echo [%date% %time%] PULL effectue >> %LOGFILE%
echo ✅ Pull terminé ! Voir %LOGFILE%
pause
goto menu

:push
echo ==========================
echo   📤 Commit + Push
echo ==========================
git add .
set /p commit_msg="Entrez un message pour le commit: "
git commit -m "%commit_msg%"
git push origin main
echo [%date% %time%] PUSH effectue - Message: %commit_msg% >> %LOGFILE%
echo ✅ Commit + Push terminé ! Voir %LOGFILE%
pause
goto menu

:showlog
echo ==========================
echo   📜 Journal des actions
echo ==========================
type %LOGFILE%
pause
goto menu
