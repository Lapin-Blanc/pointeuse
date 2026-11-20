document.querySelectorAll("#imprimer, [data-imprimer]").forEach(function (b) {
  b.addEventListener("click", function () { window.print(); });
});
