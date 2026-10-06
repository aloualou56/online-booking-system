from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('businesses', '0026_business_google_calendar_id_and_more'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='business',
            name='google_calendar_id',
        ),
        migrations.RemoveField(
            model_name='business',
            name='google_calendar_refresh_token',
        ),
        migrations.RemoveField(
            model_name='business',
            name='google_calendar_sync_enabled',
        ),
        migrations.RemoveField(
            model_name='business',
            name='google_calendar_token_uri',
        ),
    ]
