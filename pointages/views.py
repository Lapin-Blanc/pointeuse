import csv
from datetime import datetime
from functools import wraps
from io import BytesIO

import segno
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from . import stats
from .forms import LieuForm, PersonneForm, PointageManuelForm
from .models import Journal, Personne, Pointage, Service, Ville
from .services import ARRIVEE, SORTIE, TROP_COURT, est_admin, est_pointeur, pointer


# ---------------------------------------------------------------------------
# Contrôle d'accès
# ---------------------------------------------------------------------------

def admin_requis(vue):
    @wraps(vue)
    @login_required
    def wrapper(request, *args, **kwargs):
        if not est_admin(request.user):
            raise PermissionDenied
        return vue(request, *args, **kwargs)
    return wrapper


def pointeur_requis(vue):
    @wraps(vue)
    @login_required
    def wrapper(request, *args, **kwargs):
        if not est_pointeur(request.user):
            raise PermissionDenied
        return vue(request, *args, **kwargs)
    return wrapper


def _mois_demande(request):
    try:
        d = datetime.strptime(request.GET.get("mois", ""), "%Y-%m")
        return d.year, d.month
    except ValueError:
        t = timezone.localdate()
        return t.year, t.month


def _lieu_session(request):
    ville = Ville.objects.filter(pk=request.session.get("ville")).first()
    service = Service.objects.filter(pk=request.session.get("service")).first()
    return ville, service


@login_required
def accueil(request):
    if est_admin(request.user):
        return redirect("tableau_de_bord")
    return redirect("pointage")


# ---------------------------------------------------------------------------
# Vision RH et bilan (administrateur)
# ---------------------------------------------------------------------------

@admin_requis
def tableau_de_bord(request):
    annee, mois = _mois_demande(request)
    ctx = stats.tableau_de_bord(annee, mois)
    ctx["mois"] = "%04d-%02d" % (annee, mois)
    return render(request, "pointages/tableau_de_bord.html", ctx)


@admin_requis
def bilan(request):
    annee, mois = _mois_demande(request)
    form = LieuForm(request.GET or None)
    ville = service = None
    if form.is_valid():
        ville, service = form.cleaned_data["ville"], form.cleaned_data["service"]
    b = stats.bilan_mensuel(annee, mois, ville=ville, service=service)
    fmt = request.GET.get("format")
    nom = "bilan-%04d-%02d" % (annee, mois)
    if fmt == "csv":
        return _bilan_csv(b, nom)
    if fmt == "xlsx":
        return _bilan_xlsx(b, nom, annee, mois)
    return render(request, "pointages/bilan.html", {
        "b": b, "form": form, "mois": "%04d-%02d" % (annee, mois),
        "query": request.GET.urlencode(),
    })


ENTETES_BILAN = ["Matricule", "Nom", "Prénom", "Service", "Mode de paie", "Salaire / taux",
                 "Jours travaillés", "Heures", "Jours de congé", "Jours d'absence",
                 "Salaire théorique", "Salaire réel"]


def _ligne_bilan(l):
    p = l["personne"]
    return [p.matricule, p.nom, p.prenoms, str(p.service or ""), p.get_mode_paie_display(), float(p.taux),
            l["jours"], float(round(l["heures"], 2)), l["conges"], l["absences"],
            float(l["theorique"]), float(l["reel"])]


def _bilan_csv(b, nom):
    r = HttpResponse(content_type="text/csv; charset=utf-8")
    r["Content-Disposition"] = 'attachment; filename="%s.csv"' % nom
    r.write("﻿")
    w = csv.writer(r, delimiter=";")
    w.writerow(ENTETES_BILAN)
    for l in b["lignes"]:
        w.writerow(_ligne_bilan(l))
    return r


def _bilan_xlsx(b, nom, annee, mois):
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill

    wb = Workbook()
    ws = wb.active
    ws.title = "Bilan %02d-%04d" % (mois, annee)
    ws.append(["%s — Bilan du mois %02d/%04d (%d jours ouvrés)"
               % (settings.POINTAGE_MAX["NOM"], mois, annee, b["jours_ouvres"])])
    ws["A1"].font = Font(bold=True, size=14)
    ws.append([])
    ws.append(ENTETES_BILAN)
    for c in ws[3]:
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor="1F4E79")
    for l in b["lignes"]:
        ws.append(_ligne_bilan(l))
    t = b["total"]
    ws.append(["", "TOTAL", "", "", "", "", t["jours"], float(round(t["heures"], 2)), "", "",
               float(t["theorique"]), float(t["reel"])])
    for c in ws[ws.max_row]:
        c.font = Font(bold=True)
    for col, largeur in zip("ABCDEFGHIJKL", [11, 18, 16, 18, 13, 13, 10, 9, 10, 10, 15, 15]):
        ws.column_dimensions[col].width = largeur
    buf = BytesIO()
    wb.save(buf)
    r = HttpResponse(buf.getvalue(),
                     content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    r["Content-Disposition"] = 'attachment; filename="%s.xlsx"' % nom
    return r


@admin_requis
def journal(request):
    qs = Journal.objects.select_related("utilisateur")
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(Q(details__icontains=q) | Q(objet__icontains=q) | Q(utilisateur__username__icontains=q))
    page = Paginator(qs, 50).get_page(request.GET.get("page"))
    return render(request, "pointages/journal.html", {"page": page, "q": q})


# ---------------------------------------------------------------------------
# Pointage (pointeur et administrateur)
# ---------------------------------------------------------------------------

@pointeur_requis
def pointage(request):
    admin = est_admin(request.user)
    if request.method == "POST" and "choisir_lieu" in request.POST:
        lieu = LieuForm(request.POST)
        if lieu.is_valid():
            request.session["ville"] = lieu.cleaned_data["ville"].pk if lieu.cleaned_data["ville"] else None
            request.session["service"] = lieu.cleaned_data["service"].pk if lieu.cleaned_data["service"] else None
        return redirect("pointage")

    ville, service = _lieu_session(request)
    form = PointageManuelForm(request.POST or None, admin=admin,
                              initial={"ville": ville, "service": service})
    if request.method == "POST" and form.is_valid():
        d = form.cleaned_data
        Pointage.objects.create(personne=d["personne"], checkin=d["checkin"], checkout=d["checkout"],
                                ville=d["ville"] or ville, service=d["service"] or service,
                                source="manuel", saisi_par=request.user)
        messages.success(request, "Pointage enregistré pour %s." % d["personne"])
        return redirect("pointage")

    jour = timezone.localdate()
    du_jour = Pointage.objects.filter(checkin__date=jour).select_related("personne", "service", "saisi_par")
    if ville:
        du_jour = du_jour.filter(ville=ville)
    if service:
        du_jour = du_jour.filter(service=service)
    return render(request, "pointages/pointage.html", {
        "form": form, "lieu": LieuForm(initial={"ville": ville, "service": service}),
        "ville": ville, "service": service, "du_jour": du_jour, "jour": jour,
    })


@pointeur_requis
@require_POST
def scan(request):
    code = request.POST.get("code", "").strip()
    personne = (Personne.objects.filter(code_badge=code).first()
                or Personne.objects.filter(matricule__iexact=code).first()) if code else None
    if not personne:
        return JsonResponse({"ok": False, "message": "Badge inconnu : %s" % code[:40]}, status=404)
    if not personne.actif:
        return JsonResponse({"ok": False, "message": "%s n'est plus actif." % personne}, status=403)
    ville, service = _lieu_session(request)
    resultat, p = pointer(personne, source="qr", user=request.user, ville=ville, service=service)
    textes = {ARRIVEE: "Arrivée enregistrée", SORTIE: "Sortie enregistrée",
              TROP_COURT: "Déjà pointé il y a moins de %d min" % settings.POINTAGE_MAX["DELAI_MIN_MINUTES"]}
    return JsonResponse({
        "ok": resultat != TROP_COURT, "resultat": resultat, "message": textes[resultat],
        "nom": str(personne), "matricule": personne.matricule,
        "heure": timezone.localtime().strftime("%H:%M"),
        "photo": personne.photo.url if personne.photo else None,
    })


def _peut_modifier_pointage(user, p):
    if est_admin(user):
        return True
    return timezone.localtime(p.checkin).date() == timezone.localdate()


@pointeur_requis
def pointage_modifier(request, pk):
    p = get_object_or_404(Pointage, pk=pk)
    admin = est_admin(request.user)
    if not _peut_modifier_pointage(request.user, p):
        messages.error(request, "Seul l'administrateur peut modifier un pointage d'un autre jour.")
        return redirect("pointages_liste")
    initial = {"pk": p.pk, "personne": p.personne, "date": timezone.localtime(p.checkin).date(),
               "arrivee": timezone.localtime(p.checkin).time().replace(second=0, microsecond=0),
               "depart": timezone.localtime(p.checkout).time().replace(second=0, microsecond=0) if p.checkout else None,
               "ville": p.ville, "service": p.service}
    form = PointageManuelForm(request.POST or None, admin=admin, initial=initial)
    if request.method == "POST" and form.is_valid():
        d = form.cleaned_data
        # Pour un pointeur, le formulaire n'a pas de date : il utilise celle du jour,
        # qui est aussi celle du pointage (seuls ceux du jour lui sont modifiables).
        p.checkin, p.checkout = d["checkin"], d["checkout"]
        p.personne, p.ville, p.service = d["personne"], d["ville"], d["service"]
        p.save()
        messages.success(request, "Pointage modifié.")
        return redirect(request.GET.get("suite") or "pointages_liste")
    return render(request, "pointages/pointage_form.html", {"form": form, "p": p})


@admin_requis
@require_POST
def pointage_supprimer(request, pk):
    p = get_object_or_404(Pointage, pk=pk)
    p.delete()
    messages.success(request, "Pointage supprimé.")
    return redirect(request.POST.get("suite") or "pointages_liste")


@pointeur_requis
def pointages_liste(request):
    admin = est_admin(request.user)
    qs = Pointage.objects.select_related("personne", "ville", "service", "saisi_par")
    if not admin:
        qs = qs.filter(saisi_par=request.user)
    lieu = LieuForm(request.GET or None)
    if lieu.is_valid():
        if lieu.cleaned_data["ville"]:
            qs = qs.filter(ville=lieu.cleaned_data["ville"])
        if lieu.cleaned_data["service"]:
            qs = qs.filter(service=lieu.cleaned_data["service"])
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(Q(personne__nom__icontains=q) | Q(personne__prenoms__icontains=q)
                       | Q(personne__matricule__iexact=q))
    for champ, filtre in (("du", "checkin__date__gte"), ("au", "checkin__date__lte")):
        try:
            qs = qs.filter(**{filtre: datetime.strptime(request.GET.get(champ, ""), "%Y-%m-%d").date()})
        except ValueError:
            pass
    if request.GET.get("ouverts"):
        qs = qs.filter(checkout__isnull=True)
    page = Paginator(qs, 50).get_page(request.GET.get("page"))
    aujourd_hui = timezone.localdate()
    for p in page:
        p.modifiable = admin or timezone.localtime(p.checkin).date() == aujourd_hui
    params = request.GET.copy()
    params.pop("page", None)
    return render(request, "pointages/pointages_liste.html", {
        "page": page, "lieu": lieu, "q": q, "params": params.urlencode(),
        "du": request.GET.get("du", ""), "au": request.GET.get("au", ""), "ouverts": request.GET.get("ouverts"),
    })


# ---------------------------------------------------------------------------
# Employés
# ---------------------------------------------------------------------------

@pointeur_requis
def employes(request):
    qs = Personne.objects.select_related("service", "ville")
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(Q(nom__icontains=q) | Q(prenoms__icontains=q) | Q(matricule__iexact=q) | Q(cin__iexact=q))
    statut = request.GET.get("statut", "actifs")
    if statut == "actifs":
        qs = qs.filter(actif=True)
    elif statut == "inactifs":
        qs = qs.filter(actif=False)
    page = Paginator(qs, 50).get_page(request.GET.get("page"))
    return render(request, "pointages/employes.html", {"page": page, "q": q, "statut": statut})


def _peut_modifier_employe(user, personne):
    return est_admin(user) or (personne.cree_par_id == user.pk and personne.modifiable_par_pointeur())


@pointeur_requis
def employe_form(request, pk=None):
    personne = get_object_or_404(Personne, pk=pk) if pk else None
    if personne and not _peut_modifier_employe(request.user, personne):
        messages.error(request, "Le délai de 24 h pour modifier cette fiche est dépassé. "
                                "Contactez l'administrateur.")
        return redirect("employe_fiche", pk=personne.pk)
    form = PersonneForm(request.POST or None, request.FILES or None, instance=personne)
    if not est_admin(request.user):
        for champ in ("mode_paie", "taux", "date_sortie"):
            form.fields.pop(champ)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        if not personne:
            obj.cree_par = request.user
        obj.save()
        messages.success(request, "Fiche enregistrée : %s (%s)." % (obj, obj.matricule))
        return redirect("employe_fiche", pk=obj.pk)
    return render(request, "pointages/employe_form.html", {"form": form, "personne": personne})


@pointeur_requis
def employe_fiche(request, pk):
    personne = get_object_or_404(Personne.objects.select_related("service", "ville", "contrat"), pk=pk)
    annees = sorted({d.year for d in personne.pointage_set.dates("checkin", "year")}
                    | {timezone.localdate().year}, reverse=True)
    try:
        annee = int(request.GET.get("annee", annees[0]))
    except ValueError:
        annee = annees[0]
    pointages = personne.pointage_set.filter(checkin__year=annee).select_related("service")[:200]
    conges = personne.conge_set.filter(debut__year=annee)
    a, m = _mois_demande(request)
    return render(request, "pointages/employe_fiche.html", {
        "p": personne, "pointages": pointages, "conges": conges, "annee": annee, "annees": annees,
        "solde": personne.solde_conge(), "admin": est_admin(request.user),
        "modifiable": _peut_modifier_employe(request.user, personne),
        "bilan": stats.bilan_mensuel(a, m, personne=personne)["lignes"][0] if est_admin(request.user) else None,
    })


def _qr(personne):
    if not personne.code_badge:
        personne.save()
    return segno.make(personne.code_badge, error="m")


@pointeur_requis
def badge(request, pk):
    personne = get_object_or_404(Personne, pk=pk)
    qr = _qr(personne)
    return render(request, "pointages/badge.html", {"p": personne, "qr": qr.svg_data_uri(scale=6, border=2)})


@pointeur_requis
def badge_png(request, pk):
    personne = get_object_or_404(Personne, pk=pk)
    buf = BytesIO()
    _qr(personne).save(buf, kind="png", scale=12, border=3)
    r = HttpResponse(buf.getvalue(), content_type="image/png")
    r["Content-Disposition"] = 'attachment; filename="badge-%s.png"' % personne.matricule
    return r


@pointeur_requis
def media_protege(request, path):
    """Photos et pièces d'identité : réservées aux utilisateurs connectés."""
    from django.views.static import serve
    return serve(request, path, document_root=settings.MEDIA_ROOT)


# ---------------------------------------------------------------------------
# Import Excel / CSV
# ---------------------------------------------------------------------------

@admin_requis
def importer(request):
    from . import importation

    rapport = type_import = None
    if request.method == "POST":
        type_import = request.POST.get("type")
        fichier = request.FILES.get("fichier")
        simuler = request.POST.get("action") == "verifier"
        if type_import not in ("employes", "pointages") or not fichier:
            messages.error(request, "Choisissez un type d'import et un fichier.")
        elif not fichier.name.lower().endswith((".xlsx", ".xlsm", ".csv", ".txt")):
            messages.error(request, "Format non pris en charge : utilisez un fichier Excel (.xlsx) ou CSV.")
        else:
            try:
                lignes = importation.lire_fichier(fichier)
                fonction = importation.importer_employes if type_import == "employes" else importation.importer_pointages
                rapport = fonction(lignes, user=request.user, simuler=simuler)
                rapport["simulation"] = simuler
            except Exception as e:  # noqa: BLE001 — fichier illisible
                messages.error(request, "Impossible de lire le fichier : %s" % e)
    return render(request, "pointages/importer.html", {"rapport": rapport, "type_import": type_import})


@admin_requis
def importer_modele(request, type_import):
    from . import importation

    if type_import not in ("employes", "pointages"):
        raise PermissionDenied
    r = HttpResponse(importation.modele(type_import),
                     content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    r["Content-Disposition"] = 'attachment; filename="modele-%s.xlsx"' % type_import
    return r
