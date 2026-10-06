from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('businesses', '0007_min_duration_5'),
    ]

    operations = [
        migrations.AddField(
            model_name='business',
            name='custom_category',
            field=models.CharField(blank=True, max_length=120, verbose_name='Προσαρμοσμένη Κατηγορία'),
        ),
    ]
