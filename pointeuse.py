#!/usr/bin/env python3

import os
import django
from datetime import timedelta
from datetime import datetime
from time import sleep

from django.utils import timezone
from django.core.exceptions import ObjectDoesNotExist
os.environ.setdefault("DJANGO_SETTINGS_MODULE","pointeuse.settings")
django.setup()

from RPi import GPIO as gpio
gpio.setmode(gpio.BCM)
from Adafruit_CharLCD import Adafruit_CharLCD as LCD

from pointages.models import Personne, Pointage

from pythonbeid.beid import BeidReader

from pprint import pprint

# Constants
MIN_DELAY = 1

GREEN_LED = 20
RED_LED = 21

gpio.setup(GREEN_LED, gpio.OUT)
gpio.setup(RED_LED, gpio.OUT)

gpio.output(RED_LED, True)
gpio.output(GREEN_LED, False)

lcd = LCD()
lcd.clear()
lcd.message("System ready\nInsert card...")

class PointeuseReader(BeidReader):

    def on_removed(self):
        print("---------------------")
        print("Card removed")
        print("---------------------")
        gpio.output(GREEN_LED, False)
        gpio.output(RED_LED, False)
        lcd.clear()
        lcd.message("System ready\nInsert card...")


    def on_inserted(self, card):
        gpio.output(RED_LED, True)
        lcd.clear()
        lcd.message("Reading infos...")

        infos = card.read_infos()
        print("---------------------")
        print("Card inserted")
        print("---------------------")
        pprint(infos)

        gpio.output(GREEN_LED, True)
        gpio.output(RED_LED, False)

        try:
            Personne.objects.get(num_nat=infos["num_nat"])
        except ObjectDoesNotExist:
            p = Personne(**infos).save()
            print("Personne créée :", p)

        try:
            Personne.objects.get(num_nat=infos["num_nat"])
            Personne.objects.filter(num_nat=infos["num_nat"]).update(**infos)
            print("\nPersonne mise à jour :")
        except ObjectDoesNotExist:
            p = Personne(**infos).save()
            print("\nPersonne créée :", p)

        p = Personne.objects.get(num_nat=infos["num_nat"])
        print(p)
        p_name = p.nom + " " + p.prenoms.split()[0]
        p_message = datetime.now().strftime("%H:%M") 

        if not p.pointage_set.filter(checkin__date = timezone.now().date()):
            p.pointage_set.create(checkin=timezone.now())
            print("Premier pointage de la journée")
            p_message = p_message + " CHECKIN"
            
        else:
            try:
                pointage_started = p.pointage_set.get(checkin__date = timezone.now().date() , checkout__exact = None)
                if pointage_started.checkin >= timezone.now() - timedelta(minutes = MIN_DELAY):
                    print("Durée de pointage trop courte")
                else:
                    pointage_started.checkout = timezone.now()
                    pointage_started.save()
                    print("Pointage clôturé")
                    p_message = p_message + " CHECKOUT"
            except ObjectDoesNotExist:
                p.pointage_set.create(checkin=timezone.now())
                print("Nouveau pointage pour la journée")
                p_message = p_message + " CHECKIN"
        ############################
        lcd.clear()
        lcd.message(p_name + "\n" + p_message)
        ############################
        
if __name__ == "__main__":
    p = PointeuseReader()
    print("Application started")

    while True:
        sleep(3600)
