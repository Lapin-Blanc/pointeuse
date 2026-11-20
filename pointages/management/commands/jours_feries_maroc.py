from datetime import date

from django.core.management.base import BaseCommand
from django.utils import timezone

from pointages.models import JourFerie

# Jours fériés à date fixe au Maroc. Les fêtes religieuses (Aïd al-Fitr, Aïd al-Adha,
# 1er Moharram, Aïd al-Mawlid) suivent le calendrier lunaire : ajoutez-les chaque année
# dans l'administration (Jours fériés) une fois les dates officielles annoncées.
FIXES = [
    (1, 1, "Nouvel An"),
    (1, 11, "Manifeste de l'Indépendance"),
    (1, 14, "Nouvel An amazigh (Yennayer)"),
    (5, 1, "Fête du Travail"),
    (7, 30, "Fête du Trône"),
    (8, 14, "Allégeance Oued Eddahab"),
    (8, 20, "Révolution du Roi et du Peuple"),
    (8, 21, "Fête de la Jeunesse"),
    (10, 31, "Fête de l'Unité"),
    (11, 6, "Marche Verte"),
    (11, 18, "Fête de l'Indépendance"),
]


class Command(BaseCommand):
    help = "Ajoute les jours fériés marocains à date fixe pour une année."

    def add_arguments(self, parser):
        parser.add_argument("annee", nargs="?", type=int, default=timezone.localdate().year)

    def handle(self, annee, **options):
        n = 0
        for mois, jour, nom in FIXES:
            _, cree = JourFerie.objects.get_or_create(date=date(annee, mois, jour), defaults={"nom": nom})
            n += cree
        self.stdout.write(self.style.SUCCESS(
            "%d jour(s) férié(s) ajouté(s) pour %d. Pensez à ajouter les fêtes religieuses." % (n, annee)))
