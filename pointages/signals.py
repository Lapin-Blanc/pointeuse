from django.contrib.auth.models import Group
from django.db.models.signals import post_delete, post_migrate, post_save
from django.dispatch import receiver

from .models import Conge, Journal, JourFerie, Personne, Pointage
from .services import GROUPE_ADMIN, GROUPE_POINTEUR, utilisateur_courant

SUIVIS = {Personne: "Employé", Pointage: "Pointage", Conge: "Congé", JourFerie: "Jour férié"}


def _ecrire(instance, action):
    Journal.objects.create(
        utilisateur=utilisateur_courant(), action=action,
        objet=SUIVIS[type(instance)], objet_id=instance.pk, details=str(instance)[:500],
    )


@receiver(post_save)
def journal_enregistrement(sender, instance, created, raw=False, **kwargs):
    if sender in SUIVIS and not raw:
        _ecrire(instance, "Création" if created else "Modification")


@receiver(post_delete)
def journal_suppression(sender, instance, **kwargs):
    if sender in SUIVIS:
        _ecrire(instance, "Suppression")


def creer_groupes(sender, **kwargs):
    if sender.name == "pointages":
        Group.objects.get_or_create(name=GROUPE_ADMIN)
        Group.objects.get_or_create(name=GROUPE_POINTEUR)


post_migrate.connect(creer_groupes)
