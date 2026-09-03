(function () {
    function initChainedAddressSelects(root) {
        var departmentSelect = root.querySelector('select[name="department"]');
        var citySelect = root.querySelector('select[name="city"]');
        if (!departmentSelect || !citySelect) return;

        var endpointTemplate = root.dataset.citiesUrl || '';

        function populateCities(departmentId, selectedCityId) {
            if (!departmentId) {
                citySelect.innerHTML = '<option value="">---------</option>';
                return;
            }
            var endpoint = endpointTemplate.replace('0', String(departmentId));
            fetch(endpoint)
                .then(function (response) {
                    if (!response.ok) throw new Error('Error al cargar municipios');
                    return response.json();
                })
                .then(function (data) {
                    citySelect.innerHTML = '<option value="">---------</option>';
                    (data.cities || []).forEach(function (city) {
                        var option = document.createElement('option');
                        option.value = city.id;
                        option.textContent = city.name;
                        if (selectedCityId && String(city.id) === String(selectedCityId)) {
                            option.selected = true;
                        }
                        citySelect.appendChild(option);
                    });
                })
                .catch(function () {
                    citySelect.innerHTML = '<option value="">---------</option>';
                });
        }

        var selectedCity = citySelect.value;

        departmentSelect.addEventListener('change', function () {
            populateCities(this.value, null);
        });

        if (departmentSelect.value) {
            populateCities(departmentSelect.value, selectedCity);
        }
    }

    document.addEventListener('DOMContentLoaded', function () {
        document.querySelectorAll('[data-chained-address]').forEach(initChainedAddressSelects);
    });
})();