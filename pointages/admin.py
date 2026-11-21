from django.contrib import admin

from .models import Conge, Journal, JourFerie, Personne, Pointage, Service, TypeContrat, Ville


@admin.register(Pointage)
class PointageAdmin(admin.ModelAdmin):
    fields = ["personne", "checkin", "checkout", "ville", "service", "source"]
    list_display = ["personne", "checkin", "checkout", "is_closed", "duration", "ville", "service", "source", "saisi_par"]
    list_filter = ["ville", "service", "source", "checkin"]
    search_fields = ["personne__nom", "personne__prenoms", "personne__matricule"]
    date_hierarchy = "checkin"
    autocomplete_fields = ["personne"]

    def save_model(self, request, obj, form, change):
        if not change:
            obj.saisi_par = request.user
        super().save_model(request, obj, form, change)


class CongeInline(admin.TabularInline):
    model = Conge
    extra = 0
    fields = ["type", "debut", "fin", "motif"]


@admin.register(Personne)
class PersonneAdmin(admin.ModelAdmin):
    fieldsets = [
        ('Renseignements généraux', {"fields": ["photo", ("nom", "prenoms", "sexe"), ("date_naissance", "lieu_naissance"),
                                                "nationalite", ("cin", "cnss"), ("telephone", "email"),
                                                ("situation_familiale", "enfants")]}),
        ('Adresse', {"fields": ["adresse", ("code_postal", "localite")]}),
        ('Poste', {"fields": [("matricule", "actif"), ("poste", "qualification"), ("ville", "service", "contrat"),
                              ("date_entree", "date_sortie")]}),
        ('Paie', {"fields": [("mode_paie", "taux"), ("paiement_banque", "banque", "rib")]}),
        ('Carte d\'identité (eID)', {"fields": ["num_nat", "num_carte", "debut_val", "fin_val",
                                                "commune_delivrance", "document"], "classes": ["collapse"]}),
    ]
    list_display = ["matricule", "nom", "prenoms", "poste", "service", "ville", "mode_paie", "taux", "actif"]
    list_filter = ["actif", "ville", "service", "contrat", "mode_paie", "sexe"]
    search_fields = ["nom", "prenoms", "matricule", "cin", "num_nat"]
    inlines = [CongeInline]
    actions = ["nouveau_badge"]

    @admin.action(description="Générer un nouveau badge QR (l'ancien ne marchera plus)")
    def nouveau_badge(self, request, queryset):
        for p in queryset:
            p.code_badge = None
            p.save()
        self.message_user(request, "%d badge(s) régénéré(s)." % queryset.count())


@admin.register(Conge)
class CongeAdmin(admin.ModelAdmin):
    list_display = ["personne", "type", "debut", "fin", "jours_calendaires", "jours_ouvres", "motif"]
    list_filter = ["type", "debut"]
    search_fields = ["personne__nom", "personne__prenoms", "personne__matricule"]
    date_hierarchy = "debut"
    autocomplete_fields = ["personne"]

    def save_model(self, request, obj, form, change):
        if not change:
            obj.cree_par = request.user
        super().save_model(request, obj, form, change)


@admin.register(JourFerie)
class JourFerieAdmin(admin.ModelAdmin):
    list_display = ["date", "nom"]
    date_hierarchy = "date"


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ["nom", "ville", "heure_debut"]
    list_filter = ["ville"]
    search_fields = ["nom"]


admin.site.register(Ville, search_fields=["nom"])
admin.site.register(TypeContrat)


@admin.register(Journal)
class JournalAdmin(admin.ModelAdmin):
    list_display = ["date", "utilisateur", "action", "objet", "details"]
    list_filter = ["action", "objet", "utilisateur"]
    search_fields = ["details"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
