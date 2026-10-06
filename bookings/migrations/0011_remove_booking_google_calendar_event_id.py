from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('bookings', '0010_booking_google_calendar_event_id'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='booking',
            name='google_calendar_event_id',
        ),
    ]
