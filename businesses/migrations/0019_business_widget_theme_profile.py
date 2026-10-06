from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('businesses', '0018_business_custom_site_builder'),
    ]

    operations = [
        migrations.AddField(
            model_name='business',
            name='widget_theme_profile',
            field=models.CharField(choices=[('classic', 'Κλασικό χρυσό'), ('site_match', 'Προφίλ που ταιριάζει με το custom site')], default='classic', help_text='Επιλέξτε την οπτική ταυτότητα του booking widget.', max_length=20, verbose_name='Προφίλ widget'),
        ),
    ]
