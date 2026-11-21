#!/usr/bin/env python3

import os
import django
from datetime import datetime
from time import sleep

from django.core.exceptions import ObjectDoesNotExist
os.environ.setdefault("DJANGO_SETTINGS_MODULE","pointeuse.settings")
django.setup()

from RPi import GPIO as gpio
gpio.setmode(gpio.BCM)
from Adafruit_CharLCD import Adafruit_CharLCD as LCD

from pointages.models import Personne
from pointages.services import ARRIVEE, SORTIE, pointer

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
lcd.message(datetime.now().strftime("%H:%M") + "\nIntroduire carte")

# Global variables

lcd_free_flag = True

class PointeuseReader(BeidReader):

    def on_removed(self):
        global lcd_free_flag
        print("---------------------")
        print("Card removed")
        print("---------------------")
        gpio.output(GREEN_LED, False)
        gpio.output(RED_LED, False)
        lcd.clear()
        lcd.message(datetime.now().strftime("%H:%M") + "\nIntroduire carte")
        lcd_free_flag = True


    def on_inserted(self, card):
        global lcd_free_flag
        lcd_free_flag = False
        gpio.output(RED_LED, True)
        lcd.clear()
        lcd.message("Lecture infos")

        infos = card.read_infos()
        print("---------------------")
        print("Card inserted")
        print("---------------------")
        pprint(infos)

        lcd.clear()
        lcd.message("Verification\nPersonne")
        try:
            p = Personne.objects.get(num_nat=infos["num_nat"])
            if p.num_carte != infos['num_carte']:
                Personne.objects.filter(num_nat=infos["num_nat"]).update(**infos)
                print("\nPersonne mise à jour :")

        except ObjectDoesNotExist:
            p = Personne(**infos)
            p.save()
            print("Personne créée :", p)

        p_name = str(p)
        if not p.actif:
            lcd.clear()
            lcd.message(p_name + "\nAcces refuse")
            gpio.output(RED_LED, True)
            return
        resultat, _ = pointer(p, source="eid")
        p_message = datetime.now().strftime("%H:%M")
        if resultat == ARRIVEE:
            print("Arrivée enregistrée")
            p_message += " ARRIVEE"
        elif resultat == SORTIE:
            print("Sortie enregistrée")
            p_message += " SORTIE"
        else:
            print("Durée de pointage trop courte")
        ############################
        lcd.clear()
        lcd.message(p_name + "\n" + p_message)
        sleep(1)
        gpio.output(GREEN_LED, True)
        gpio.output(RED_LED, False)
        ############################
        
if __name__ == "__main__":
    p = PointeuseReader()
    print("Application started")
    gpio.output(GREEN_LED, False)
    gpio.output(RED_LED, False)

    while True:
        if lcd_free_flag == True:
            lcd.clear()
            lcd.message(datetime.now().strftime("%H:%M") + "\nIntroduire carte")
        sleep(60)
