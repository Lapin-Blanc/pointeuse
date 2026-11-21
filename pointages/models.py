import secrets
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone


GENDER_CHOICES = (
    ('M', 'Homme'),
    ('F', 'Femme'),
)

SITUATION_CHOICES = (
    ('celibataire', 'Célibataire'),
    ('marie', 'Marié(e)'),
    ('divorce', 'Divorcé(e)'),
    ('veuf', 'Veuf / veuve'),
)

MODE_PAIE_CHOICES = (
    ('M', 'Mensuel'),
    ('J', 'Journalier'),
    ('H', 'Horaire'),
)


# ---------------------------------------------------------------------------
# Référentiels
# ---------------------------------------------------------------------------

class Ville(models.Model):
    nom = models.CharField(max_length=100, unique=True)

    class Meta:
        ordering = ["nom"]

    def __str__(self):
        return self.nom


class Service(models.Model):
    """Service ou chantier. L'heure de début sert au calcul des retards."""
    nom = models.CharField(max_length=100, unique=True)
    ville = models.ForeignKey(Ville, on_delete=models.SET_NULL, null=True, blank=True)
    heure_debut = models.TimeField("Heure de début prévue", default="08:00")

    class Meta:
        ordering = ["nom"]
        verbose_name = "Service / chantier"
        verbose_name_plural = "Services / chantiers"

    def __str__(self):
        return self.nom


class TypeContrat(models.Model):
    nom = models.CharField(max_length=100, unique=True)

    class Meta:
        ordering = ["nom"]
        verbose_name = "Type de contrat"
        verbose_name_plural = "Types de contrat"

    def __str__(self):
        return self.nom


class JourFerie(models.Model):
    date = models.DateField(unique=True)
    nom = models.CharField(max_length=100)

    class Meta:
        ordering = ["date"]
        verbose_name = "Jour férié"
        verbose_name_plural = "Jours fériés"

    def __str__(self):
        return "%s (%s)" % (self.nom, self.date.strftime("%d/%m/%Y"))


# ---------------------------------------------------------------------------
# Employés
# ---------------------------------------------------------------------------

def _nouveau_code_badge():
    return secrets.token_hex(8)


class Personne(models.Model):
    # Identité (remplie automatiquement par la carte eID, ou à la main)
    num_nat = models.CharField("Numéro national", max_length=11, blank=True)
    num_carte = models.CharField("Numéro de carte", max_length=100, blank=True)

    nom = models.CharField(max_length=100)
    prenoms = models.CharField("Prénom(s)", max_length=100)
    suffixe = models.CharField("Suffixe", max_length=20, blank=True)

    date_naissance = models.DateField("Date de naissance", blank=True, null=True)
    lieu_naissance = models.CharField(max_length=100, blank=True)
    nationalite = models.CharField("Nationalité", max_length=100, blank=True)
    sexe = models.CharField(max_length=1, choices=GENDER_CHOICES, blank=True)

    debut_val = models.DateField("Début de validité", blank=True, null=True)
    fin_val = models.DateField("Fin de validité", blank=True, null=True)
    commune_delivrance = models.CharField("Commune de délivrance", max_length=100, blank=True)

    adresse = models.CharField("Rue et numéro", max_length=200, blank=True)
    code_postal = models.CharField("Code postal", max_length=6, blank=True)
    localite = models.CharField(max_length=100, blank=True)

    # Fiche RH
    matricule = models.CharField(max_length=20, unique=True, null=True, blank=True)
    cin = models.CharField("CIN", max_length=20, blank=True)
    cnss = models.CharField("N° CNSS", max_length=20, blank=True)
    telephone = models.CharField("Téléphone", max_length=30, blank=True)
    email = models.EmailField(blank=True)
    photo = models.ImageField(upload_to="photos/", blank=True)
    situation_familiale = models.CharField(max_length=20, choices=SITUATION_CHOICES, blank=True)
    enfants = models.PositiveSmallIntegerField("Nombre d'enfants", default=0)

    poste = models.CharField(max_length=100, blank=True)
    qualification = models.CharField(max_length=100, blank=True)
    ville = models.ForeignKey(Ville, on_delete=models.SET_NULL, null=True, blank=True)
    service = models.ForeignKey(Service, on_delete=models.SET_NULL, null=True, blank=True,
                                verbose_name="Service / chantier")
    contrat = models.ForeignKey(TypeContrat, on_delete=models.SET_NULL, null=True, blank=True)
    date_entree = models.DateField("Date d'entrée", null=True, blank=True)
    date_sortie = models.DateField("Date de sortie", null=True, blank=True)

    mode_paie = models.CharField("Mode de paie", max_length=1, choices=MODE_PAIE_CHOICES, default='M')
    taux = models.DecimalField("Salaire / taux", max_digits=10, decimal_places=2, default=0,
                               help_text="Salaire mensuel, prix de la journée ou de l'heure selon le mode de paie.")
    paiement_banque = models.BooleanField("Payé par virement", default=False)
    banque = models.CharField(max_length=100, blank=True)
    rib = models.CharField("RIB", max_length=34, blank=True)
    document = models.FileField("Pièce d'identité scannée", upload_to="documents/", blank=True)

    actif = models.BooleanField(default=True)
    code_badge = models.CharField(max_length=32, unique=True, null=True, blank=True, editable=False)
    cree_le = models.DateTimeField("Créé le", default=timezone.now, editable=False)
    cree_par = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                 null=True, blank=True, editable=False, related_name="+")

    class Meta:
        ordering = ["nom", "prenoms"]
        verbose_name = "Employé"
        verbose_name_plural = "Employés"

    def __str__(self):
        prenom = self.prenoms.split()[0] if self.prenoms else ""
        return ("%s %s" % (self.nom, prenom)).strip()

    def save(self, *args, **kwargs):
        if not self.code_badge:
            self.code_badge = _nouveau_code_badge()
        super().save(*args, **kwargs)
        if not self.matricule:
            matricule, n = "EMP%04d" % self.pk, 1
            while Personne.objects.filter(matricule__iexact=matricule).exclude(pk=self.pk).exists():
                n += 1  # matricule déjà pris (par exemple importé d'un fichier)
                matricule = "EMP%04d-%d" % (self.pk, n)
            Personne.objects.filter(pk=self.pk).update(matricule=matricule)
            self.matricule = matricule

    def modifiable_par_pointeur(self):
        return timezone.now() - self.cree_le < timedelta(hours=24)

    def solde_conge(self):
        """Jours de congé annuel encore disponibles (reliquats non expirés compris, FIFO)."""
        from .conges import disponible
        return disponible(self)


# ---------------------------------------------------------------------------
# Pointages
# ---------------------------------------------------------------------------

SOURCE_CHOICES = (
    ('eid', 'Carte eID'),
    ('qr', 'QR code'),
    ('manuel', 'Saisie manuelle'),
)


class Pointage(models.Model):
    personne = models.ForeignKey(Personne, on_delete=models.PROTECT, verbose_name="Employé")
    checkin = models.DateTimeField("Heure d'arrivée")
    checkout = models.DateTimeField("Heure de départ", null=True, blank=True)
    ville = models.ForeignKey(Ville, on_delete=models.SET_NULL, null=True, blank=True)
    service = models.ForeignKey(Service, on_delete=models.SET_NULL, null=True, blank=True,
                                verbose_name="Service / chantier")
    source = models.CharField(max_length=10, choices=SOURCE_CHOICES, default='manuel')
    saisi_par = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                  null=True, blank=True, editable=False, related_name="+")

    class Meta:
        ordering = ["-checkin"]

    def is_closed(self):
        return bool(self.checkin and self.checkout)

    is_closed.short_description = "Clôturé"
    is_closed.boolean = True

    def duree(self):
        if self.checkout:
            return self.checkout - self.checkin
        return None

    def duration(self):
        td = self.duree()
        if td is None:
            return None
        minutes = int(td.total_seconds() // 60)
        return "%d:%02d" % (minutes // 60, minutes % 60)

    duration.short_description = "Durée"

    def __str__(self):
        return "%s — %s" % (self.personne, timezone.localtime(self.checkin).strftime("%d/%m/%Y %H:%M"))


# ---------------------------------------------------------------------------
# Congés
# ---------------------------------------------------------------------------

TYPE_CONGE_CHOICES = (
    ('annuel', 'Congé annuel'),
    ('maladie', 'Congé maladie'),
    ('maternite', 'Congé maternité / paternité'),
    ('sans_solde', 'Congé sans solde'),
    ('autre', 'Autre absence autorisée'),
)


def jours_ouvres(debut, fin):
    """Jours travaillés entre deux dates incluses, sans les jours de repos ni les jours fériés."""
    repos = settings.POINTAGE_MAX["JOURS_REPOS"]
    feries = set(JourFerie.objects.filter(date__range=(debut, fin)).values_list("date", flat=True))
    n, d = 0, debut
    while d <= fin:
        if d.weekday() not in repos and d not in feries:
            n += 1
        d += timedelta(days=1)
    return n


class Conge(models.Model):
    personne = models.ForeignKey(Personne, on_delete=models.CASCADE, verbose_name="Employé")
    type = models.CharField(max_length=20, choices=TYPE_CONGE_CHOICES, default='annuel')
    debut = models.DateField("Du")
    fin = models.DateField("Au")
    motif = models.CharField(max_length=200, blank=True)
    cree_par = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                 null=True, blank=True, editable=False, related_name="+")

    class Meta:
        ordering = ["-debut"]
        verbose_name = "Congé"

    def __str__(self):
        return "%s : %s du %s au %s" % (self.personne, self.get_type_display(),
                                         self.debut.strftime("%d/%m/%Y"), self.fin.strftime("%d/%m/%Y"))

    def jours_calendaires(self):
        return (self.fin - self.debut).days + 1

    jours_calendaires.short_description = "Jours calendaires"

    def jours_ouvres(self):
        return jours_ouvres(self.debut, self.fin)

    jours_ouvres.short_description = "Jours décomptés"


# ---------------------------------------------------------------------------
# Journal d'audit
# ---------------------------------------------------------------------------

class Journal(models.Model):
    date = models.DateTimeField(default=timezone.now)
    utilisateur = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                    null=True, blank=True)
    action = models.CharField(max_length=20)
    objet = models.CharField(max_length=50)
    objet_id = models.PositiveIntegerField(null=True)
    details = models.TextField(blank=True)

    class Meta:
        ordering = ["-date"]
        verbose_name = "Entrée du journal"
        verbose_name_plural = "Journal des actions"

    def __str__(self):
        return "%s %s %s" % (self.date, self.action, self.objet)
