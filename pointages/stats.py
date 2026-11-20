"""Calculs du tableau de bord (Vision RH) et du bilan mensuel."""
import calendar
from collections import defaultdict
from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings
from django.db.models import Q
from django.utils import timezone

from .models import Conge, Personne, Pointage, jours_ouvres

CONGES_PAYES = ("annuel", "maternite")


def cfg(cle):
    return settings.POINTAGE_MAX[cle]


def bornes_mois(annee, mois):
    return date(annee, mois, 1), date(annee, mois, calendar.monthrange(annee, mois)[1])


def mois_precedent(annee, mois):
    return (annee - 1, 12) if mois == 1 else (annee, mois - 1)


def arrondi(x, n="0.01"):
    return Decimal(x).quantize(Decimal(n), rounding=ROUND_HALF_UP)


def heures(td):
    return Decimal(td.total_seconds()) / Decimal(3600)


def format_heures(h):
    minutes = int(round(float(h) * 60))
    return "%dh%02d" % (minutes // 60, minutes % 60)


def _pointages_periode(debut, fin, personnes=None):
    qs = Pointage.objects.filter(checkin__date__range=(debut, fin)).select_related(
        "personne", "ville", "service", "personne__service")
    if personnes is not None:
        qs = qs.filter(personne__in=personnes)
    return qs


def _jours_conge(personne_ids, debut, fin, types=None):
    """{personne_id: {type: nb_jours_ouvres}} pour les congés qui touchent la période."""
    qs = Conge.objects.filter(personne_id__in=personne_ids, debut__lte=fin, fin__gte=debut)
    if types:
        qs = qs.filter(type__in=types)
    res = defaultdict(lambda: defaultdict(int))
    for c in qs:
        res[c.personne_id][c.type] += jours_ouvres(max(c.debut, debut), min(c.fin, fin))
    return res


# ---------------------------------------------------------------------------
# Bilan mensuel
# ---------------------------------------------------------------------------

def salaire(personne, h, jours_travailles, jours_conges_payes, jours_ouvres_mois):
    """Renvoie (théorique, réel) pour le mois."""
    hm = Decimal(cfg("HEURES_MENSUELLES"))
    hj = Decimal(cfg("HEURES_PAR_JOUR"))
    taux = personne.taux
    if personne.mode_paie == "M":
        theorique = taux
        h_payees = h + jours_conges_payes * hj
        reel = min(taux, taux * h_payees / hm) if hm else Decimal(0)
    elif personne.mode_paie == "J":
        theorique = taux * jours_ouvres_mois
        reel = taux * (jours_travailles + jours_conges_payes)
    else:
        theorique = taux * hm
        reel = taux * (h + jours_conges_payes * hj)
    return arrondi(theorique), arrondi(reel)


def bilan_mensuel(annee, mois, ville=None, service=None, personne=None):
    debut, fin = bornes_mois(annee, mois)
    personnes = Personne.objects.select_related("service", "ville", "contrat")
    if personne:
        personnes = personnes.filter(pk=personne.pk)
    else:
        personnes = personnes.filter(Q(actif=True) | Q(pointage__checkin__date__range=(debut, fin))).distinct()
    if ville:
        personnes = personnes.filter(ville=ville)
    if service:
        personnes = personnes.filter(service=service)
    personnes = list(personnes)

    jom = jours_ouvres(debut, fin)
    aujourd_hui = timezone.localdate()
    # Pour le mois en cours, les absences ne se comptent que sur les jours déjà passés.
    jours_ecoules = jours_ouvres(debut, min(fin, aujourd_hui)) if debut <= aujourd_hui else 0
    conges_ecoules = _jours_conge([p.pk for p in personnes], debut, min(fin, aujourd_hui)) if debut <= aujourd_hui else {}
    par_personne = defaultdict(lambda: {"td": timedelta(), "jours": set(), "ouverts": 0})
    for p in _pointages_periode(debut, fin, personnes):
        d = par_personne[p.personne_id]
        jour = timezone.localtime(p.checkin).date()
        d["jours"].add(jour)
        if p.checkout:
            d["td"] += p.checkout - p.checkin
        elif jour < aujourd_hui:
            d["ouverts"] += 1  # sortie oubliée (ceux d'aujourd'hui sont simplement présents)
    conges = _jours_conge([p.pk for p in personnes], debut, fin)

    lignes = []
    tot = {"heures": Decimal(0), "theorique": Decimal(0), "reel": Decimal(0), "jours": 0}
    for p in personnes:
        d = par_personne[p.pk]
        h = heures(d["td"])
        jc_payes = sum(v for k, v in conges[p.pk].items() if k in CONGES_PAYES)
        jc_total = sum(conges[p.pk].values())
        theo, reel = salaire(p, h, len(d["jours"]), jc_payes, jom)
        lignes.append({
            "personne": p, "jours": len(d["jours"]), "heures": h, "heures_txt": format_heures(h),
            "conges": jc_total, "ouverts": d["ouverts"],
            "absences": max(jours_ecoules - len(d["jours"])
                            - sum(conges_ecoules.get(p.pk, {}).values()), 0),
            "theorique": theo, "reel": reel,
        })
        tot["heures"] += h
        tot["theorique"] += theo
        tot["reel"] += reel
        tot["jours"] += len(d["jours"])
    tot["heures_txt"] = format_heures(tot["heures"])
    lignes.sort(key=lambda l: (l["personne"].nom, l["personne"].prenoms))
    return {"lignes": lignes, "total": tot, "jours_ouvres": jom, "debut": debut, "fin": fin}


# ---------------------------------------------------------------------------
# Tableau de bord
# ---------------------------------------------------------------------------

def _limite_retard(personne, jour):
    service = personne.service
    h = service.heure_debut if service else datetime.strptime(cfg("HEURE_DEBUT"), "%H:%M").time()
    limite = datetime.combine(jour, h) + timedelta(minutes=cfg("TOLERANCE_RETARD_MINUTES"))
    return timezone.make_aware(limite)


def premieres_arrivees(pointages):
    """{(personne_id, jour): (personne, premier checkin)}"""
    res = {}
    for p in pointages:
        cle = (p.personne_id, timezone.localtime(p.checkin).date())
        if cle not in res or p.checkin < res[cle][1]:
            res[cle] = (p.personne, p.checkin)
    return res


def tableau_de_bord(annee, mois):
    aujourd_hui = timezone.localdate()
    actifs = list(Personne.objects.filter(actif=True).select_related("service", "ville"))

    # --- Aujourd'hui
    du_jour = list(_pointages_periode(aujourd_hui, aujourd_hui))
    pointes = {p.personne_id for p in du_jour}
    presents = [p for p in du_jour if not p.checkout]
    en_conge = list(Conge.objects.filter(debut__lte=aujourd_hui, fin__gte=aujourd_hui)
                    .select_related("personne"))
    ids_conge = {c.personne_id for c in en_conge}
    absents = [p for p in actifs if p.pk not in pointes and p.pk not in ids_conge]
    retards_jour = []
    for (pid, jour), (pers, checkin) in premieres_arrivees(du_jour).items():
        limite = _limite_retard(pers, jour)
        if checkin > limite:
            retards_jour.append({"personne": pers, "arrivee": checkin,
                                 "minutes": int((checkin - limite).total_seconds() // 60) + cfg("TOLERANCE_RETARD_MINUTES")})
    retards_jour.sort(key=lambda r: -r["minutes"])
    sorties_oubliees = list(Pointage.objects.filter(checkout__isnull=True, checkin__date__lt=aujourd_hui)
                            .select_related("personne", "service").order_by("-checkin")[:50])
    conges_a_venir = list(Conge.objects.filter(debut__gt=aujourd_hui, debut__lte=aujourd_hui + timedelta(days=30))
                          .select_related("personne").order_by("debut"))

    # --- Mois choisi
    debut, fin = bornes_mois(annee, mois)
    pts_mois = list(_pointages_periode(debut, fin))
    par_ville, par_service, par_jour = defaultdict(Decimal), defaultdict(Decimal), defaultdict(Decimal)
    par_personne = defaultdict(Decimal)
    for p in pts_mois:
        if not p.checkout:
            continue
        h = heures(p.checkout - p.checkin)
        par_ville[p.ville.nom if p.ville else "Sans ville"] += h
        par_service[p.service.nom if p.service else "Sans service"] += h
        par_jour[timezone.localtime(p.checkin).day] += h
        par_personne[p.personne] += h

    for pers in actifs:
        par_personne.setdefault(pers, Decimal(0))

    a_l_heure = en_retard = 0
    for (pid, jour), (pers, checkin) in premieres_arrivees(pts_mois).items():
        if checkin > _limite_retard(pers, jour):
            en_retard += 1
        else:
            a_l_heure += 1
    total_arrivees = a_l_heure + en_retard

    bilan = bilan_mensuel(annee, mois)
    pa, pm = mois_precedent(annee, mois)
    bilan_prec = bilan_mensuel(pa, pm)

    def variation(a, b):
        if not b:
            return None
        return arrondi((Decimal(a) - Decimal(b)) * 100 / Decimal(b), "0.1")

    classement = sorted(((pers, h) for pers, h in par_personne.items()), key=lambda x: -x[1])

    def barres(d):
        m = max(d.values(), default=0) or 1
        return [{"nom": k, "heures": format_heures(v), "pct": int(v * 100 / m)}
                for k, v in sorted(d.items(), key=lambda x: -x[1])]

    nb_jours = calendar.monthrange(annee, mois)[1]
    m_jour = max(par_jour.values(), default=0) or 1
    histo = [{"jour": j, "heures": format_heures(par_jour[j]), "pct": int(par_jour[j] * 100 / m_jour)}
             for j in range(1, nb_jours + 1)]

    return {
        "aujourd_hui": aujourd_hui,
        "nb_actifs": len(actifs), "nb_pointes": len(pointes), "presents": presents,
        "nb_sortis": len(pointes) - len({p.personne_id for p in presents}),
        "absents": absents, "en_conge": en_conge, "retards_jour": retards_jour,
        "sorties_oubliees": sorties_oubliees, "conges_a_venir": conges_a_venir,
        "heures_mois": bilan["total"]["heures_txt"], "heures_prec": bilan_prec["total"]["heures_txt"],
        "var_heures": variation(bilan["total"]["heures"], bilan_prec["total"]["heures"]),
        "cout_reel": bilan["total"]["reel"], "cout_theorique": bilan["total"]["theorique"],
        "cout_prec": bilan_prec["total"]["reel"],
        "var_cout": variation(bilan["total"]["reel"], bilan_prec["total"]["reel"]),
        "ponctualite": int(a_l_heure * 100 / total_arrivees) if total_arrivees else None,
        "a_l_heure": a_l_heure, "en_retard": en_retard,
        "par_ville": barres(par_ville), "par_service": barres(par_service), "histo": histo,
        "top": [(p, format_heures(h)) for p, h in classement[:5]],
        "flop": [(p, format_heures(h)) for p, h in classement[::-1][:5]],
    }
