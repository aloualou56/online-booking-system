from django.core.validators import RegexValidator
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('businesses', '0015_business_break_period'),
    ]

    operations = [
        migrations.AddField(
            model_name='business',
            name='widget_background_color',
            field=models.CharField(default='#f8fafc', max_length=7, validators=[RegexValidator('^#[0-9A-Fa-f]{6}$', 'Χρησιμοποιήστε χρώμα σε μορφή #RRGGBB.')], verbose_name='Widget background χρώμα'),
        ),
        migrations.AddField(
            model_name='business',
            name='widget_dark_color',
            field=models.CharField(default='#8a6500', max_length=7, validators=[RegexValidator('^#[0-9A-Fa-f]{6}$', 'Χρησιμοποιήστε χρώμα σε μορφή #RRGGBB.')], verbose_name='Widget dark χρώμα'),
        ),
        migrations.AddField(
            model_name='business',
            name='widget_primary_color',
            field=models.CharField(default='#c9a227', max_length=7, validators=[RegexValidator('^#[0-9A-Fa-f]{6}$', 'Χρησιμοποιήστε χρώμα σε μορφή #RRGGBB.')], verbose_name='Widget primary χρώμα'),
        ),
        migrations.AddField(
            model_name='business',
            name='widget_secondary_color',
            field=models.CharField(default='#f0c04a', max_length=7, validators=[RegexValidator('^#[0-9A-Fa-f]{6}$', 'Χρησιμοποιήστε χρώμα σε μορφή #RRGGBB.')], verbose_name='Widget secondary χρώμα'),
        ),
    ]
