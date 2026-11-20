(function () {
  "use strict";
  var form = document.getElementById("form-scan");
  var champ = document.getElementById("code");
  var resultat = document.getElementById("resultat");
  var boutonCamera = document.getElementById("camera");
  var info = document.getElementById("camera-info");
  var dernier = { code: null, quand: 0 };
  var enCours = false;
  var scanner = null;

  function afficher(classe, titre, lignes, photo) {
    resultat.className = "resultat " + classe;
    resultat.textContent = "";
    if (photo) {
      var img = document.createElement("img");
      img.src = photo;
      img.alt = "";
      resultat.appendChild(img);
    }
    var t = document.createElement("div");
    t.className = "grand";
    t.textContent = titre;
    resultat.appendChild(t);
    lignes.forEach(function (l) {
      var d = document.createElement("div");
      d.textContent = l;
      resultat.appendChild(d);
    });
  }

  function bip(ok) {
    try {
      var ctx = new (window.AudioContext || window.webkitAudioContext)();
      var o = ctx.createOscillator();
      o.frequency.value = ok ? 880 : 220;
      o.connect(ctx.destination);
      o.start();
      o.stop(ctx.currentTime + (ok ? 0.12 : 0.35));
    } catch (e) { /* pas de son */ }
  }

  function envoyer(code) {
    code = (code || "").trim();
    if (!code || enCours) return;
    // Évite de pointer deux fois le même badge resté devant la caméra.
    if (code === dernier.code && Date.now() - dernier.quand < 5000) return;
    dernier = { code: code, quand: Date.now() };
    enCours = true;
    var donnees = new FormData(form);
    donnees.set("code", code);
    fetch(form.action, { method: "POST", body: donnees, credentials: "same-origin" })
      .then(function (r) { return r.json(); })
      .then(function (r) {
        if (r.ok) {
          var txt = r.resultat === "ARRIVEE" ? "ARRIVÉE" : "SORTIE";
          afficher(r.resultat, r.nom, [txt + " à " + r.heure, r.matricule], r.photo);
          bip(true);
          setTimeout(function () { window.location.reload(); }, 2500);
        } else {
          afficher(r.resultat || "erreur", r.nom || "Refusé", [r.message], r.photo);
          bip(false);
        }
      })
      .catch(function () {
        afficher("erreur", "Erreur réseau", ["Le pointage n'a pas été enregistré. Réessayez."]);
        bip(false);
      })
      .finally(function () {
        enCours = false;
        champ.value = "";
        champ.focus();
      });
  }

  form.addEventListener("submit", function (e) {
    e.preventDefault();
    envoyer(champ.value);
  });

  boutonCamera.addEventListener("click", function () {
    if (scanner) {
      scanner.stop().then(function () { scanner.clear(); scanner = null; });
      boutonCamera.textContent = "Utiliser la caméra";
      return;
    }
    if (!window.isSecureContext) {
      info.textContent = "La caméra ne fonctionne qu'en HTTPS (ou sur localhost). Utilisez le champ ci-dessus ou un lecteur USB.";
      return;
    }
    if (typeof Html5Qrcode === "undefined") {
      info.textContent = "Le lecteur de QR code n'a pas pu être chargé.";
      return;
    }
    scanner = new Html5Qrcode("lecteur");
    scanner.start({ facingMode: "environment" }, { fps: 10, qrbox: 220 }, envoyer, function () {})
      .then(function () { boutonCamera.textContent = "Arrêter la caméra"; info.textContent = ""; })
      .catch(function (err) {
        info.textContent = "Caméra indisponible : " + err;
        scanner = null;
      });
  });
})();
