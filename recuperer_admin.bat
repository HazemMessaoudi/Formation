@echo off
chcp 65001 >nul
title Recuperation du compte administrateur
cd /d "%~dp0"

:: v1.7 - Outil local : pose un mot de passe provisoire pour le compte
:: "moushrif 'am" (administrateur) quand il a ete oublie.
:: Le programme doit etre FERME avant de lancer cet outil.
:: 1.0 : l'outil console est RecupererAdmin.exe (le programme n'a plus de console).

if exist "RecupererAdmin.exe" (
    "RecupererAdmin.exe"
    goto fin
)
if exist "FormationKasserine.exe" (
    "FormationKasserine.exe" --recuperer-admin
    goto fin
)

where python >nul 2>&1
if %errorlevel% equ 0 (
    python recuperer_admin.py
    goto fin
)
where python3 >nul 2>&1
if %errorlevel% equ 0 (
    python3 recuperer_admin.py
    goto fin
)
echo [ERREUR] Ni RecupererAdmin.exe ni Python n'ont ete trouves dans ce dossier.

:fin
echo.
pause
