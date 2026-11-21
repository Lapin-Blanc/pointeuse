from datetime import datetime, timedelta

from django import forms
from django.utils import timezone

from .models import Personne, Service, Ville


class DateInput(forms.DateInput):
    input_type = "date"


class TimeInput(forms.TimeInput):
    input_type = "time"


class PersonneForm(forms.ModelForm):
    class Meta:
        model = Personne
        fields = [
            "photo", "nom", "prenoms", "sexe", "date_naissance", "lieu_naissance", "nationalite",
            "cin", "cnss", "telephone", "email", "situation_familiale", "enfants",
            "adresse", "code_postal", "localite",
            "poste", "qualification", "ville", "service", "contrat", "date_entree", "date_sortie",
            "mode_paie", "taux", "paiement_banque", "banque", "rib", "document",
        ]
        widgets = {"date_naissance": DateInput(), "date_entree": DateInput(), "date_sortie": DateInput()}

    GROUPES = [
        ("Identité", ["photo", "nom", "prenoms", "sexe", "date_naissance", "lieu_naissance", "nationalite", "cin", "cnss"]),
        ("Contact et famille", ["telephone", "email", "situation_familiale", "enfants", "adresse", "code_postal", "localite"]),
        ("Poste", ["poste", "qualification", "ville", "service", "contrat", "date_entree", "date_sortie"]),
        ("Paie et banque", ["mode_paie", "taux", "paiement_banque", "banque", "rib"]),
        ("Pièce d'identité scannée", ["document"]),
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["photo"].widget.attrs["accept"] = "image/*"
        self.fields["document"].widget.attrs["accept"] = "image/*,application/pdf"

    def groupes(self):
        for titre, noms in self.GROUPES:
            champs = [self[n] for n in noms if n in self.fields]
            if champs:
                yield titre, champs


class LieuForm(forms.Form):
    ville = forms.ModelChoiceField(Ville.objects.all(), required=False, empty_label="— Toutes —")
    service = forms.ModelChoiceField(Service.objects.all(), required=False, empty_label="— Tous —",
                                     label="Service / chantier")


class PointageManuelForm(forms.Form):
    """Saisie d'un pointage. Le pointeur ne choisit que les heures : la date est celle du jour."""
    personne = forms.ModelChoiceField(Personne.objects.filter(actif=True), label="Employé")
    date = forms.DateField(widget=DateInput(), required=False)
    arrivee = forms.TimeField(widget=TimeInput(), label="Arrivée")
    depart = forms.TimeField(widget=TimeInput(), label="Départ", required=False)
    ville = forms.ModelChoiceField(Ville.objects.all(), required=False)
    service = forms.ModelChoiceField(Service.objects.all(), required=False, label="Service / chantier")

    def __init__(self, *args, admin=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.admin = admin
        if not admin:
            del self.fields["date"]

    def clean(self):
        data = super().clean()
        jour = data.get("date") if self.admin else None
        jour = jour or timezone.localdate()
        if data.get("arrivee"):
            data["checkin"] = timezone.make_aware(datetime.combine(jour, data["arrivee"]))
        data["checkout"] = (timezone.make_aware(datetime.combine(jour, data["depart"]))
                            if data.get("depart") else None)
        if data.get("checkin") and data["checkout"] and data["checkout"] <= data["checkin"]:
            raise forms.ValidationError("L'heure de départ doit être après l'heure d'arrivée.")
        if data.get("checkin") and data["checkin"] > timezone.now() + timedelta(minutes=5):
            raise forms.ValidationError("On ne peut pas pointer une heure dans le futur.")
        personne = data.get("personne")
        if personne and data.get("checkin"):
            fin = data["checkout"] or data["checkin"]
            chevauche = personne.pointage_set.filter(checkin__date=jour).exclude(pk=self.initial.get("pk"))
            for p in chevauche:
                p_fin = p.checkout or timezone.now()
                if p.checkin <= fin and data["checkin"] <= p_fin:
                    raise forms.ValidationError(
                        "Ce pointage chevauche un pointage existant (%s). Contactez l'administrateur pour le corriger."
                        % timezone.localtime(p.checkin).strftime("%H:%M"))
        return data
