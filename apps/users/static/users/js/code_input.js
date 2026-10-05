(function () {
    // Casillas para el código de un solo uso. El input real conserva el valor:
    // estas casillas solo lo pintan, así que pegar el código entero funciona
    // sin código extra (el pegado dispara el mismo evento 'input').
    function initCodeInput(root) {
        var input = root.querySelector('input');
        var boxes = Array.prototype.slice.call(root.querySelectorAll('[data-code-box]'));
        if (!input || !boxes.length) return;

        function onlyDigits(value) {
            return (value || '').replace(/\D/g, '');
        }

        function paint(value) {
            var digits = onlyDigits(value);
            boxes.forEach(function (box, index) {
                var digit = digits[index] || '';
                box.textContent = digit;
                box.classList.toggle('is-filled', Boolean(digit));
            });
        }

        function caretIndex() {
            return Math.min(input.selectionStart || 0, boxes.length - 1);
        }

        function markFocused(index) {
            boxes.forEach(function (box, position) {
                box.classList.toggle('is-focused', position === index);
            });
        }

        function focusBox(index) {
            var target = Math.max(0, Math.min(index, boxes.length - 1));
            input.focus();
            input.setSelectionRange(target, target);
            markFocused(target);
        }

        input.addEventListener('input', function () {
            var digits = onlyDigits(input.value);
            if (digits !== input.value) input.value = digits;
            paint(digits);
            focusBox(Math.min(digits.length, boxes.length - 1));
        });

        input.addEventListener('keydown', function (event) {
            var index = caretIndex();
            if (event.key === 'ArrowLeft') {
                event.preventDefault();
                focusBox(index - 1);
            } else if (event.key === 'ArrowRight') {
                event.preventDefault();
                focusBox(index + 1);
            } else if (event.key === 'Backspace' && !input.value) {
                // Ya no queda nada que borrar: camina hacia atrás.
                event.preventDefault();
                focusBox(index - 1);
            }
        });

        input.addEventListener('focus', function () {
            markFocused(caretIndex());
        });

        input.addEventListener('blur', function () {
            boxes.forEach(function (box) { box.classList.remove('is-focused'); });
        });

        root.addEventListener('mousedown', function (event) {
            var box = event.target.closest('[data-code-box]');
            if (!box) return;
            event.preventDefault();
            focusBox(boxes.indexOf(box));
        });

        paint(input.value);
        input.focus();
        markFocused(caretIndex());
    }

    document.addEventListener('DOMContentLoaded', function () {
        document.querySelectorAll('[data-code-input]').forEach(initCodeInput);
    });
})();