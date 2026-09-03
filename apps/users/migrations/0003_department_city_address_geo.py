import django.db.models.deletion
from django.db import migrations, models


def migrate_existing_geo_data(apps, schema_editor):
    """Siembra Department/City a partir de las direcciones existentes.
    Las columnas de dirección aún son varchar en este punto, por lo que se
    guarda el id de la relación como string para que el posterior AlterField
    hacia ForeignKey (bigint) pueda convertir los valores numéricos."""
    Address = apps.get_model('users', 'Address')
    Department = apps.get_model('users', 'Department')
    City = apps.get_model('users', 'City')

    if not Address.objects.exists():
        return

    department_pk_by_name = {}
    city_pk_by_key = {}
    next_dept_api_id = -1
    next_city_api_id = -1

    for address in Address.objects.iterator():
        dept_name = (address.department or '').strip()
        city_name = (address.city or '').strip()
        if not dept_name:
            continue

        if dept_name not in department_pk_by_name:
            department = Department.objects.create(
                api_id=next_dept_api_id,
                name=dept_name,
            )
            department_pk_by_name[dept_name] = department.pk
            next_dept_api_id -= 1

        key = (dept_name, city_name)
        if key not in city_pk_by_key:
            city = City.objects.create(
                api_id=next_city_api_id,
                name=city_name,
                department_id=department_pk_by_name[dept_name],
            )
            city_pk_by_key[key] = city.pk
            next_city_api_id -= 1

        address.department = str(department_pk_by_name[dept_name])
        address.city = str(city_pk_by_key[key])
        address.save(update_fields=['department', 'city'])


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0002_add_address_model'),
    ]

    operations = [
        migrations.CreateModel(
            name='City',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('api_id', models.IntegerField(unique=True, verbose_name='identificador externo')),
                ('name', models.CharField(max_length=100, verbose_name='nombre')),
            ],
            options={
                'verbose_name': 'ciudad',
                'verbose_name_plural': 'ciudades',
                'ordering': ['name'],
            },
        ),
        migrations.CreateModel(
            name='Department',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('api_id', models.IntegerField(unique=True, verbose_name='identificador externo')),
                ('name', models.CharField(max_length=100, verbose_name='nombre')),
            ],
            options={
                'verbose_name': 'departamento',
                'verbose_name_plural': 'departamentos',
                'ordering': ['name'],
            },
        ),
        migrations.AddField(
            model_name='city',
            name='department',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='cities', to='users.department', verbose_name='departamento'),
        ),
        migrations.RunPython(
            migrate_existing_geo_data,
            migrations.RunPython.noop,
        ),
        migrations.AlterField(
            model_name='address',
            name='city',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='addresses', to='users.city', verbose_name='ciudad o municipio'),
        ),
        migrations.AlterField(
            model_name='address',
            name='department',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='addresses', to='users.department', verbose_name='departamento'),
        ),
        migrations.AddIndex(
            model_name='city',
            index=models.Index(fields=['department', 'name'], name='idx_city_department_name'),
        ),
    ]