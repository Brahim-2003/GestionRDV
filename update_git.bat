@echo off
REM === Script pour mettre à jour le projet sur GitHub ===

cd /d C:\Users\A1\Documents\Brahim\Mon Projet\GestionRDV

echo ==========================
echo   Synchronisation GitHub
echo ==========================

REM 1. Récupérer les changements distants
git pull origin main --rebase

REM 2. Ajouter tous les fichiers modifiés
git add .

REM 3. Demander un message de commit à l'utilisateur
set /p commit_msg="Entrez un message pour le commit: "

REM 4. Faire le commit
git commit -m "%commit_msg%"

REM 5. Envoyer les changements sur GitHub
git push origin main

echo ==========================
echo   Projet mis à jour !
echo ==========================

pause
