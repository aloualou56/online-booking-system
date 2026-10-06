from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('businesses', '0019_business_widget_theme_profile'),
    ]

    operations = [
        migrations.AddField(
            model_name='business',
            name='allow_superadmin_troubleshooting_access',
            field=models.BooleanField(
                default=False,
                help_text='Επιτρέπει προσωρινή πρόσβαση στον Super Admin στο panel της επιχείρησης για τεχνική υποστήριξη.',
                verbose_name='Πρόσβαση Super Admin για Troubleshooting',
            ),
        ),
    ]
