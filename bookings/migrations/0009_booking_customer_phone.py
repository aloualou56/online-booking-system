# Generated migration for customer_phone field

from django.db import migrations, models


def add_customer_phone_if_missing(apps, schema_editor):
    """Add customer_phone column only when it does not already exist."""
    Booking = apps.get_model('bookings', 'Booking')
    table_name = Booking._meta.db_table
    existing_columns = {
        c.name for c in schema_editor.connection.introspection.get_table_description(
            schema_editor.connection.cursor(),
            table_name,
        )
    }
    if 'customer_phone' in existing_columns:
        return

    field = models.CharField(
        blank=True,
        max_length=20,
        verbose_name='Τηλέφωνο Πελάτη (για SMS)',
    )
    field.set_attributes_from_name('customer_phone')
    schema_editor.add_field(Booking, field)


def noop_reverse(apps, schema_editor):
    return


class Migration(migrations.Migration):

    dependencies = [
        ('bookings', '0008_booking_customer_contact_preference'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunPython(
                    add_customer_phone_if_missing,
                    reverse_code=noop_reverse,
                )
            ],
            state_operations=[
                migrations.AddField(
                    model_name='booking',
                    name='customer_phone',
                    field=models.CharField(
                        blank=True,
                        max_length=20,
                        verbose_name='Τηλέφωνο Πελάτη (για SMS)',
                    ),
                )
            ],
        ),
    ]
