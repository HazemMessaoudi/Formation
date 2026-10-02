@echo off
chcp 65001 >nul
title Construction de l'executable - Formation Kasserine

echo.
echo  =====================================================
echo   Construction de l'executable Windows
echo  =====================================================
echo.

cd /d "%~dp0"

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

echo [1/3] Installation des dependances...
%PYTHON% -m pip install -r requirements-lock.txt --quiet
%PYTHON% -m pip install pyinstaller==6.22.3 --quiet

echo [2/3] Nettoyage des constructions precedentes...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

echo [3/3] Construction en cours (plusieurs minutes)...
%PYTHON% -m PyInstaller formation_kasserine.spec --noconfirm

if %errorlevel% neq 0 (
    echo.
    echo [ERREUR] La construction a echoue.
    pause
    exit /b 1
)

:: v1.7 - l'outil de recuperation du compte administrateur accompagne l'exe
for %%F in (*.bat) do (
    if /i not "%%F"=="construire_exe.bat" if /i not "%%F"=="lancer.bat" copy /y "%%F" "dist\FormationKasserine\" >nul
)
:: 1.0 - installateur WebView2 (s'il est present) : installe en silence au besoin
if exist "Outils" xcopy /e /i /y /q "Outils" "dist\FormationKasserine\Outils" >nul

echo.
echo  =====================================================
echo   TERMINE
echo.
echo   Le dossier   dist\FormationKasserine\
echo   est autonome : copiez-le sur n'importe quel poste
echo   Windows et lancez FormationKasserine.exe
echo.
echo   IMPORTANT : ne copiez PAS le dossier data\ d'un
echo   poste a l'autre sauf pour transferer les donnees.
echo  =====================================================
echo.
if not "%1"=="/nopause" pause
