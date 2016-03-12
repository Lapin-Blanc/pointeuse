from django.contrib import admin
from .models import Personne, Pointage

# Register your models here.
class PointageAdmin(admin.ModelAdmin):
    fieldsets = [
        ('Pointages', {"fields" : ["personne", "checkin", "checkout"]}),
    ]
    list_display = ["personne","checkin","checkout","is_closed","duration"]
    list_filter = ["personne__nom", "checkin"]
    search_fields = ["personne__nom"]
    date_hierarchy = "checkin"

class PersonneAdmin(admin.ModelAdmin):
    fieldsets = [
        ('Renseignement généraux',  {"fields" : [("nom", "prenoms", "sexe"), "date_naissance", "lieu_naissance", "nationalite","num_nat"]}),
        ('Adresse', {"fields" : ["adresse", "code_postal", "localite"]}),
        ('Carte d\'identité', {"fields" : ["num_carte", "debut_val", "fin_val", "commune_delivrance"], "classes" : ["collapse"]}),
    ]
    list_display = ['nom','prenoms','sexe','date_naissance','lieu_naissance','nationalite','code_postal','localite']
    list_filter = ['sexe', 'code_postal', 'nationalite']
    search_fields = ['nom', 'prenoms']
    date_hierarchy = 'date_naissance'
    
admin.site.register(Personne, PersonneAdmin)
admin.site.register(Pointage, PointageAdmin)

