from django.conf import settings

from .services import est_admin, est_pointeur


def pointage_max(request):
    user = getattr(request, "user", None)
    return {
        "APP": settings.POINTAGE_MAX,
        "est_admin": bool(user and est_admin(user)),
        "est_pointeur": bool(user and est_pointeur(user)),
    }
