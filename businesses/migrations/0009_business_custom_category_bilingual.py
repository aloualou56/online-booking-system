from django.db import migrations, models


def copy_existing_custom_category(apps, schema_editor):
    Business = apps.get_model('businesses', 'Business')
    for business in Business.objects.filter(custom_category__gt=''):
        if not business.custom_category_gr:
            business.custom_category_gr = business.custom_category
        if not business.custom_category_en:
            business.custom_category_en = business.custom_category
        business.save(update_fields=['custom_category_gr', 'custom_category_en'])


class Migration(migrations.Migration):

    dependencies = [
        ('businesses', '0008_business_custom_category'),
    ]

    operations = [
        migrations.AddField(
            model_name='business',
            name='custom_category_en',
            field=models.CharField(blank=True, max_length=120, verbose_name='Προσαρμοσμένη Κατηγορία (Αγγλικά)'),
        ),
        migrations.AddField(
            model_name='business',
            name='custom_category_gr',
            field=models.CharField(blank=True, max_length=120, verbose_name='Προσαρμοσμένη Κατηγορία (Ελληνικά)'),
        ),
        migrations.RunPython(copy_existing_custom_category, migrations.RunPython.noop),
    ]
