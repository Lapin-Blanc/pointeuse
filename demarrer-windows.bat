@echo off
chcp 65001 > nul
title Pointage Max
cd /d "%~dp0"
where py > nul 2>&1 && (set PY=py -3) || (set PY=python)
%PY% --version > nul 2>&1 || (
  echo Python n'est pas installe. Installez-le depuis https://www.python.org/downloads/
  echo en cochant "Add python.exe to PATH", puis relancez ce fichier.
  start https://www.python.org/downloads/
  pause
  exit /b 1
)
if not exist venv (
  echo Premiere installation, patientez une a deux minutes...
  %PY% -m venv venv || (pause & exit /b 1)
  venv\Scripts\python -m pip install --upgrade pip > nul
  venv\Scripts\pip install -r requirements.txt || (pause & exit /b 1)
)
set POINTAGE_DEBUG=1
venv\Scripts\python manage.py makemigrations pointages > nul
venv\Scripts\python manage.py migrate
venv\Scripts\python manage.py premier_demarrage
echo.
echo Pointage Max demarre : http://127.0.0.1:8000/
echo Fermez cette fenetre pour arreter.
start "" http://127.0.0.1:8000/
venv\Scripts\python manage.py runserver 127.0.0.1:8000 --noreload
pause
