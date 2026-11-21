from datetime import date, datetime, time as time_obj, timedelta
from decimal import Decimal

from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from . import stats
from .models import Conge, Journal, JourFerie, Personne, Pointage, Service, Ville
from .services import ARRIVEE, GROUPE_POINTEUR, SORTIE, TROP_COURT, pointer


def aware(y, m, d, h=8, mi=0):
    return timezone.make_aware(datetime(y, m, d, h, mi))


class Base(TestCase):
    def setUp(self):
        self.ville = Ville.objects.create(nom="Casablanca")
        self.service = Service.objects.create(nom="Chantier A", ville=self.ville, heure_debut="08:00")
        self.p = Personne.objects.create(nom="Alaoui", prenoms="Karim Ahmed", ville=self.ville,
                                         service=self.service, mode_paie="M", taux=Decimal("8623"))
        self.admin = User.objects.create_superuser("admin", "", "motdepasse-admin")
        self.pointeur = User.objects.create_user("pointeur", "", "motdepasse-pointeur")
        self.pointeur.groups.add(Group.objects.get(name=GROUPE_POINTEUR))


class ModeleTests(Base):
    def test_matricule_et_badge_automatiques(self):
        self.assertEqual(self.p.matricule, "EMP%04d" % self.p.pk)
        self.assertEqual(len(self.p.code_badge), 16)

    def test_pointer_arrivee_puis_sortie(self):
        t = aware(2026, 3, 2, 8, 0)
        r, pt = pointer(self.p, maintenant=t)
        self.assertEqual(r, ARRIVEE)
        r, _ = pointer(self.p, maintenant=t + timedelta(seconds=20))
        self.assertEqual(r, TROP_COURT)
        r, pt2 = pointer(self.p, maintenant=t + timedelta(hours=2))
        self.assertEqual((r, pt2.pk), (SORTIE, pt.pk))
        self.assertEqual(pt2.duration(), "2:00")
        r, pt3 = pointer(self.p, maintenant=t + timedelta(hours=2, minutes=30))
        self.assertEqual(r, ARRIVEE)
        self.assertNotEqual(pt3.pk, pt.pk)

    def test_conge_sans_jours_feries_ni_dimanches(self):
        # Du lundi 27 juillet au samedi 1er août 2026 : 6 jours, le 30 juillet (Fête du Trône) est férié.
        JourFerie.objects.create(date=date(2026, 7, 30), nom="Fête du Trône")
        c = Conge.objects.create(personne=self.p, debut=date(2026, 7, 27), fin=date(2026, 8, 2))
        self.assertEqual(c.jours_calendaires(), 7)
        self.assertEqual(c.jours_ouvres(), 5)  # dimanche 2 août et 30 juillet exclus

    def test_journal_audit(self):
        self.assertTrue(Journal.objects.filter(objet="Employé", action="Création", objet_id=self.p.pk).exists())


class BilanTests(Base):
    def test_salaire_mensuel_au_prorata(self):
        # Exemple de la vidéo : 8623 DH/mois, 43 h 31 sur le mois -> environ 1965 DH (base 191 h).
        debut = aware(2026, 3, 2, 8, 0)
        for i, minutes in enumerate([8 * 60 + 40, 8 * 60 + 40, 8 * 60 + 40, 8 * 60 + 40, 8 * 60 + 51]):
            d = debut + timedelta(days=i)
            Pointage.objects.create(personne=self.p, checkin=d, checkout=d + timedelta(minutes=minutes))
        l = stats.bilan_mensuel(2026, 3, personne=self.p)["lignes"][0]
        self.assertEqual(l["jours"], 5)
        self.assertEqual(l["heures_txt"], "43h31")
        self.assertEqual(l["theorique"], Decimal("8623.00"))
        self.assertAlmostEqual(float(l["reel"]), 8623 * (43 + 31 / 60) / 191, delta=0.01)

    def test_salaire_journalier_et_horaire(self):
        j = Personne.objects.create(nom="B", prenoms="J", mode_paie="J", taux=Decimal("200"))
        h = Personne.objects.create(nom="C", prenoms="H", mode_paie="H", taux=Decimal("20"))
        for pers in (j, h):
            for jour in (2, 3, 4):
                Pointage.objects.create(personne=pers, checkin=aware(2026, 3, jour, 8), checkout=aware(2026, 3, jour, 16))
        self.assertEqual(stats.bilan_mensuel(2026, 3, personne=j)["lignes"][0]["reel"], Decimal("600.00"))
        self.assertEqual(stats.bilan_mensuel(2026, 3, personne=h)["lignes"][0]["reel"], Decimal("480.00"))

    def test_conge_paye_compte_pour_mensuel(self):
        Conge.objects.create(personne=self.p, debut=date(2026, 3, 2), fin=date(2026, 3, 7))  # 6 jours ouvrés
        l = stats.bilan_mensuel(2026, 3, personne=self.p)["lignes"][0]
        self.assertAlmostEqual(float(l["reel"]), 8623 * 48 / 191, delta=0.01)

    def test_tableau_de_bord(self):
        maintenant = timezone.localtime()
        arrivee = maintenant.replace(hour=9, minute=0, second=0, microsecond=0)
        if arrivee > maintenant:
            arrivee = maintenant - timedelta(minutes=1)
        Pointage.objects.create(personne=self.p, checkin=arrivee)
        autre = Personne.objects.create(nom="Absent", prenoms="Ali")
        Pointage.objects.create(personne=autre, checkin=arrivee - timedelta(days=2))  # sortie oubliée
        tb = stats.tableau_de_bord(maintenant.year, maintenant.month)
        self.assertEqual(len(tb["presents"]), 1)
        self.assertIn(autre, tb["absents"])
        self.assertEqual(len(tb["sorties_oubliees"]), 1)


class VuesTests(Base):
    def test_pages_admin(self):
        self.client.force_login(self.admin)
        Pointage.objects.create(personne=self.p, checkin=timezone.now() - timedelta(hours=1))
        for nom, args in [("tableau_de_bord", []), ("bilan", []), ("journal", []), ("pointage", []),
                          ("pointages_liste", []), ("employes", []), ("employe_nouveau", []),
                          ("employe_fiche", [self.p.pk]), ("employe_modifier", [self.p.pk]),
                          ("badge", [self.p.pk])]:
            r = self.client.get(reverse(nom, args=args))
            self.assertEqual(r.status_code, 200, nom)
        r = self.client.get(reverse("admin:index"))
        self.assertEqual(r.status_code, 200)

    def test_exports(self):
        self.client.force_login(self.admin)
        r = self.client.get(reverse("bilan") + "?format=xlsx")
        self.assertEqual(r["Content-Type"], "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        r = self.client.get(reverse("bilan") + "?format=csv")
        self.assertIn("Matricule", r.content.decode("utf-8"))
        r = self.client.get(reverse("badge_png", args=[self.p.pk]))
        self.assertEqual(r.content[:4], b"\x89PNG")

    def test_pointeur_restrictions(self):
        self.client.force_login(self.pointeur)
        self.assertEqual(self.client.get(reverse("tableau_de_bord")).status_code, 403)
        self.assertEqual(self.client.get(reverse("bilan")).status_code, 403)
        self.assertEqual(self.client.get(reverse("pointage")).status_code, 200)
        ancien = Pointage.objects.create(personne=self.p, checkin=timezone.now() - timedelta(days=2))
        r = self.client.get(reverse("pointage_modifier", args=[ancien.pk]))
        self.assertRedirects(r, reverse("pointages_liste"))
        r = self.client.post(reverse("pointage_supprimer", args=[ancien.pk]))
        self.assertEqual(r.status_code, 403)
        # Fiche créée par l'admin : non modifiable par le pointeur
        r = self.client.get(reverse("employe_modifier", args=[self.p.pk]))
        self.assertRedirects(r, reverse("employe_fiche", args=[self.p.pk]))

    def test_pointeur_fiche_24h(self):
        self.client.force_login(self.pointeur)
        r = self.client.post(reverse("employe_nouveau"), {"nom": "Nouveau", "prenoms": "Said", "enfants": 0})
        nouveau = Personne.objects.get(nom="Nouveau")
        self.assertEqual(nouveau.cree_par, self.pointeur)
        self.assertEqual(self.client.get(reverse("employe_modifier", args=[nouveau.pk])).status_code, 200)
        Personne.objects.filter(pk=nouveau.pk).update(cree_le=timezone.now() - timedelta(hours=25))
        r = self.client.get(reverse("employe_modifier", args=[nouveau.pk]))
        self.assertRedirects(r, reverse("employe_fiche", args=[nouveau.pk]))

    def test_scan_qr(self):
        self.client.force_login(self.pointeur)
        r = self.client.post(reverse("scan"), {"code": self.p.code_badge}).json()
        self.assertEqual(r["resultat"], ARRIVEE)
        self.assertEqual(Pointage.objects.get().saisi_par, self.pointeur)
        r = self.client.post(reverse("scan"), {"code": self.p.matricule}).json()
        self.assertEqual(r["resultat"], TROP_COURT)
        self.assertEqual(self.client.post(reverse("scan"), {"code": "inconnu"}).status_code, 404)
        Personne.objects.filter(pk=self.p.pk).update(actif=False)
        self.assertEqual(self.client.post(reverse("scan"), {"code": self.p.code_badge}).status_code, 403)

    def test_saisie_manuelle_pointeur_aujourd_hui(self):
        self.client.force_login(self.pointeur)
        r = self.client.post(reverse("pointage"), {"personne": self.p.pk, "arrivee": "00:01", "depart": "00:02"})
        self.assertEqual(r.status_code, 302)
        pt = Pointage.objects.get()
        self.assertEqual(timezone.localtime(pt.checkin).date(), timezone.localdate())
        # chevauchement refusé
        r = self.client.post(reverse("pointage"), {"personne": self.p.pk, "arrivee": "00:01", "depart": "00:02"})
        self.assertContains(r, "chevauche")

    def test_acces_anonyme(self):
        self.assertRedirects(self.client.get(reverse("tableau_de_bord")),
                             reverse("login") + "?next=" + reverse("tableau_de_bord"))
        r = self.client.get("/media/documents/x.pdf")
        self.assertEqual(r.status_code, 302)

    def test_entetes_securite(self):
        r = self.client.get(reverse("login"))
        self.assertIn("default-src 'self'", r["Content-Security-Policy"])


class ImportTests(Base):
    def _fichier(self, nom, contenu):
        from django.core.files.uploadedfile import SimpleUploadedFile
        return SimpleUploadedFile(nom, contenu)

    def test_import_employes_csv_puis_pointages_excel(self):
        from openpyxl import Workbook
        import io
        self.client.force_login(self.admin)
        csv_txt = ("Matricule;Nom;Prénom;CIN;Service;Ville;Contrat;Date d'entrée;Mode de paie;Salaire\n"
                   "A100;Tazi;Amine;BK1;Atelier;Tanger;CDI;01/02/2024;Journalier;250,50\n"
                   ";Sans;Matricule;BK2;;;;;;\n"
                   "A101;Erreur;Date;BK3;;;;32/13/2024;;\n").encode("cp1252")
        r = self.client.post(reverse("importer"), {"type": "employes", "action": "verifier",
                                                   "fichier": self._fichier("e.csv", csv_txt)})
        self.assertEqual(r.context["rapport"]["crees"], 2)
        self.assertFalse(Personne.objects.filter(nom="Tazi").exists())  # simulation : rien enregistré
        r = self.client.post(reverse("importer"), {"type": "employes", "action": "importer",
                                                   "fichier": self._fichier("e.csv", csv_txt)})
        rap = r.context["rapport"]
        self.assertEqual((rap["crees"], len(rap["erreurs"])), (2, 1))
        t = Personne.objects.get(matricule="A100")
        self.assertEqual((t.mode_paie, t.taux, t.service.nom, t.ville.nom), ("J", Decimal("250.50"), "Atelier", "Tanger"))
        self.assertTrue(Personne.objects.get(nom="Sans").matricule.startswith("EMP"))
        # Réimport : mise à jour, pas de doublon
        r = self.client.post(reverse("importer"), {"type": "employes", "action": "importer",
                                                   "fichier": self._fichier("e.csv", csv_txt)})
        self.assertEqual(r.context["rapport"]["maj"], 2)
        self.assertEqual(Personne.objects.filter(nom="Tazi").count(), 1)

        wb = Workbook()
        ws = wb.active
        ws.append(["Matricule", "Date", "Arrivée", "Sortie"])
        ws.append(["A100", datetime(2026, 3, 2), "08:00", "16h30"])
        ws.append(["BK2", "03/03/2026", time_obj(7, 45), None])
        ws.append(["INCONNU", "03/03/2026", "08:00", "17:00"])
        buf = io.BytesIO(); wb.save(buf)
        r = self.client.post(reverse("importer"), {"type": "pointages", "action": "importer",
                                                   "fichier": self._fichier("p.xlsx", buf.getvalue())})
        rap = r.context["rapport"]
        self.assertEqual((rap["crees"], len(rap["erreurs"])), (2, 1))
        self.assertEqual(Pointage.objects.get(personne=t).duration(), "8:30")
        r = self.client.post(reverse("importer"), {"type": "pointages", "action": "importer",
                                                   "fichier": self._fichier("p.xlsx", buf.getvalue())})
        self.assertEqual(r.context["rapport"]["ignores"], 2)

    def test_modeles(self):
        self.client.force_login(self.admin)
        for t in ("employes", "pointages"):
            r = self.client.get(reverse("importer_modele", args=[t]))
            self.assertEqual(r.content[:2], b"PK")


class SoldeFifoTests(Base):
    def test_reliquat_utilise_en_premier(self):
        from .conges import soldes
        self.p.date_entree = date(2024, 1, 1)
        self.p.save()
        # Les 10 jours de 2025 puis les 12 de 2026 sont pris d'abord sur 2024 (18 j), puis sur 2025.
        Conge.objects.create(personne=self.p, debut=date(2025, 3, 2), fin=date(2025, 3, 13))  # 10 jours ouvrés
        Conge.objects.create(personne=self.p, debut=date(2026, 3, 2), fin=date(2026, 3, 14))  # 12 jours ouvrés
        s = soldes(self.p, aujourd_hui=date(2026, 11, 20))
        par_annee = {l["annee"]: l for l in s["annees"]}
        # 2024 : 18 acquis jamais pris, encore valable jusqu'à fin 2026 -> consommé en premier
        self.assertEqual(par_annee[2024]["pris"], 18)
        self.assertEqual(par_annee[2025]["pris"], 4)
        self.assertEqual(s["disponible"], 14 + 18)
        # En 2027, le reliquat 2024 a disparu et 2025 reste valable
        s = soldes(self.p, aujourd_hui=date(2027, 1, 10))
        self.assertTrue({l["annee"]: l for l in s["annees"]}[2024]["expire"])

    def test_prorata_entree_en_cours_annee(self):
        from .conges import acquis_annee
        self.p.date_entree = date(2026, 7, 1)
        self.assertEqual(acquis_annee(self.p, 2026), 9)
