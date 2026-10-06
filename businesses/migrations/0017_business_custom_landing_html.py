from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('businesses', '0016_business_widget_palette'),
    ]

    operations = [
        migrations.AddField(
            model_name='business',
            name='custom_landing_html',
            field=models.FileField(blank=True, help_text='Προαιρετικά ανεβάστε αρχείο .html για δημόσια σελίδα στο /<slug>/', null=True, upload_to='business_custom_pages/', verbose_name='Προσαρμοσμένη HTML Σελίδα'),
        ),
    ]
