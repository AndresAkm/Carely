/* Actualizar pedido: avanzar de estado y revertir los cambios sin guardar. */
(function () {
    'use strict';

    // Configuración de avance de estado
    var statusOrder = ['pendiente', 'confirmado', 'enviado', 'entregado'];
    var statusInput = document.getElementById('id_status');
    var advanceBtn = document.getElementById('advanceStatusBtn');
    var timeline = document.getElementById('orderTimeline');

    // Estado con el que se cargó la página, para poder revertir sin guardar.
    var initialStatus = statusInput ? statusInput.value : '';
    var initialTimeline = timeline ? timeline.innerHTML : '';

    function revertChanges() {
        if (statusInput) statusInput.value = initialStatus;
        if (timeline) timeline.innerHTML = initialTimeline;
        if (advanceBtn && advanceBtn.parentElement) {
            advanceBtn.parentElement.style.display = '';
        }
    }

    if (advanceBtn && timeline && statusInput) {
        advanceBtn.addEventListener('click', function () {
            var currentStatus = statusInput.value;
            var currentIndex = statusOrder.indexOf(currentStatus);

            if (currentIndex >= 0 && currentIndex < statusOrder.length - 1) {
                var newStatus = statusOrder[currentIndex + 1];
                statusInput.value = newStatus; // Actualiza el input hidden

                // Actualiza visualmente el timeline
                var steps = timeline.querySelectorAll('.osf-step');
                var lines = timeline.querySelectorAll('.osf-line');

                // Encuentra el paso actual y el siguiente
                steps.forEach(function (step, index) {
                    if (step.dataset.status === newStatus) {
                        var circle = step.querySelector('.osf-circle');
                        circle.classList.remove('osf-circle--pending');
                        circle.classList.add('osf-circle--done');

                        var icon = circle.querySelector('i');
                        if (icon) icon.style.display = 'inline-block';

                        // Pinta la línea anterior
                        if (index > 0 && lines[index - 1]) {
                            lines[index - 1].classList.add('osf-line--done');
                        }
                    }
                });

                // Si llegamos a entregado, ocultar botón y estado cancelado visualmente
                if (newStatus === 'entregado') {
                    advanceBtn.parentElement.style.display = 'none';
                    var cancelStep = Array.prototype.find.call(steps, function (s) {
                        return s.dataset.status === 'cancelado';
                    });
                    if (cancelStep) {
                        cancelStep.style.display = 'none';
                        if (lines[lines.length - 1]) lines[lines.length - 1].style.display = 'none';
                    }
                }
            }
        });
    }

    // Descartar cambios (estado y notas) al pulsar "Revertir"
    var notesTA = document.getElementById('id_order_notes');
    var cancelBtn = document.getElementById('cancelNotesBtn');
    if (cancelBtn) {
        cancelBtn.addEventListener('click', function () {
            if (notesTA) {
                notesTA.value = notesTA.defaultValue;
                notesTA.blur();
            }
            revertChanges();
        });
    }
})();
