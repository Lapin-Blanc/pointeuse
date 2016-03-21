#!/bin/bash

sudo apt-get -y update
sudo apt-get -y upgrade
sudo apt-get -y install swig libpcsclite-dev libacr38u python3-setuptools build-essential python3-pip git python3-rpi.gpio
sudo pip3 install django pytz

git clone https://github.com/LudovicRousseau/pyscard.git
cd pyscard
sudo python3 setup.py build_ext install
cd ..
sudo rm -fr pyscard

git clone https://github.com/Lapin-Blanc/pythonbeid.git

python3 manage.py makemigrations
python3 manage.py migrate
python3 manage.py createsuperuser

sudo cp pointage /etc/init.d/
sudo /etc/init.d/pointage start
sudo update-rc.d pointage defaults
