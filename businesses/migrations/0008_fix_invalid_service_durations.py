# Generated data migration to fix invalid service durations

from django.db import migrations


def fix_invalid_durations(apps, schema_editor):
    """Update services with duration < 5 minutes to minimum 5 minutes."""
    Service = apps.get_model('businesses', 'Service')
    # Update any services with too short duration
    updated = Service.objects.filter(duration_minutes__lt=5).update(duration_minutes=5)
    if updated:
        print(f"Fixed {updated} service(s) with invalid duration")


def reverse_migration(apps, schema_editor):
    # No reverse action needed - we can't know what the original values were
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('businesses', '0007_min_duration_5'),
    ]

    operations = [
        migrations.RunPython(fix_invalid_durations, reverse_migration),
    ]
