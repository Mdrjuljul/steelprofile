@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

rem ============================================================
rem  SteelProfile - lanceur Windows
rem  Double-cliquez sur ce fichier pour ouvrir l'interface.
rem  Les arguments eventuels sont transmis a l'application :
rem      Lancer SteelProfile.bat --profile "IPE/IPE 200"
rem ============================================================

set "PY="
set "PYW="

rem 1) Interpreteur "python" du PATH (le plus courant).
where.exe python >nul 2>nul
if not errorlevel 1 (
    python -c "import sys" >nul 2>nul
    if not errorlevel 1 (
        set "PY=python"
        set "PYW=pythonw"
        where.exe pythonw >nul 2>nul
        if errorlevel 1 set "PYW=python"
    )
)

rem 2) Sinon, le lanceur officiel "py".
if not defined PY (
    where.exe py >nul 2>nul
    if not errorlevel 1 (
        py -3 -c "import sys" >nul 2>nul
        if not errorlevel 1 (
            set "PY=py -3"
            set "PYW=pyw -3"
        )
    )
)

if not defined PY (
    echo.
    echo Python 3 est introuvable sur cet ordinateur.
    echo.
    echo Installez-le depuis https://www.python.org/downloads/windows/
    echo en cochant "Add python.exe to PATH", puis relancez ce fichier.
    echo.
    pause
    exit /b 1
)

rem 3) Verification de PySide6 (interface uniquement).
%PY% -c "import PySide6" >nul 2>nul
if errorlevel 1 (
    echo.
    echo L'interface a besoin de PySide6, qui n'est pas installe.
    echo.
    choice /c ON /n /m "L'installer maintenant ? [O]ui / [N]on "
    if errorlevel 2 (
        echo.
        echo Installation annulee. Commande manuelle :
        echo     %PY% -m pip install PySide6
        echo.
        pause
        exit /b 1
    )
    echo.
    echo Installation de PySide6...
    %PY% -m pip install PySide6
    if errorlevel 1 (
        echo.
        echo L'installation a echoue. Verifiez votre connexion reseau.
        pause
        exit /b 1
    )
)

rem 4) Lancement sans console (pythonw) depuis le dossier du projet.
start "" %PYW% -m app.gui %*
exit /b 0
