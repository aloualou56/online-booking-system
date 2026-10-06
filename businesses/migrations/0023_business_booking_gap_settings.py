from django.db import migrations, models
import django.core.validators


class Migration(migrations.Migration):

    dependencies = [
        ('businesses', '0021_business_sms_reminder_minutes_before'),
    ]

    operations = [
        migrations.AddField(
            model_name='business',
            name='booking_gap_enabled',
            field=models.BooleanField(
                default=False,
                help_text='Αν είναι ενεργό, προστίθεται κενό χρόνος μεταξύ των ραντεβού.',
                verbose_name='Κενό μεταξύ ραντεβού',
            ),
        ),
        migrations.AddField(
            model_name='business',
            name='booking_gap_minutes',
            field=models.PositiveIntegerField(
                default=0,
                help_text='Πόσα λεπτά να αφήνονται ανάμεσα σε δύο ραντεβού.',
                validators=[django.core.validators.MinValueValidator(0), django.core.validators.MaxValueValidator(240)],
                verbose_name='Κενό μεταξύ ραντεβού (λεπτά)',
            ),
        ),
    ]