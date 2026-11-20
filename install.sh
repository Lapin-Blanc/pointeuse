#!/bin/bash
# Installation de Pointage Max (Raspberry Pi OS, Debian ou Ubuntu).
#   bash install.sh          -> application web seule (pointage QR, Vision RH, bilan…)
#   bash install.sh --eid    -> + borne avec lecteur de carte eID, écran LCD et LED (Raspberry Pi)
set -e
cd "$(dirname "$0")"
DOSSIER="$(pwd)"
UTILISATEUR="$(whoami)"

sudo apt-get update
sudo apt-get install -y python3-venv python3-dev build-essential git libjpeg-dev zlib1g-dev

if [ "$1" = "--eid" ]; then
  sudo apt-get install -y swig libpcsclite-dev pcscd libacr38u python3-rpi.gpio
  [ -d pythonbeid ] || git clone https://github.com/Lapin-Blanc/pythonbeid.git
fi

python3 -m venv --system-site-packages venv
venv/bin/pip install --upgrade pip
venv/bin/pip install -r requirements.txt
[ "$1" = "--eid" ] && venv/bin/pip install pyscard

venv/bin/python manage.py makemigrations pointages
venv/bin/python manage.py migrate
venv/bin/python manage.py collectstatic --noinput
venv/bin/python manage.py jours_feries_maroc
echo "Création du compte administrateur :"
venv/bin/python manage.py createsuperuser

IP="$(hostname -I | awk '{print $1}')"
for service in pointage-web pointage-borne; do
  [ "$service" = "pointage-borne" ] && [ "$1" != "--eid" ] && continue
  sed -e "s|@DOSSIER@|$DOSSIER|g" -e "s|@UTILISATEUR@|$UTILISATEUR|g" -e "s|@HOSTS@|localhost,127.0.0.1,$IP,$(hostname).local|g" \
    "deploiement/$service.service" | sudo tee "/etc/systemd/system/$service.service" > /dev/null
  sudo systemctl daemon-reload
  sudo systemctl enable --now "$service"
done

# Ancien service init.d de la version précédente
if [ -f /etc/init.d/pointage ]; then
  sudo /etc/init.d/pointage stop || true
  sudo update-rc.d -f pointage remove || true
  sudo rm -f /etc/init.d/pointage
fi

echo
echo "Pointage Max est prêt : http://$IP:8000/"
