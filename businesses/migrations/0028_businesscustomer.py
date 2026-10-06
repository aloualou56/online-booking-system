# Generated manually on 2026-04-05

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('businesses', '0027_remove_business_google_calendar_fields'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='BusinessCustomer',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('identity_key', models.CharField(max_length=255, verbose_name='Κλειδί Ταυτότητας')),
                ('display_name', models.CharField(max_length=150, verbose_name='Ονοματεπώνυμο')),
                ('phone', models.CharField(blank=True, max_length=20, verbose_name='Τηλέφωνο')),
                ('email', models.EmailField(blank=True, max_length=254, verbose_name='Email')),
                ('notes', models.TextField(blank=True, verbose_name='Σημειώσεις / Προτιμήσεις')),
                ('booking_count', models.PositiveIntegerField(default=0, verbose_name='Συνολικά Ραντεβού')),
                ('last_booking_at', models.DateTimeField(blank=True, null=True, verbose_name='Τελευταίο Ραντεβού')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('business', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='business_customers', to='businesses.business', verbose_name='Επιχείρηση')),
                ('user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='business_customer_profiles', to=settings.AUTH_USER_MODEL, verbose_name='Χρήστης')),
            ],
            options={
                'verbose_name': 'Πελάτης Επιχείρησης',
                'verbose_name_plural': 'Πελάτες Επιχείρησης',
                'ordering': ['display_name'],
            },
        ),
        migrations.AddConstraint(
            model_name='businesscustomer',
            constraint=models.UniqueConstraint(fields=('business', 'identity_key'), name='unique_business_customer_identity'),
        ),
    ]
