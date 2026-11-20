from django.urls import path

from . import views

urlpatterns = [
    path("", views.accueil, name="accueil"),
    path("vision-rh/", views.tableau_de_bord, name="tableau_de_bord"),
    path("bilan/", views.bilan, name="bilan"),
    path("journal/", views.journal, name="journal"),
    path("importer/", views.importer, name="importer"),
    path("importer/modele-<str:type_import>.xlsx", views.importer_modele, name="importer_modele"),
    path("pointage/", views.pointage, name="pointage"),
    path("pointage/scan/", views.scan, name="scan"),
    path("pointages/", views.pointages_liste, name="pointages_liste"),
    path("pointages/<int:pk>/modifier/", views.pointage_modifier, name="pointage_modifier"),
    path("pointages/<int:pk>/supprimer/", views.pointage_supprimer, name="pointage_supprimer"),
    path("employes/", views.employes, name="employes"),
    path("employes/nouveau/", views.employe_form, name="employe_nouveau"),
    path("employes/<int:pk>/", views.employe_fiche, name="employe_fiche"),
    path("employes/<int:pk>/modifier/", views.employe_form, name="employe_modifier"),
    path("employes/<int:pk>/badge/", views.badge, name="badge"),
    path("employes/<int:pk>/badge.png", views.badge_png, name="badge_png"),
]
