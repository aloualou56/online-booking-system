from django.db import migrations, models
import django.core.validators


class Migration(migrations.Migration):

    dependencies = [
        ('businesses', '0020_business_allow_superadmin_troubleshooting_access'),
    ]

    operations = [
        migrations.AddField(
            model_name='business',
            name='sms_reminder_minutes_before',
            field=models.PositiveIntegerField(
                default=30,
                help_text='Πόσα λεπτά πριν το ραντεβού θα σταλεί SMS υπενθύμιση στην επιχείρηση.',
                validators=[django.core.validators.MinValueValidator(5), django.core.validators.MaxValueValidator(1440)],
                verbose_name='SMS υπενθύμιση πριν το ραντεβού (λεπτά)',
            ),
        ),
    ]
