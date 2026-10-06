from django.db import migrations


def drop_image_column_if_present(apps, schema_editor):
    """Drop notifications_news.image only where it still exists.

    The field was removed from the News model without a migration. Production
    later had the column dropped by a migration generated directly on the
    server, which has since been deleted, so there the column is already gone
    and this is a no-op. Databases that never saw that file still carry the
    column and get it dropped here.
    """
    connection = schema_editor.connection
    with connection.cursor() as cursor:
        columns = [
            column.name
            for column in connection.introspection.get_table_description(
                cursor, 'notifications_news'
            )
        ]

    if 'image' in columns:
        schema_editor.execute('ALTER TABLE notifications_news DROP COLUMN image')


class Migration(migrations.Migration):

    dependencies = [
        ('notifications', '0004_smsnotification_new_business_type'),
    ]

    operations = [
        # The state change is what silences makemigrations; the database side
        # is conditional because the two environments disagree on the schema.
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.RemoveField(
                    model_name='news',
                    name='image',
                ),
            ],
            database_operations=[
                migrations.RunPython(
                    drop_image_column_if_present,
                    migrations.RunPython.noop,
                ),
            ],
        ),
    ]
