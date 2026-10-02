@echo off
chcp 65001 >nul

:: === نظام إدارة التكوين الديواني - القصرين ===
:: Lancement depuis les sources (Python). L'executable, lui, se lance par
:: FormationKasserine.exe. 1.0 : le programme s'ouvre dans SA fenetre
:: (a defaut Edge en mode application, puis le navigateur).

set "APP_DIR=%~dp0"
cd /d "%APP_DIR%"

echo.
echo  =====================================================
echo   Systeme de Gestion de la Formation - Kasserine
echo  =====================================================
echo.

:: 1.0 : choisir le meilleur Python installe (3.12 d'abord ; 3.10 a 3.14).
set PYTHON=
for %%V in (3.12 3.13 3.11 3.10 3.14) do (
    if not defined PYTHON (
        py -%%V -c "import sys" >nul 2>&1 && set "PYTHON=py -%%V"
    )
)
if not defined PYTHON (
    python -c "import sys; sys.exit(0 if (3,10) <= sys.version_info[:2] <= (3,14) else 1)" >nul 2>&1 && set PYTHON=python
)
if not defined PYTHON (
    echo [ERREUR] Python 3.10 a 3.14 introuvable. Installez Python 3.12
    echo https://www.python.org/downloads/
    pause
    exit /b 1
)
echo [OK] Python : %PYTHON%

%PYTHON% -c "import flask, waitress, reportlab, arabic_reshaper, bidi, PIL, openpyxl, xlrd, webview" >nul 2>&1
if %errorlevel% neq 0 (
    echo [!] Installation des bibliotheques requises...
    %PYTHON% -m pip install -r requirements-lock.txt --quiet
    if %errorlevel% neq 0 (
        echo [ERREUR] Echec de l'installation. Verifiez la connexion internet.
        pause
        exit /b 1
    )
    echo [OK] Bibliotheques installees
) else (
    echo [OK] Bibliotheques presentes
)

echo.
echo [OK] Demarrage... (journal : data\logs\lanceur.log)
echo  Pour arreter : fermez la fenetre du programme.
echo.

%PYTHON% lancer_app.py
