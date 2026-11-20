from django.contrib.auth.models import User
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Crée le compte admin / admin123 s'il n'existe encore aucun utilisateur (utilisation locale)."

    def handle(self, **options):
        if User.objects.exists():
            return
        User.objects.create_superuser("admin", "", "admin123")
        self.stdout.write(self.style.WARNING(
            "Compte créé : identifiant « admin », mot de passe « admin123 ». "
            "Changez-le dès la première connexion (clic sur votre nom en haut à droite)."))
