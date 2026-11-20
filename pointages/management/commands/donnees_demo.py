import random
from datetime import datetime, time, timedelta
from decimal import Decimal

from django.contrib.auth.models import Group, User
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.utils import timezone

from pointages.models import Conge, Personne, Pointage, Service, TypeContrat, Ville
from pointages.services import GROUPE_POINTEUR

EMPLOYES = [
    ("Alaoui", "Karim", "M", "Chef de chantier", "M", "8623"),
    ("Bennani", "Salma", "F", "Comptable", "M", "7500"),
    ("Chraibi", "Youssef", "M", "Maçon", "J", "200"),
    ("El Idrissi", "Fatima Zahra", "F", "Secrétaire", "M", "5200"),
    ("Fassi", "Omar", "M", "Électricien", "H", "28"),
    ("Haddad", "Nadia", "F", "Ingénieure", "M", "14000"),
    ("Kettani", "Mehdi", "M", "Ouvrier", "J", "180"),
    ("Lahlou", "Imane", "F", "Technicienne", "M", "6800"),
    ("Mansouri", "Rachid", "M", "Chauffeur", "J", "190"),
    ("Naciri", "Hind", "F", "RH", "M", "9000"),
    ("Ouazzani", "Hamza", "M", "Soudeur", "H", "30"),
    ("Tazi", "Amine", "M", "Magasinier", "M", "4800"),
]


class Command(BaseCommand):
    help = "Remplit la base avec des données de démonstration (à ne pas utiliser en production)."

    def handle(self, **options):
        random.seed(42)
        call_command("jours_feries_maroc", timezone.localdate().year)
        villes = [Ville.objects.get_or_create(nom=n)[0] for n in ("Casablanca", "Rabat", "Tanger")]
        services = [
            Service.objects.get_or_create(nom="Chantier Anfa", defaults={"ville": villes[0], "heure_debut": time(7, 30)})[0],
            Service.objects.get_or_create(nom="Bureau Rabat", defaults={"ville": villes[1], "heure_debut": time(8, 30)})[0],
            Service.objects.get_or_create(nom="Atelier Tanger", defaults={"ville": villes[2], "heure_debut": time(8, 0)})[0],
        ]
        contrats = [TypeContrat.objects.get_or_create(nom=n)[0] for n in ("CDI", "CDD", "Intérim")]

        if not User.objects.filter(username="admin").exists():
            User.objects.create_superuser("admin", "", "admin123")
        if not User.objects.filter(username="pointeur").exists():
            u = User.objects.create_user("pointeur", "", "pointeur123")
            u.groups.add(Group.objects.get(name=GROUPE_POINTEUR))

        personnes = []
        for i, (nom, prenom, sexe, poste, mode, taux) in enumerate(EMPLOYES):
            s = services[i % 3]
            p, _ = Personne.objects.get_or_create(nom=nom, prenoms=prenom, defaults=dict(
                sexe=sexe, poste=poste, mode_paie=mode, taux=Decimal(taux), service=s, ville=s.ville,
                contrat=contrats[i % 3], cin="B%06d" % (100000 + i * 7919 % 900000), telephone="06%08d" % (i * 1234567 % 10 ** 8),
                date_entree=timezone.localdate() - timedelta(days=400 + i * 30), situation_familiale="marie" if i % 2 else "celibataire"))
            personnes.append(p)

        aujourd_hui = timezone.localdate()
        debut = (aujourd_hui.replace(day=1) - timedelta(days=1)).replace(day=1)
        Conge.objects.get_or_create(personne=personnes[3], debut=aujourd_hui - timedelta(days=2),
                                    defaults={"fin": aujourd_hui + timedelta(days=3), "type": "annuel"})
        Conge.objects.get_or_create(personne=personnes[7], debut=aujourd_hui + timedelta(days=8),
                                    defaults={"fin": aujourd_hui + timedelta(days=15), "type": "annuel"})
        Conge.objects.get_or_create(personne=personnes[10], debut=debut + timedelta(days=10),
                                    defaults={"fin": debut + timedelta(days=12), "type": "maladie"})
        if Pointage.objects.exists():
            self.stdout.write("Pointages déjà présents, non recréés.")
            return
        d = debut
        maintenant = timezone.localtime()
        while d <= aujourd_hui:
            if d.weekday() != 6:
                for i, p in enumerate(personnes):
                    if random.random() < 0.08 or (d == aujourd_hui and i in (3, 5, 9)):
                        continue  # absence
                    if p.conge_set.filter(debut__lte=d, fin__gte=d).exists():
                        continue
                    h = datetime.combine(d, p.service.heure_debut) + timedelta(minutes=random.randint(-15, 35))
                    arrivee = timezone.make_aware(h)
                    if arrivee > maintenant:
                        continue
                    duree = timedelta(hours=random.choice([7, 8, 8, 8, 9]), minutes=random.randint(0, 50))
                    depart = arrivee + duree
                    if d == aujourd_hui or (random.random() < 0.01):
                        depart = None if (d == aujourd_hui and i % 4) or d != aujourd_hui else min(depart, maintenant)
                    if depart and depart > maintenant:
                        depart = None
                    Pointage.objects.create(personne=p, checkin=arrivee, checkout=depart, ville=p.ville,
                                            service=p.service, source=random.choice(["qr", "qr", "manuel", "eid"]))
            d += timedelta(days=1)
        self.stdout.write(self.style.SUCCESS(
            "Données de démo créées. Connexion : admin / admin123 ou pointeur / pointeur123."))
