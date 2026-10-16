// Detalle rápido de filas del panel. En móvil las tablas ocultan sus columnas
// secundarias (`d-none d-md-table-cell`), así que este script vuelca las celdas
// `data-label` de la fila pulsada en el modal compartido para no perder datos.
// Las celdas marcadas con `data-detail-skip` se omiten.
(function () {
  "use strict";

  document.addEventListener("click", function (event) {
    const trigger = event.target.closest("[data-table-detail]");
    if (!trigger) return;

    const modalEl = document.getElementById("tableDetailModal");
    const row = trigger.closest("tr");
    if (!modalEl || !row) return;

    const body = modalEl.querySelector("[data-table-detail-body]");
    if (!body) return;

    const titleEl = modalEl.querySelector("#tableDetailModalLabel");
    if (titleEl) {
      titleEl.textContent = trigger.dataset.tableDetailTitle || "Detalle";
    }

    body.innerHTML = "";
    row.querySelectorAll("td[data-label]").forEach(function (cell) {
      if (cell.hasAttribute("data-detail-skip")) return;
      const dt = document.createElement("dt");
      dt.textContent = cell.getAttribute("data-label");
      const dd = document.createElement("dd");
      dd.innerHTML = cell.innerHTML.trim() || "—";
      body.appendChild(dt);
      body.appendChild(dd);
    });

    if (window.bootstrap && window.bootstrap.Modal) {
      window.bootstrap.Modal.getOrCreateInstance(modalEl).show();
    }
  });
})();
