"""Logique métier partagée par la borne eID (pointeuse.py), le scan QR et la saisie manuelle."""
from contextvars import ContextVar
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from .models import Pointage

ARRIVEE = "ARRIVEE"
SORTIE = "SORTIE"
TROP_COURT = "TROP_COURT"

GROUPE_ADMIN = "Administrateur"
GROUPE_POINTEUR = "Pointeur"


def est_admin(user):
    return user.is_authenticated and (user.is_superuser or user.groups.filter(name=GROUPE_ADMIN).exists())


def est_pointeur(user):
    return user.is_authenticated and (est_admin(user) or user.groups.filter(name=GROUPE_POINTEUR).exists())


def pointer(personne, source="manuel", user=None, ville=None, service=None, maintenant=None):
    """Enregistre une arrivée ou une sortie pour la personne.

    Renvoie (resultat, pointage) avec resultat parmi ARRIVEE, SORTIE, TROP_COURT.
    """
    maintenant = maintenant or timezone.now()
    jour = timezone.localtime(maintenant).date()
    ouvert = (personne.pointage_set
              .filter(checkin__date=jour, checkout__isnull=True)
              .order_by("-checkin").first())
    if ouvert:
        if ouvert.checkin >= maintenant - timedelta(minutes=settings.POINTAGE_MAX["DELAI_MIN_MINUTES"]):
            return TROP_COURT, ouvert
        ouvert.checkout = maintenant
        ouvert.save()
        return SORTIE, ouvert
    p = Pointage.objects.create(
        personne=personne, checkin=maintenant, source=source, saisi_par=user,
        ville=ville or personne.ville, service=service or personne.service,
    )
    return ARRIVEE, p


# --- Utilisateur courant, pour le journal d'audit -------------------------

_utilisateur_courant = ContextVar("utilisateur_courant", default=None)


def utilisateur_courant():
    return _utilisateur_courant.get()


class UtilisateurCourantMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = request.user if getattr(request, "user", None) and request.user.is_authenticated else None
        token = _utilisateur_courant.set(user)
        try:
            return self.get_response(request)
        finally:
            _utilisateur_courant.reset(token)


class EntetesSecuriteMiddleware:
    """Content-Security-Policy et autres en-têtes de sécurité."""

    CSP = ("default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
           "img-src 'self' data: blob:; media-src 'self' blob:; connect-src 'self'; "
           "frame-ancestors 'none'; base-uri 'self'; form-action 'self'")

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response.setdefault("Content-Security-Policy", self.CSP)
        response.setdefault("Referrer-Policy", "same-origin")
        response.setdefault("Permissions-Policy", "camera=(self), microphone=(), geolocation=()")
        return response
