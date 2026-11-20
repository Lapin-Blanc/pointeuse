"""Import d'employés et de pointages depuis un fichier Excel (.xlsx) ou CSV."""
import csv
import io
import unicodedata
from datetime import date, datetime, time
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.utils import timezone

from .models import Personne, Pointage, Service, TypeContrat, Ville

# Nom de champ -> en-têtes acceptés (sans accents, en minuscules)
COLONNES_EMPLOYES = {
    "matricule": ["matricule", "mat", "id", "code"],
    "nom": ["nom", "nom de famille", "last name"],
    "prenoms": ["prenom", "prenoms", "first name"],
    "cin": ["cin", "carte nationale", "cni", "n cin"],
    "cnss": ["cnss", "n cnss", "numero cnss"],
    "sexe": ["sexe", "genre"],
    "date_naissance": ["date de naissance", "naissance", "date naissance"],
    "lieu_naissance": ["lieu de naissance", "lieu naissance"],
    "telephone": ["telephone", "tel", "gsm", "portable"],
    "email": ["email", "e-mail", "mail"],
    "adresse": ["adresse"],
    "localite": ["localite", "ville de residence"],
    "poste": ["poste", "fonction", "emploi"],
    "qualification": ["qualification", "qualite"],
    "ville": ["ville", "site"],
    "service": ["service", "chantier", "departement"],
    "contrat": ["contrat", "type de contrat"],
    "date_entree": ["date d'entree", "date entree", "entree", "date d embauche", "embauche"],
    "mode_paie": ["mode de paie", "paie", "type de paie", "mode paie"],
    "taux": ["salaire", "taux", "salaire / taux", "montant"],
    "banque": ["banque"],
    "rib": ["rib", "iban"],
}

COLONNES_POINTAGES = {
    "matricule": ["matricule", "mat", "code", "cin"],
    "date": ["date", "jour"],
    "arrivee": ["arrivee", "entree", "heure d'arrivee", "heure arrivee", "debut"],
    "sortie": ["sortie", "depart", "heure de depart", "heure de sortie", "fin"],
}


def _norm(texte):
    texte = unicodedata.normalize("NFKD", str(texte or "")).encode("ascii", "ignore").decode()
    return " ".join(texte.lower().replace("_", " ").replace("°", "").replace("’", "'").split())


def lire_fichier(fichier):
    """Renvoie une liste de lignes (listes de valeurs), en-tête comprise."""
    nom = fichier.name.lower()
    if nom.endswith((".xlsx", ".xlsm")):
        from openpyxl import load_workbook
        wb = load_workbook(fichier, read_only=True, data_only=True)
        return [list(r) for r in wb.active.iter_rows(values_only=True)]
    brut = fichier.read()
    for enc in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            texte = brut.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    dialecte = csv.Sniffer().sniff(texte[:4096], delimiters=";,\t") if texte.strip() else csv.excel
    return [r for r in csv.reader(io.StringIO(texte), dialecte)]


def _associer(entete, colonnes):
    index = {}
    for i, titre in enumerate(entete):
        t = _norm(titre)
        for champ, alias in colonnes.items():
            if champ not in index and t in alias:
                index[champ] = i
    return index


def _texte(v):
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    return str(v).strip()


def _date(v):
    if v in (None, ""):
        return None
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    s = _texte(v)
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%d.%m.%Y", "%d/%m/%y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    raise ValueError("date illisible « %s » (format attendu : JJ/MM/AAAA)" % s)


def _heure(v):
    if v in (None, ""):
        return None
    if isinstance(v, datetime):
        return v.time()
    if isinstance(v, time):
        return v
    if isinstance(v, float) and 0 <= v < 1:  # heure Excel stockée en fraction de jour
        minutes = round(v * 24 * 60)
        return time(minutes // 60, minutes % 60)
    s = _texte(v).lower().replace("h", ":")
    if s.endswith(":"):
        s += "00"
    for fmt in ("%H:%M", "%H:%M:%S"):
        try:
            return datetime.strptime(s, fmt).time()
        except ValueError:
            pass
    raise ValueError("heure illisible « %s » (format attendu : HH:MM)" % _texte(v))


def _decimal(v):
    if v in (None, ""):
        return Decimal(0)
    try:
        return Decimal(_texte(v).replace(" ", "").replace(" ", "").replace(",", "."))
    except InvalidOperation:
        raise ValueError("montant illisible « %s »" % _texte(v))


def _mode_paie(v):
    t = _norm(v)
    if t.startswith("h"):
        return "H"
    if t.startswith("j"):
        return "J"
    return "M"


def _sexe(v):
    t = _norm(v)
    return "F" if t.startswith("f") else ("M" if t[:1] in ("m", "h") else "")


def importer_employes(lignes, user=None, simuler=False):
    if not lignes:
        raise ValueError("Le fichier est vide.")
    index = _associer(lignes[0], COLONNES_EMPLOYES)
    if "nom" not in index:
        raise ValueError("Colonne « Nom » introuvable. Utilisez le modèle à télécharger.")
    rapport = {"crees": 0, "maj": 0, "erreurs": [], "colonnes": sorted(index)}
    with transaction.atomic():
        for n, ligne in enumerate(lignes[1:], start=2):
            val = lambda c: ligne[index[c]] if c in index and index[c] < len(ligne) else None
            if not _texte(val("nom")):
                continue
            try:
                matricule, cin = _texte(val("matricule")), _texte(val("cin"))
                p = None
                if matricule:
                    p = Personne.objects.filter(matricule__iexact=matricule).first()
                if not p and cin:
                    p = Personne.objects.filter(cin__iexact=cin).first()
                cree = p is None
                p = p or Personne(cree_par=user)
                for champ in ("nom", "prenoms", "cin", "cnss", "lieu_naissance", "telephone", "email",
                              "adresse", "localite", "poste", "qualification", "banque", "rib"):
                    if champ in index and _texte(val(champ)):
                        setattr(p, champ, _texte(val(champ)))
                if matricule:
                    p.matricule = matricule
                if "sexe" in index:
                    p.sexe = _sexe(val("sexe")) or p.sexe
                for champ in ("date_naissance", "date_entree"):
                    if champ in index and val(champ) not in (None, ""):
                        setattr(p, champ, _date(val(champ)))
                if "mode_paie" in index and _texte(val("mode_paie")):
                    p.mode_paie = _mode_paie(val("mode_paie"))
                if "taux" in index and _texte(val("taux")):
                    p.taux = _decimal(val("taux"))
                if p.rib:
                    p.paiement_banque = True
                if _texte(val("ville")):
                    p.ville = Ville.objects.get_or_create(nom=_texte(val("ville")))[0]
                if _texte(val("service")):
                    p.service = Service.objects.get_or_create(nom=_texte(val("service")),
                                                              defaults={"ville": p.ville})[0]
                if _texte(val("contrat")):
                    p.contrat = TypeContrat.objects.get_or_create(nom=_texte(val("contrat")))[0]
                p.full_clean(exclude=["photo", "document", "matricule"])
                with transaction.atomic():
                    p.save()
                rapport["crees" if cree else "maj"] += 1
            except Exception as e:  # noqa: BLE001 — on rapporte l'erreur de la ligne et on continue
                rapport["erreurs"].append("Ligne %d : %s" % (n, _message(e)))
        if simuler:
            transaction.set_rollback(True)
    return rapport


def importer_pointages(lignes, user=None, simuler=False):
    if not lignes:
        raise ValueError("Le fichier est vide.")
    index = _associer(lignes[0], COLONNES_POINTAGES)
    manquantes = [c for c in ("matricule", "date", "arrivee") if c not in index]
    if manquantes:
        raise ValueError("Colonnes introuvables : %s. Utilisez le modèle à télécharger." % ", ".join(manquantes))
    rapport = {"crees": 0, "maj": 0, "ignores": 0, "erreurs": [], "colonnes": sorted(index)}
    with transaction.atomic():
        for n, ligne in enumerate(lignes[1:], start=2):
            val = lambda c: ligne[index[c]] if c in index and index[c] < len(ligne) else None
            code = _texte(val("matricule"))
            if not code:
                continue
            try:
                p = (Personne.objects.filter(matricule__iexact=code).first()
                     or Personne.objects.filter(cin__iexact=code).first())
                if not p:
                    raise ValueError("employé « %s » inconnu (importez d'abord les employés)" % code)
                jour = _date(val("date"))
                arrivee, sortie = _heure(val("arrivee")), _heure(val("sortie"))
                checkin = timezone.make_aware(datetime.combine(jour, arrivee))
                checkout = timezone.make_aware(datetime.combine(jour, sortie)) if sortie else None
                if checkout and checkout <= checkin:
                    raise ValueError("la sortie (%s) est avant l'arrivée (%s)" % (sortie, arrivee))
                if p.pointage_set.filter(checkin=checkin).exists():
                    rapport["ignores"] += 1  # déjà importé
                    continue
                Pointage.objects.create(personne=p, checkin=checkin, checkout=checkout, ville=p.ville,
                                        service=p.service, source="manuel", saisi_par=user)
                rapport["crees"] += 1
            except Exception as e:  # noqa: BLE001
                rapport["erreurs"].append("Ligne %d : %s" % (n, _message(e)))
        if simuler:
            transaction.set_rollback(True)
    return rapport


def _message(e):
    if hasattr(e, "message_dict"):
        return " ; ".join("%s : %s" % (k, " ".join(v)) for k, v in e.message_dict.items())
    return str(e)


def modele(type_import):
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill

    wb = Workbook()
    ws = wb.active
    if type_import == "employes":
        ws.title = "Employés"
        ws.append(["Matricule", "Nom", "Prénom", "CIN", "CNSS", "Sexe", "Date de naissance", "Téléphone",
                   "Poste", "Service", "Ville", "Contrat", "Date d'entrée", "Mode de paie", "Salaire", "Banque", "RIB"])
        ws.append(["EMP0101", "Alaoui", "Karim", "BK123456", "123456789", "M", "15/03/1990", "0612345678",
                   "Maçon", "Chantier Anfa", "Casablanca", "CDI", "01/02/2024", "Mensuel", 4500, "", ""])
        ws.append(["", "Bennani", "Salma", "BE654321", "", "F", "", "", "Comptable", "Bureau", "Rabat", "CDD",
                   "01/09/2025", "Journalier", 250, "CIH", "230780000000000000000000"])
    else:
        ws.title = "Pointages"
        ws.append(["Matricule", "Date", "Arrivée", "Sortie"])
        ws.append(["EMP0101", "03/11/2026", "08:00", "17:00"])
        ws.append(["EMP0101", "04/11/2026", "07:55", "16:30"])
    for c in ws[1]:
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor="1F4E79")
    for col in ws.columns:
        ws.column_dimensions[col[0].column_letter].width = 16
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
