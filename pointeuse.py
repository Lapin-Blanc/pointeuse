#!/usr/bin/env python3

import os
import django
from datetime import timedelta
from datetime import datetime

from django.utils import timezone
from django.core.exceptions import ObjectDoesNotExist
os.environ.setdefault("DJANGO_SETTINGS_MODULE","pointeuse.settings")
django.setup()
from pointages.models import Personne, Pointage

from pythonbeid.beid import BeidReader

from pprint import pprint
# Constants
MIN_DELAY = 1

class PointeuseReader(BeidReader):

    def on_removed(self):
        print("---------------------")
        print("Card removed")
        print("---------------------")

    def on_inserted(self, card):
        infos = card.read_infos()
        print("---------------------")
        print("Card inserted")
        print("---------------------")
        pprint(infos)

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

        if not p.pointage_set.filter(checkin__date = timezone.now().date()):
            p.pointage_set.create(checkin=timezone.now())
            print("Premier pointage de la journée")
        else:
            try:
                pointage_started = p.pointage_set.get(checkin__date = timezone.now().date() , checkout__exact = None)
                if pointage_started.checkin >= timezone.now() - timedelta(minutes = MIN_DELAY):
                    print("Durée de pointage trop courte")
                else:
                    pointage_started.checkout = timezone.now()
                    pointage_started.save()
                    print("Pointage clôturé")
            except ObjectDoesNotExist:
                p.pointage_set.create(checkin=timezone.now())
                print("Nouveau pointage pour la journée")

if __name__ == "__main__":
    p = PointeuseReader()
    print("Application started")

    while True:
        pass
