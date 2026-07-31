from django.contrib.auth.models import AbstractUser
from django.db import models


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
