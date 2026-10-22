import logging

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.files.storage import default_storage
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.shortcuts import redirect, render
from django.views import View

from apps.catalog.models import Category, Product
from apps.core.forms import LandingBenefitsForm, SiteCustomizationForm
from apps.core.landing import DEFAULT_BENEFITS, benefits_initial, get_hero_image_url
from apps.core.models import MAX_FEATURED_PRODUCTS, SiteCustomization
from apps.core.permissions import is_admin

logger = logging.getLogger(__name__)

PRODUCTS_PER_PAGE = 12
# Botones de paginación y de filtro: su presencia en el POST indica que el
# usuario solo está navegando, así que no se guarda nada.
BROWSE_FIELD = 'browse_page'
IMAGE_FIELDS = ('hero_image', 'logo', 'logo_icon')


def valid_ids(values):
    """IDs enteros que llegan del formulario; lo que no sea un entero se descarta."""
    ids = set()
    for value in values or []:
        text = str(value).strip()
        if text.isdigit():
            ids.add(int(text))
    return ids


def page_window(page):
    """Números de página a mostrar: primera, última y vecinas de la actual.

    `None` marca un hueco; así el paginador no crece con el catálogo.
    """
    total = page.paginator.num_pages
    current = page.number
    wanted = {1, total} | set(range(max(1, current - 2), min(total, current + 2) + 1))
    items, previous = [], 0
    for number in sorted(wanted):
        if number - previous > 1:
            items.append(None)
        items.append(number)
        previous = number
    return items


def build_product_picker(selected, query, category_id, only_selected, page_number):
    products = Product.objects.select_related('category').order_by('name')
    if query:
        products = products.filter(Q(name__icontains=query) | Q(brand__icontains=query))
    if category_id:
        products = products.filter(category_id=category_id)
    if only_selected:
        products = products.filter(pk__in=selected)

    page = Paginator(products, PRODUCTS_PER_PAGE).get_page(page_number)
    visible = {product.pk for product in page.object_list}
    # Lo seleccionado que no se ve en esta página viaja como campo oculto: así
    # cambiar de página o filtrar no lo quita al guardar.
    hidden = Product.objects.filter(pk__in=selected - visible).values_list('pk', flat=True)
    return {
        'page': page,
        'page_links': page_window(page),
        'hidden_ids': list(hidden),
        'selected_ids': {str(pk) for pk in selected},
        'selected_count': Product.objects.filter(pk__in=selected).count(),
        'max_count': MAX_FEATURED_PRODUCTS,
        'categories': Category.objects.order_by('order', 'name'),
        'filters': {
            'query': query,
            'category_id': category_id,
            'only_selected': only_selected,
        },
    }


class DashboardCustomizationMixin(LoginRequiredMixin, UserPassesTestMixin):
    def test_func(self):
        return is_admin(self.request.user)

    def handle_no_permission(self):
        return redirect('core:home')


class SiteCustomizationView(DashboardCustomizationMixin, View):
    template_name = 'core/dashboard/site_customization.html'

    def get(self, request, *args, **kwargs):
        config = SiteCustomization.load()
        form = SiteCustomizationForm(instance=config)
        benefits_form = LandingBenefitsForm(initial=benefits_initial())
        return self._render(request, form, benefits_form, self._image_urls(config))

    def post(self, request, *args, **kwargs):
        config = SiteCustomization.load()
        # Antes de validar: el formulario reasigna las imágenes al construir la
        # instancia, y hay que saber cuáles eran los archivos anteriores.
        old_images = {
            field: getattr(config, field).name if getattr(config, field) else ''
            for field in IMAGE_FIELDS
        }
        image_urls = self._image_urls(config)

        form = SiteCustomizationForm(request.POST, request.FILES, instance=config)
        benefits_form = LandingBenefitsForm(request.POST)

        if BROWSE_FIELD in request.POST:
            # Paginar o filtrar solo rearma la pantalla con lo que el usuario
            # ya escribió o marcó: no valida ni guarda.
            return self._render(request, form, benefits_form, image_urls)

        if form.is_valid() and benefits_form.is_valid():
            with transaction.atomic():
                form.save()
                benefits_form.save()
            self._remove_replaced_images(form, old_images)
            messages.success(request, 'Los cambios se guardaron. Ya se ven en la landing.')
            return redirect('dashboard:site_customization')

        messages.error(request, 'Revisa los campos marcados antes de guardar.')
        return self._render(request, form, benefits_form, image_urls)

    def _image_urls(self, config):
        return {
            'hero_image_url': get_hero_image_url(config),
            'logo_url': config.get_logo_url(),
            'logo_icon_url': config.get_logo_icon_url(),
        }

    def _remove_replaced_images(self, form, old_images):
        for field, old_name in old_images.items():
            if field not in form.changed_data or not old_name:
                continue
            current = getattr(form.instance, field)
            new_name = current.name if current else ''
            if new_name == old_name:
                continue
            try:
                default_storage.delete(old_name)
            except Exception:
                # Un archivo huérfano no justifica revertir un guardado correcto.
                logger.warning('No se pudo borrar la imagen anterior: %s', old_name)

    def _picker_state(self, request):
        source = request.POST if request.method == 'POST' else {}
        query = str(source.get('product_q', '')).strip()[:100]
        raw_category = str(source.get('product_category', '')).strip()
        category_id = int(raw_category) if raw_category.isdigit() else None
        only_selected = bool(source.get('product_selected'))
        page_number = source.get(BROWSE_FIELD, 1)
        return query, category_id, only_selected, page_number

    def _render(self, request, form, benefits_form, image_urls):
        # Con el formulario sin enlazar, el valor inicial son los ids guardados.
        # Con el POST, es lo que el usuario acaba de marcar en todas las páginas.
        selected = valid_ids(form['featured_products'].value())
        query, category_id, only_selected, page_number = self._picker_state(request)
        icons = {block['position']: block['icon'] for block in DEFAULT_BENEFITS}

        context = {
            'form': form,
            'benefits_form': benefits_form,
            **image_urls,
            'picker': build_product_picker(selected, query, category_id, only_selected, page_number),
            'selected_category_ids': {str(value) for value in form['featured_categories'].value() or []},
            'benefit_blocks': [
                {
                    'position': position,
                    'icon': icons[position],
                    'title': benefits_form[f'title_{position}'],
                    'description': benefits_form[f'description_{position}'],
                }
                for position in icons
            ],
        }
        return render(request, self.template_name, context)
