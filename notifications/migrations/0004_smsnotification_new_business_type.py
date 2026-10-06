from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('notifications', '0003_news'),
    ]

    operations = [
        migrations.AlterField(
            model_name='smsnotification',
            name='sms_type',
            field=models.CharField(
                choices=[
                    ('confirmation', 'Επιβεβαίωση ραντεβού'),
                    ('reminder', 'Υπενθύμιση 24ωρο'),
                    ('review_invite', 'Πρόσκληση αξιολόγησης'),
                    ('cancellation', 'Ακύρωση ραντεβού'),
                    ('approved', 'Εγκρίθηκε ραντεβού'),
                    ('rejected', 'Απορρίφθηκε ραντεβού'),
                    ('new_booking', 'Νέο ραντεβού (προς επαγγελματία)'),
                    ('new_business', 'Νέα αίτηση επιχείρησης (προς Super Admin)'),
                ],
                max_length=20,
                verbose_name='Τύπος',
            ),
        ),
    ]
