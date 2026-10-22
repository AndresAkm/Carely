/* Panel: vista previa de la imagen y selector de productos (filtro y contador). */
(function () {
    'use strict';

    var input = document.querySelector('input[name="hero_image"]');
    var preview = document.querySelector('[data-image-preview]');
    var hint = document.querySelector('[data-image-hint]');
    if (!input || !preview) return;

    var currentSrc = preview.getAttribute('src');
    var allowed = ['image/jpeg', 'image/png', 'image/webp'];

    function setHint(text) {
        if (hint) hint.textContent = text;
    }

    input.addEventListener('change', function () {
        var file = input.files && input.files[0];
        if (!file) {
            preview.setAttribute('src', currentSrc);
            setHint('Imagen actual de la portada');
            return;
        }
        if (allowed.indexOf(file.type) === -1) {
            input.value = '';
            preview.setAttribute('src', currentSrc);
            setHint('Formato no permitido: usa JPG, PNG o WebP.');
            return;
        }
        preview.setAttribute('src', URL.createObjectURL(file));
        setHint('Vista previa de la nueva imagen. Se publica al guardar.');
    });
})();

(function () {
    'use strict';

    var allowed = ['image/jpeg', 'image/png', 'image/webp'];

    ['logo', 'logo_icon'].forEach(function (name) {
        var input = document.querySelector('input[name="' + name + '"]');
        var preview = document.querySelector('[data-logo-preview="' + name + '"]');
        if (!input || !preview) return;

        var currentSrc = preview.getAttribute('src');
        input.addEventListener('change', function () {
            var file = input.files && input.files[0];
            if (!file) {
                preview.setAttribute('src', currentSrc);
                return;
            }
            if (allowed.indexOf(file.type) === -1) {
                input.value = '';
                preview.setAttribute('src', currentSrc);
                return;
            }
            preview.setAttribute('src', URL.createObjectURL(file));
        });
    });
})();

(function () {
    'use strict';

    var form = document.querySelector('.site-customization');
    if (!form) return;

    var filterButton = form.querySelector('[data-product-filter]');
    var clearButton = form.querySelector('[data-product-clear]');
    var query = document.getElementById('productQuery');
    var category = document.getElementById('productCategory');
    var onlySelected = document.getElementById('productOnlySelected');
    var counter = form.querySelector('[data-selected-count]');

    // Enter en el buscador aplica el filtro; sin esto guardaría el formulario.
    if (query && filterButton) {
        query.addEventListener('keydown', function (event) {
            if (event.key === 'Enter') {
                event.preventDefault();
                filterButton.click();
            }
        });
    }

    if (clearButton && filterButton) {
        clearButton.addEventListener('click', function () {
            if (query) query.value = '';
            if (category) category.value = '';
            if (onlySelected) onlySelected.checked = false;
            filterButton.click();
        });
    }

    // Cuenta lo que se guardaría: los marcados en pantalla más los ocultos.
    function updateCounter() {
        if (!counter) return;
        var selected = form.querySelectorAll(
            'input[name="featured_products"]:checked, input[type="hidden"][name="featured_products"]'
        ).length;
        counter.textContent = selected + ' de ' + counter.getAttribute('data-max') + ' seleccionados';
    }

    form.addEventListener('change', function (event) {
        if (event.target && event.target.name === 'featured_products') updateCounter();
    });
    updateCounter();
})();
