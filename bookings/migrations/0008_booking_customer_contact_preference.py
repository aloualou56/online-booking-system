from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bookings', '0007_booking_rejection_reason'),
    ]

    operations = [
        migrations.AddField(
            model_name='booking',
            name='customer_contact_preference',
            field=models.CharField(
                blank=True,
                choices=[('email', 'Email'), ('phone', 'Telephone'), ('both', 'Both')],
                default='both',
                max_length=10,
                verbose_name='Προτίμηση Επικοινωνίας Πελάτη',
            ),
        ),
    ]
