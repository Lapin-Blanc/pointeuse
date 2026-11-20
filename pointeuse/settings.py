"""
Réglages de Pointage Max.

Les valeurs sensibles ou propres à chaque installation se règlent par variables
d'environnement (voir README.md) :

    POINTAGE_DEBUG=1            mode développement (jamais en production)
    POINTAGE_HOSTS=192.168.1.20,pointage.local
    POINTAGE_TZ=Africa/Casablanca
    POINTAGE_HTTPS=1            si le site est servi en HTTPS (cookies sécurisés)
"""

import os
import secrets
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def _env_bool(nom, defaut="0"):
    return os.environ.get(nom, defaut).lower() in ("1", "true", "oui", "yes")


def _cle_secrete():
    """Clé lue dans l'environnement, sinon dans secret_key.txt (créé au premier lancement, hors Git)."""
    if os.environ.get("POINTAGE_SECRET_KEY"):
        return os.environ["POINTAGE_SECRET_KEY"]
    fichier = BASE_DIR / "secret_key.txt"
    if not fichier.exists():
        fichier.write_text(secrets.token_urlsafe(50))
        fichier.chmod(0o600)
    return fichier.read_text().strip()


SECRET_KEY = _cle_secrete()

DEBUG = _env_bool("POINTAGE_DEBUG")

ALLOWED_HOSTS = [h.strip() for h in os.environ.get("POINTAGE_HOSTS", "localhost,127.0.0.1").split(",") if h.strip()]
if os.environ.get("POINTAGE_HOSTS", "") == "*":
    ALLOWED_HOSTS = ["*"]


# --- Réglages métier ---------------------------------------------------------
# Valeurs par défaut pour le Maroc. Pour la Belgique par exemple :
# DEVISE "€", HEURES_MENSUELLES 164.67 (38 h/sem.), JOURS_REPOS [5, 6], CONGE_ANNUEL_JOURS 20.

POINTAGE_MAX = {
    "NOM": "Pointage Max",
    "DEVISE": os.environ.get("POINTAGE_DEVISE", "DH"),
    "HEURES_MENSUELLES": float(os.environ.get("POINTAGE_HEURES_MENSUELLES", "191")),  # 44 h/semaine
    "HEURES_PAR_JOUR": float(os.environ.get("POINTAGE_HEURES_PAR_JOUR", "8")),
    "JOURS_REPOS": [int(j) for j in os.environ.get("POINTAGE_JOURS_REPOS", "6").split(",") if j != ""],  # 0=lundi … 6=dimanche
    "CONGE_ANNUEL_JOURS": int(os.environ.get("POINTAGE_CONGE_ANNUEL", "18")),  # 1,5 jour par mois
    "CONGE_REPORT_ANNEES": int(os.environ.get("POINTAGE_CONGE_REPORT", "2")),  # reliquat utilisable 2 ans de plus
    "HEURE_DEBUT": os.environ.get("POINTAGE_HEURE_DEBUT", "08:00"),
    "TOLERANCE_RETARD_MINUTES": int(os.environ.get("POINTAGE_TOLERANCE_RETARD", "10")),
    "DELAI_MIN_MINUTES": 1,  # délai minimum entre une arrivée et une sortie
}


# --- Application ---------------------------------------------------------------

INSTALLED_APPS = [
    'pointages',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'pointages.services.UtilisateurCourantMiddleware',
    'pointages.services.EntetesSecuriteMiddleware',
]

ROOT_URLCONF = 'pointeuse.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'pointages.context_processors.pointage_max',
            ],
        },
    },
]

WSGI_APPLICATION = 'pointeuse.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator', 'OPTIONS': {'min_length': 6}},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "accueil"
LOGOUT_REDIRECT_URL = "login"


# --- Langue et heure -------------------------------------------------------------

LANGUAGE_CODE = 'fr'
TIME_ZONE = os.environ.get("POINTAGE_TZ", "Africa/Casablanca")
USE_I18N = True
USE_TZ = True


# --- Fichiers ---------------------------------------------------------------------

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'
FILE_UPLOAD_PERMISSIONS = 0o640
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024

DEFAULT_AUTO_FIELD = 'django.db.models.AutoField'


# --- Sécurité ----------------------------------------------------------------------

SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_AGE = 12 * 3600
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
CSRF_COOKIE_HTTPONLY = True
X_FRAME_OPTIONS = "DENY"
SECURE_CONTENT_TYPE_NOSNIFF = True

if _env_bool("POINTAGE_HTTPS"):
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    CSRF_TRUSTED_ORIGINS = ["https://%s" % h for h in ALLOWED_HOSTS if h != "*"]
