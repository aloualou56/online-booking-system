# Generated migration for guest review support

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('reviews', '0002_review_business_reply'),
    ]

    operations = [
        migrations.AlterField(
            model_name='review',
            name='customer',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='reviews', to='accounts.customuser'),
        ),
        migrations.AddField(
            model_name='review',
            name='guest_name',
            field=models.CharField(blank=True, max_length=100, verbose_name='Όνομα Επισκέπτη'),
        ),
        migrations.AddField(
            model_name='review',
            name='guest_email',
            field=models.EmailField(blank=True, max_length=254, verbose_name='Email Επισκέπτη'),
        ),
    ]
