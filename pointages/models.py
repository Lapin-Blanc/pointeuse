from django.db import models
import datetime

# Create your models here.

GENDER_CHOICES = (
    ('M', 'Homme'),
    ('F', 'Femme'),
)

class Personne(models.Model):

    num_nat = models.CharField("Numéro national", max_length=11)
    num_carte = models.CharField("Numéro de carte", max_length=100)

    nom = models.CharField(max_length=100)
    prenoms = models.CharField("Prénom(s)", max_length=100)
    suffixe = models.CharField("Prénom(s)", max_length=20, blank=True)

    date_naissance = models.DateField("Date de naissance", blank=True, null=True)
    lieu_naissance = models.CharField(max_length=100, blank=True)
    nationalite = models.CharField("Nationalité", max_length=100, blank=True)
    sexe = models.CharField(max_length=1, choices=GENDER_CHOICES)

    debut_val = models.DateField("Début de validité", blank=True, null=True)
    fin_val = models.DateField("Fin de validité", blank=True, null=True)
    commune_delivrance = models.CharField("Commune de délivrance", max_length=100, blank=True)
    
    adresse = models.CharField("Rue et numéro", max_length=200, blank=True)
    code_postal = models.CharField("Code postal", max_length=6, blank=True)
    localite = models.CharField(max_length=100, blank=True)
    
    def __str__(self):
        return "%s %s" % (self.nom, self.prenoms.split()[0])

class Pointage(models.Model):
    
    personne = models.ForeignKey(Personne())
    checkin = models.DateTimeField("Heure d'arrivée")
    checkout = models.DateTimeField("Heure de départ", null=True, blank=True)

    def is_closed(self):
        return bool(self.checkin and self.checkout)

    is_closed.short_description = "Clôturé"
    is_closed.boolean = True

    def duration(self):
        if self.checkout:
            td = self.checkout - self.checkin        
            return ':'.join(str(td).split(':')[:2])
        else:
            return None

    duration.short_description = "Durée"

    def __str__(self):
        return "checkin : %s |  checkout : %s" % (self.checkin, self.checkout)


