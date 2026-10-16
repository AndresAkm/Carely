from django.templatetags.static import static

from apps.catalog.models import Category, Product
from apps.core.models import MAX_FEATURED_PRODUCTS, LandingBenefit

# Contenido que la landing mostraba antes de ser editable. Si un bloque no
# tiene fila en `LandingBenefit`, se usa este valor.
DEFAULT_BENEFITS = [
    {
        'position': 1,
        'icon': 'bi-shield-check',
        'title': 'Productos 100% Originales',
        'description': 'Trabajamos directamente con marcas reconocidas para garantizar la autenticidad de cada producto.',
    },
    {
        'position': 2,
        'icon': 'bi-truck',
        'title': 'Envío Rápido y Seguro',
        'description': 'Recibe tus productos en la puerta de tu casa con entregas rápidas y empaque cuidadoso.',
    },
    {
        'position': 3,
        'icon': 'bi-star',
        'title': 'Asesoría Personalizada',
        'description': 'Nuestro equipo de expertos te ayuda a encontrar los productos ideales para tu tipo de piel.',
    },
    {
        'position': 4,
        'icon': 'bi-arrow-repeat',
        'title': 'Devoluciones Sin Complicaciones',
        'description': 'Si no estás satisfecha, puedes devolver tu producto en un plazo de 30 días.',
    },
]


def get_benefits():
    """Bloques de beneficios: la fila guardada gana al texto por defecto."""
    stored = {benefit.position: benefit for benefit in LandingBenefit.objects.all()}
    blocks = []
    for default in DEFAULT_BENEFITS:
        saved = stored.get(default['position'])
        blocks.append({
            'position': default['position'],
            'icon': default['icon'],
            'title': saved.title if saved else default['title'],
            'description': saved.description if saved else default['description'],
        })
    return blocks


def benefits_initial():
    """Valores iniciales del formulario de beneficios en el panel."""
    initial = {}
    for block in get_benefits():
        initial[f"title_{block['position']}"] = block['title']
        initial[f"description_{block['position']}"] = block['description']
    return initial


def get_hero_image_url(config):
    if config.hero_image:
        return config.hero_image.url
    return static('core/images/hero-placeholder.png')


def get_featured_products(config):
    """Productos elegidos en el panel; si no queda ninguno activo, los destacados
    automáticos de siempre (`Product.featured`), para que la landing no quede vacía."""
    selected = list(
        config.featured_products.filter(is_active=True)
        .select_related('category')[:MAX_FEATURED_PRODUCTS]
    )
    if selected:
        return selected
    return list(
        Product.objects.filter(is_active=True, featured=True)
        .select_related('category')[:MAX_FEATURED_PRODUCTS]
    )


def get_featured_categories(config):
    """Categorías elegidas en el panel; sin selección activa, todas las activas."""
    selected = list(config.featured_categories.filter(is_active=True))
    if selected:
        return selected
    return list(Category.objects.filter(is_active=True))
