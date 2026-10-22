import re

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
from django.db import models
from django.templatetags.static import static

from apps.catalog.models import Category, Product

SINGLETON_PK = 1
MAX_FEATURED_PRODUCTS = 6
BENEFIT_POSITIONS = (1, 2, 3, 4)


def validate_plain_text(value):
    """Solo texto plano: los campos se muestran escapados, pero rechazar
    etiquetas deja claro que el contenido no es HTML."""
    if value and re.search(r'[<>]', value):
        raise ValidationError('No se permiten los caracteres < ni > en este campo.')


class SiteCustomization(models.Model):
    """Contenido editable de la landing y del pie de página.

    Es un singleton: siempre vive en la fila `pk=SINGLETON_PK`. Los valores por
    defecto son el texto que la landing ya mostraba, así que una base recién
    migrada se ve igual que antes.
    """

    hero_title = models.CharField(
        'título de la portada',
        max_length=80,
        default='Cultiva tu',
        validators=[validate_plain_text],
        help_text='Texto que precede a la palabra destacada, que cambia con las pestañas de color.',
    )
    hero_subtitle = models.CharField(
        'subtítulo de la portada',
        max_length=240,
        default='Productos cuidadosamente seleccionados para nutrir tu piel, tu mente y tu ritual diario de bienestar.',
        validators=[validate_plain_text],
    )
    hero_button_text = models.CharField(
        'texto del botón principal',
        max_length=40,
        default='Ver Catalogo',
        validators=[validate_plain_text],
    )
    hero_image = models.ImageField(
        'imagen principal',
        upload_to='landing/',
        blank=True,
        validators=[FileExtensionValidator(allowed_extensions=['jpg', 'jpeg', 'png', 'webp'])],
        help_text='JPG, PNG o WebP de máximo 5 MB. Si la dejas vacía se usa la imagen por defecto.',
    )
    logo = models.ImageField(
        'logo principal',
        upload_to='branding/',
        blank=True,
        validators=[FileExtensionValidator(allowed_extensions=['jpg', 'jpeg', 'png', 'webp'])],
        help_text='Logo con el nombre de la marca. Se usa en la barra de navegación y en las pantallas de acceso.',
    )
    logo_icon = models.ImageField(
        'isotipo',
        upload_to='branding/',
        blank=True,
        validators=[FileExtensionValidator(allowed_extensions=['jpg', 'jpeg', 'png', 'webp'])],
        help_text='Símbolo o isotipo de la marca. Se usa en el pie de página y en el panel.',
    )
    featured_products = models.ManyToManyField(
        Product,
        blank=True,
        related_name='landing_sections',
        verbose_name='productos destacados',
    )
    featured_categories = models.ManyToManyField(
        Category,
        blank=True,
        related_name='landing_sections',
        verbose_name='categorías destacadas',
    )
    footer_email = models.EmailField('correo de contacto', blank=True)
    footer_phone = models.CharField('teléfono', max_length=30, blank=True, validators=[validate_plain_text])
    footer_address = models.CharField('dirección', max_length=120, blank=True, validators=[validate_plain_text])
    footer_facebook = models.URLField('enlace de Facebook', blank=True)
    footer_instagram = models.URLField('enlace de Instagram', blank=True)
    footer_whatsapp = models.URLField('enlace de WhatsApp', blank=True)
    updated_at = models.DateTimeField('actualizado', auto_now=True)

    class Meta:
        verbose_name = 'personalización de la landing'
        verbose_name_plural = 'personalización de la landing'

    def __str__(self):
        return 'Personalización de la landing'

    def save(self, *args, **kwargs):
        self.pk = SINGLETON_PK
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=SINGLETON_PK)
        return obj

    def get_logo_url(self):
        if self.logo:
            return self.logo.url
        return static('core/images/carely-logo-text.webp')

    def get_logo_icon_url(self):
        if self.logo_icon:
            return self.logo_icon.url
        return static('core/images/carely-logo.webp')


class LandingBenefit(models.Model):
    """Título y descripción de cada bloque de beneficios de la landing.

    El icono de cada bloque no es editable: vive en `apps/core/landing.py`
    junto con los textos por defecto.
    """

    position = models.PositiveSmallIntegerField(
        'posición',
        unique=True,
        choices=[(position, f'Bloque {position}') for position in BENEFIT_POSITIONS],
    )
    title = models.CharField('título', max_length=80, validators=[validate_plain_text])
    description = models.CharField('descripción', max_length=200, validators=[validate_plain_text])

    class Meta:
        verbose_name = 'beneficio de la landing'
        verbose_name_plural = 'beneficios de la landing'
        ordering = ['position']

    def __str__(self):
        return f'{self.position}. {self.title}'


class ContactRequest(models.Model):
    """Mensaje recibido desde el modal de contacto del pie de página.

    Se guarda siempre, aunque el aviso por correo falle, para que el equipo
    pueda atenderlo desde el panel.
    """

    class Status(models.TextChoices):
        PENDIENTE = 'pendiente', 'Pendiente'
        RESPONDIDA = 'respondida', 'Respondida'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='contact_requests',
        verbose_name='usuario',
    )
    name = models.CharField('nombre', max_length=120)
    email = models.EmailField('correo')
    subject = models.CharField('asunto', max_length=150, blank=True)
    message = models.TextField('mensaje')
    status = models.CharField(
        'estado',
        max_length=20,
        choices=Status.choices,
        default=Status.PENDIENTE,
    )
    reply = models.TextField('respuesta', blank=True)
    replied_at = models.DateTimeField('respondida en', null=True, blank=True)
    replied_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='contact_replies',
        verbose_name='respondida por',
    )
    created_at = models.DateTimeField('creada', auto_now_add=True)
    updated_at = models.DateTimeField('actualizada', auto_now=True)

    class Meta:
        verbose_name = 'solicitud de contacto'
        verbose_name_plural = 'solicitudes de contacto'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.name} · {self.subject or self.email}'
