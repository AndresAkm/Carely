from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models, transaction
from django.utils import timezone


class User(AbstractUser):
    class Role(models.TextChoices):
        CLIENT = 'client', 'Cliente'
        ADMIN = 'admin', 'Administrador'

    email = models.EmailField(
        unique=True,
        verbose_name='correo electrónico',
        error_messages={
            'unique': 'Ya existe un usuario con este correo electrónico.',
        },
    )
    phone = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        verbose_name='teléfono',
        help_text='Número de contacto opcional.',
    )
    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.CLIENT,
        verbose_name='rol',
    )
    accepted_terms_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='términos aceptados en',
        help_text='Fecha en que el usuario aceptó los términos y condiciones vigentes.',
    )
    terms_version = models.CharField(
        max_length=20,
        blank=True,
        verbose_name='versión de los términos aceptados',
        help_text='Identificador de la versión de los términos aceptados, p. ej. 2026-01-01.',
    )
    deactivated_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='deshabilitada en',
        help_text='Fecha en que la cuenta fue deshabilitada. Se vacía al reactivarla.',
    )
    deactivated_by = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='deactivated_accounts',
        verbose_name='deshabilitada por',
        help_text='Administrador que deshabilitó la cuenta. Vacío si la deshabilitó el titular.',
    )
    two_factor_enabled = models.BooleanField(
        default=False,
        verbose_name='verificación en dos pasos activada',
        help_text='El titular confirmó que tiene acceso al correo registrado.',
    )
    two_factor_enabled_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='verificación en dos pasos activada en',
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='creado en',
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='actualizado en',
    )

    class Meta:
        verbose_name = 'usuario'
        verbose_name_plural = 'usuarios'
        ordering = ['-created_at']

    def __str__(self):
        return self.email

    @property
    def has_accepted_current_terms(self):
        return bool(
            self.accepted_terms_at and self.terms_version == settings.TERMS_VERSION,
        )

    @property
    def was_deactivated_by_admin(self):
        return bool(self.deactivated_by_id)


class Department(models.Model):
    api_id = models.IntegerField(
        'identificador externo',
        unique=True,
    )
    name = models.CharField(
        'nombre',
        max_length=100,
    )

    class Meta:
        verbose_name = 'departamento'
        verbose_name_plural = 'departamentos'
        ordering = ['name']

    def __str__(self):
        return self.name


class City(models.Model):
    api_id = models.IntegerField(
        'identificador externo',
        unique=True,
    )
    name = models.CharField(
        'nombre',
        max_length=100,
    )
    department = models.ForeignKey(
        Department,
        on_delete=models.CASCADE,
        related_name='cities',
        verbose_name='departamento',
    )

    class Meta:
        verbose_name = 'ciudad'
        verbose_name_plural = 'ciudades'
        ordering = ['name']
        indexes = [
            models.Index(fields=['department', 'name'], name='idx_city_department_name'),
        ]

    def __str__(self):
        return self.name


class Address(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='addresses',
        verbose_name='usuario',
    )
    recipient_name = models.CharField(
        'nombre del destinatario',
        max_length=150,
    )
    phone = models.CharField(
        'teléfono de contacto',
        max_length=20,
        blank=True,
    )
    address_line = models.CharField(
        'dirección principal',
        max_length=255,
    )
    address_line2 = models.CharField(
        'complemento de dirección',
        max_length=255,
        blank=True,
    )
    city = models.ForeignKey(
        City,
        on_delete=models.PROTECT,
        related_name='addresses',
        verbose_name='ciudad o municipio',
    )
    department = models.ForeignKey(
        Department,
        on_delete=models.PROTECT,
        related_name='addresses',
        verbose_name='departamento',
    )
    postal_code = models.CharField(
        'código postal',
        max_length=10,
        blank=True,
    )
    instructions = models.TextField(
        'indicaciones adicionales',
        blank=True,
    )
    is_default = models.BooleanField(
        'dirección predeterminada',
        default=False,
    )
    is_active = models.BooleanField(
        'activo',
        default=True,
    )
    created_at = models.DateTimeField(
        'creado en',
        auto_now_add=True,
    )
    updated_at = models.DateTimeField(
        'actualizado en',
        auto_now=True,
    )

    class Meta:
        verbose_name = 'dirección'
        verbose_name_plural = 'direcciones'
        ordering = ['-is_default', '-created_at']
        indexes = [
            models.Index(fields=['user', 'is_active'], name='idx_address_user_active'),
        ]

    def __str__(self):
        return f'{self.recipient_name} — {self.address_line}, {self.city.name}'

    def save(self, *args, **kwargs):
        if self.is_default and not self.is_active:
            self.is_default = False
        if self.is_default:
            with transaction.atomic():
                Address.objects.select_for_update().filter(
                    user=self.user,
                    is_default=True,
                ).exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)


class TwoFactorCode(models.Model):
    """Código de un solo uso que prueba que el titular controla su correo.

    Se usa para las acciones sensibles: activar la verificación en dos pasos,
    deshabilitar la cuenta y reactivarla. El código nunca se guarda en claro.
    """

    class Purpose(models.TextChoices):
        ENABLE = 'enable', 'Activar la verificación en dos pasos'
        DEACTIVATE = 'deactivate', 'Deshabilitar la cuenta'
        REACTIVATE = 'reactivate', 'Reactivar la cuenta'

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='two_factor_codes',
        verbose_name='usuario',
    )
    purpose = models.CharField(
        max_length=20,
        choices=Purpose.choices,
        verbose_name='uso',
    )
    code_hash = models.CharField(
        max_length=128,
        verbose_name='hash del código',
        help_text='Código cifrado con el hasher de contraseñas de Django.',
    )
    expires_at = models.DateTimeField(
        verbose_name='expira en',
    )
    used_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='usado en',
    )
    failed_attempts = models.PositiveSmallIntegerField(
        default=0,
        verbose_name='intentos fallidos',
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='creado en',
    )

    class Meta:
        verbose_name = 'código de verificación en dos pasos'
        verbose_name_plural = 'códigos de verificación en dos pasos'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'purpose'], name='idx_twofactor_user_purpose'),
        ]

    def __str__(self):
        return f'{self.get_purpose_display()} — {self.user}'

    @property
    def is_used(self):
        return self.used_at is not None

    @property
    def is_expired(self):
        return timezone.now() >= self.expires_at

    @property
    def is_locked(self):
        return self.failed_attempts >= settings.TWO_FACTOR_MAX_ATTEMPTS

    @property
    def is_usable(self):
        return not (self.is_used or self.is_expired or self.is_locked)

    def mark_as_used(self):
        self.used_at = timezone.now()
        self.save(update_fields=['used_at'])

    def register_failed_attempt(self):
        self.failed_attempts += 1
        self.save(update_fields=['failed_attempts'])
