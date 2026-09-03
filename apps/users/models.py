from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models, transaction


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
