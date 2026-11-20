#!/bin/bash
# Lancement local de Pointage Max (Mac / Linux). Double-cliquez ou lancez : bash demarrer.sh
cd "$(dirname "$0")"
if ! command -v python3 > /dev/null; then
  echo "Python 3 n'est pas installé : https://www.python.org/downloads/"; exit 1
fi
if [ ! -d venv ]; then
  echo "Première installation, patientez une à deux minutes..."
  python3 -m venv venv && venv/bin/pip install -q --upgrade pip && venv/bin/pip install -r requirements.txt || exit 1
fi
export POINTAGE_DEBUG=1
venv/bin/python manage.py makemigrations pointages > /dev/null
venv/bin/python manage.py migrate
venv/bin/python manage.py premier_demarrage
echo
echo "Pointage Max démarre : http://127.0.0.1:8000/  (Ctrl+C pour arrêter)"
( sleep 2; (command -v open > /dev/null && open http://127.0.0.1:8000/) || xdg-open http://127.0.0.1:8000/ ) > /dev/null 2>&1 &
venv/bin/python manage.py runserver 127.0.0.1:8000 --noreload
