# ⏱ Pointage Max

Application de **pointage et de gestion des employés** : présences, retards, congés, bilan mensuel
avec calcul des salaires, badges QR code, rôles Administrateur / Pointeur et journal d'audit.

Elle fonctionne sur PC, tablette et téléphone, et peut aussi piloter une **borne Raspberry Pi**
avec lecteur de carte d'identité électronique (eID), écran LCD et LED.

## Fonctionnalités

| Écran | Rôle | Contenu |
|---|---|---|
| **Vision RH** | Admin | Présents, absents, retards, sorties oubliées, congés en cours et à venir ; heures et masse salariale du mois avec comparaison au mois précédent ; ponctualité ; heures par jour, par ville et par service ; employés qui font le plus et le moins d'heures |
| **Pointer** | Admin, pointeur | Scan du badge QR (caméra ou lecteur USB) ou du matricule : arrivée/sortie automatique ; saisie manuelle ; choix de la ville et du chantier |
| **Pointages** | Admin, pointeur | Liste filtrable. Le pointeur ne voit que ses saisies et ne peut modifier que celles du jour ; l'admin peut tout modifier ou supprimer |
| **Employés** | Admin, pointeur | Fiche complète (photo, CIN, CNSS, famille, poste, contrat, paie, RIB, pièce d'identité scannée). Le pointeur peut créer une fiche et la corriger pendant 24 h |
| **Badge** | Admin, pointeur | Badge format carte bancaire à imprimer, ou QR code PNG à envoyer sur le téléphone de l'employé |
| **Bilan mensuel** | Admin | Jours, heures, congés, absences, salaire théorique et réel par employé ; filtres ville/service ; export Excel, CSV et impression |
| **Congés** | Admin | Congé annuel, maladie, maternité… Les jours de repos et les jours fériés ne sont pas décomptés ; solde annuel |
| **Importer** | Admin | Import des employés et de l'historique des pointages depuis Excel ou CSV, avec modèles et vérification avant import |
| **Journal** | Admin | Qui a créé, modifié ou supprimé quoi, et quand |
| **Paramètres** | Admin | Villes, services/chantiers (avec heure de début), types de contrat, jours fériés, utilisateurs |

### Calcul du salaire réel

- **Mensuel** : salaire × heures travaillées (+ congés payés) ÷ 191 h, plafonné au salaire.
  Exemple : 8 623 DH, 43 h 31 travaillées → 1 965 DH.
- **Journalier** : taux × jours travaillés (+ congés payés).
- **Horaire** : taux × heures (+ congés payés).

## Tester sur votre ordinateur (Windows, Mac, Linux)

1. Installez **Python 3** depuis https://www.python.org/downloads/ (sous Windows, cochez **« Add python.exe to PATH »**).
2. Décompressez le dossier, puis double-cliquez sur :
   - **Windows** : `demarrer-windows.bat`
   - **Mac** : `demarrer-mac.command` (la première fois : clic droit → Ouvrir)
   - **Linux** : `demarrer.sh`
3. Le navigateur s'ouvre sur http://127.0.0.1:8000/. Connectez-vous avec **admin / admin123**,
   puis changez ce mot de passe (clic sur votre nom en haut à droite).
4. Menu **Importer** : téléchargez le modèle Excel, remplissez-le avec vos employés, puis vos pointages, et importez-les.
   Le bouton « Vérifier sans enregistrer » signale les lignes en erreur avant l'import.

Les données restent sur votre ordinateur (fichier `db.sqlite3` et dossier `media/`).

## Installation (Raspberry Pi OS, Debian, Ubuntu)

```bash
git clone https://github.com/Lapin-Blanc/pointeuse.git
cd pointeuse
bash install.sh          # application web seule
bash install.sh --eid    # + borne avec lecteur eID, LCD et LED
```

Le script installe tout dans un environnement virtuel, crée la base de données, ajoute les jours
fériés marocains à date fixe, demande le compte administrateur et démarre les services
(`pointage-web`, et `pointage-borne` avec `--eid`). L'application est ensuite sur
`http://<adresse-du-pi>:8000/`.

### Premiers pas

1. Connectez-vous avec le compte administrateur.
2. **Paramètres** : créez les villes, les services/chantiers (avec leur heure de début) et les types de contrat.
3. **Paramètres → Jours fériés** : ajoutez les fêtes religieuses de l'année (Aïd al-Fitr, Aïd al-Adha, 1er Moharram, Aïd al-Mawlid).
4. **Paramètres → Utilisateurs** : créez les comptes des pointeurs et mettez-les dans le groupe **Pointeur**
   (ou **Administrateur** pour un deuxième administrateur).
5. **Employés** : créez les fiches, puis imprimez les badges.

### Caméra sur téléphone

Les navigateurs n'autorisent la caméra qu'en **HTTPS**. Sur le réseau local en HTTP, utilisez un
lecteur de QR code USB (il tape le code dans le champ) ou mettez le site derrière un serveur HTTPS
(Caddy, Nginx…) et ajoutez `Environment=POINTAGE_HTTPS=1` au service `pointage-web`.

## Réglages

Dans `/etc/systemd/system/pointage-web.service` (puis `sudo systemctl restart pointage-web`) :

| Variable | Par défaut | Rôle |
|---|---|---|
| `POINTAGE_HOSTS` | adresses du Pi | Noms/adresses autorisés |
| `POINTAGE_TZ` | `Africa/Casablanca` | Fuseau horaire |
| `POINTAGE_DEVISE` | `DH` | Devise affichée |
| `POINTAGE_HEURES_MENSUELLES` | `191` | Base horaire du mois (44 h/semaine) |
| `POINTAGE_HEURES_PAR_JOUR` | `8` | Heures comptées pour un jour de congé payé |
| `POINTAGE_JOURS_REPOS` | `6` | Jours non travaillés (0 = lundi … 6 = dimanche), ex. `5,6` |
| `POINTAGE_CONGE_ANNUEL` | `18` | Jours de congé annuel (acquis au prorata des mois travaillés) |
| `POINTAGE_CONGE_REPORT` | `2` | Années pendant lesquelles un reliquat de congé reste utilisable (décompte FIFO) |
| `POINTAGE_HEURE_DEBUT` | `08:00` | Heure de début si le service n'en a pas |
| `POINTAGE_TOLERANCE_RETARD` | `10` | Minutes de tolérance avant un retard |
| `POINTAGE_HTTPS` | `0` | `1` si le site est servi en HTTPS |
| `POINTAGE_DEBUG` | `0` | `1` uniquement pour le développement |

Pour la Belgique par exemple : `POINTAGE_TZ=Europe/Brussels`, `POINTAGE_DEVISE=€`,
`POINTAGE_HEURES_MENSUELLES=164.67`, `POINTAGE_JOURS_REPOS=5,6`, `POINTAGE_CONGE_ANNUEL=20`.

## Sécurité et données personnelles

- La clé secrète est générée au premier lancement dans `secret_key.txt` (hors Git).
- Les photos et pièces d'identité ne sont accessibles qu'aux utilisateurs connectés.
- En-têtes de sécurité (CSP, anti-clickjacking), protection CSRF, sessions de 12 h.
- La base contient des données personnelles (CIN, adresse, RIB) : sauvegardez `db.sqlite3` et
  le dossier `media/` dans un endroit protégé, et respectez la loi sur la protection des données
  (loi 09-08 au Maroc, RGPD en Europe).

## Développement

```bash
python3 -m venv venv && venv/bin/pip install -r requirements.txt
POINTAGE_DEBUG=1 venv/bin/python manage.py migrate
POINTAGE_DEBUG=1 venv/bin/python manage.py donnees_demo     # admin/admin123, pointeur/pointeur123
POINTAGE_DEBUG=1 venv/bin/python manage.py runserver
venv/bin/python manage.py test pointages
```

Le lecteur QR [html5-qrcode](https://github.com/mebjas/html5-qrcode) (licence Apache 2.0) est inclus
dans `pointages/static/pointages/vendor/` pour fonctionner sans Internet.
