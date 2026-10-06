from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('reviews', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='review',
            name='business_reply',
            field=models.TextField(blank=True, verbose_name='Απάντηση Επιχείρησης'),
        ),
        migrations.AddField(
            model_name='review',
            name='replied_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Ημερομηνία Απάντησης'),
        ),
    ]
