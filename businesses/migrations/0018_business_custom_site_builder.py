from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('businesses', '0017_business_custom_landing_html'),
    ]

    operations = [
        migrations.AddField(
            model_name='business',
            name='custom_site_enabled',
            field=models.BooleanField(default=False, help_text='Εμφανίζει την προσαρμοσμένη δημόσια σελίδα με προκαθορισμένο layout.', verbose_name='Ενεργή έτοιμη δημόσια σελίδα'),
        ),
        migrations.AddField(
            model_name='business',
            name='custom_site_title',
            field=models.CharField(blank=True, max_length=200, verbose_name='Τίτλος σελίδας'),
        ),
        migrations.AddField(
            model_name='business',
            name='custom_site_subtitle',
            field=models.CharField(blank=True, max_length=300, verbose_name='Υπότιτλος σελίδας'),
        ),
        migrations.AddField(
            model_name='business',
            name='custom_site_about_title',
            field=models.CharField(blank=True, max_length=200, verbose_name='Τίτλος ενότητας'),
        ),
        migrations.AddField(
            model_name='business',
            name='custom_site_about_text',
            field=models.TextField(blank=True, verbose_name='Κείμενο ενότητας'),
        ),
        migrations.AddField(
            model_name='business',
            name='custom_site_cta_text',
            field=models.CharField(blank=True, max_length=100, verbose_name='Κείμενο κουμπιού'),
        ),
        migrations.AddField(
            model_name='business',
            name='custom_site_gallery_title',
            field=models.CharField(blank=True, max_length=200, verbose_name='Τίτλος gallery'),
        ),
        migrations.AddField(
            model_name='business',
            name='custom_site_image_1',
            field=models.ImageField(blank=True, null=True, upload_to='business_site_images/', verbose_name='Εικόνα 1'),
        ),
        migrations.AddField(
            model_name='business',
            name='custom_site_image_2',
            field=models.ImageField(blank=True, null=True, upload_to='business_site_images/', verbose_name='Εικόνα 2'),
        ),
        migrations.AddField(
            model_name='business',
            name='custom_site_image_3',
            field=models.ImageField(blank=True, null=True, upload_to='business_site_images/', verbose_name='Εικόνα 3'),
        ),
    ]
