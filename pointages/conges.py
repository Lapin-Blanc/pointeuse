"""Soldes de congé annuel avec consommation FIFO.

Chaque année, l'employé acquiert CONGE_ANNUEL_JOURS jours (au prorata des mois travaillés).
Les jours pris sont décomptés d'abord sur l'année la plus ancienne encore valable.
Un reliquat reste utilisable pendant CONGE_REPORT_ANNEES années, puis il expire.
"""
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings
from django.utils import timezone


def _cfg(cle):
    return settings.POINTAGE_MAX[cle]


def _mois_travailles(personne, annee):
    debut, fin = date(annee, 1, 1), date(annee, 12, 31)
    if personne.date_entree:
        debut = max(debut, personne.date_entree)
    if personne.date_sortie:
        fin = min(fin, personne.date_sortie)
    if fin < debut:
        return 0
    mois = fin.month - debut.month + 1
    if debut.day > 15:  # entré après le 15 : le premier mois ne compte pas
        mois -= 1
    return max(mois, 0)


def acquis_annee(personne, annee):
    par_mois = Decimal(_cfg("CONGE_ANNUEL_JOURS")) / 12
    return (par_mois * _mois_travailles(personne, annee)).quantize(Decimal("0.5"), rounding=ROUND_HALF_UP)


def soldes(personne, aujourd_hui=None):
    """Renvoie {"annees": [...], "disponible": Decimal} pour le congé annuel."""
    aujourd_hui = aujourd_hui or timezone.localdate()
    report = _cfg("CONGE_REPORT_ANNEES")
    conges = list(personne.conge_set.filter(type="annuel").order_by("debut"))
    premiere = min([aujourd_hui.year]
                   + ([personne.date_entree.year] if personne.date_entree else [timezone.localtime(personne.cree_le).year])
                   + [c.debut.year for c in conges])
    annees = {a: {"annee": a, "acquis": acquis_annee(personne, a), "pris": Decimal(0)}
              for a in range(premiere, aujourd_hui.year + 1)}
    for a in list(annees):
        annees[a]["reste"] = annees[a]["acquis"]

    for c in conges:
        a_prendre = Decimal(c.jours_ouvres())
        for a in sorted(annees):
            if a_prendre <= 0:
                break
            if a > c.debut.year or a < c.debut.year - report:
                continue  # année future, ou reliquat déjà expiré à la date du congé
            pris = min(a_prendre, max(annees[a]["reste"], Decimal(0)))
            annees[a]["reste"] -= pris
            annees[a]["pris"] += pris
            a_prendre -= pris
        if a_prendre > 0:  # pas assez de solde : le dépassement est noté sur l'année du congé
            a = min(c.debut.year, aujourd_hui.year)
            annees.setdefault(a, {"annee": a, "acquis": Decimal(0), "pris": Decimal(0), "reste": Decimal(0)})
            annees[a]["pris"] += a_prendre
            annees[a]["reste"] -= a_prendre

    lignes = []
    disponible = Decimal(0)
    for a in sorted(annees):
        l = annees[a]
        l["expire_fin"] = a + report
        l["expire"] = aujourd_hui.year > a + report
        if not l["expire"]:
            disponible += l["reste"]
        lignes.append(l)
    return {"annees": lignes, "disponible": disponible}


def disponible(personne, aujourd_hui=None):
    return soldes(personne, aujourd_hui)["disponible"]
