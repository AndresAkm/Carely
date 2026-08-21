from django.db import models
from django.utils.text import slugify


class Category(models.Model):
    name = models.CharField('nombre', max_length=100)
    description = models.TextField('descripción', blank=True)
    icon = models.CharField('icono', max_length=50, help_text='Clase de Bootstrap Icons (ej: bi-emoji-wink)')
    slug = models.SlugField('slug', unique=True, blank=True)
    image = models.ImageField('imagen', upload_to='categories/', blank=True, null=True)
    order = models.PositiveIntegerField('orden', default=0)
    is_active = models.BooleanField('activo', default=True)
    created_at = models.DateTimeField('creado', auto_now_add=True)
    updated_at = models.DateTimeField('actualizado', auto_now=True)

    class Meta:
        verbose_name = 'categoría'
        verbose_name_plural = 'categorías'
        ordering = ['order', 'name']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class Product(models.Model):
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name='products', verbose_name='categoría')
    name = models.CharField('nombre', max_length=200)
    description = models.TextField('descripción', blank=True)
    price = models.DecimalField('precio', max_digits=10, decimal_places=2)
    image = models.ImageField('imagen', upload_to='products/', blank=True, null=True)
    slug = models.SlugField('slug', unique=True, blank=True)
    stock = models.PositiveIntegerField('stock', default=0)
    is_active = models.BooleanField('activo', default=True)
    featured = models.BooleanField('destacado', default=False)
    created_at = models.DateTimeField('creado', auto_now_add=True)
    updated_at = models.DateTimeField('actualizado', auto_now=True)

    class Meta:
        verbose_name = 'producto'
        verbose_name_plural = 'productos'
        ordering = ['-created_at']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)
