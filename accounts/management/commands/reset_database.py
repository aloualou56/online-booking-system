"""
Management command: Reset database and create super admin.
Usage: python manage.py reset_database
WARNING: This will delete ALL data in the database!
"""
from django.core.management.base import BaseCommand
from django.core.management.color import no_style
from django.db import connection
from django.apps import apps
import os

from django.contrib.auth import get_user_model
from django.utils.crypto import get_random_string


class Command(BaseCommand):
    help = 'Reset the entire database and create a super admin account'

    def add_arguments(self, parser):
        parser.add_argument(
            '--yes-i-am-sure',
            action='store_true',
            help='Confirm that you want to delete ALL data',
        )

    def handle(self, *args, **options):
        if not options['yes_i_am_sure']:
            self.stdout.write(
                self.style.ERROR(
                    'This command will DELETE ALL DATA in the database!\n'
                    'If you are sure, run: python manage.py reset_database --yes-i-am-sure'
                )
            )
            return

        self.stdout.write('🗑️  Starting database reset...')

        # Get all models
        all_models = apps.get_models()

        # Delete all data from all tables
        with connection.cursor() as cursor:
            style = no_style()
            db_vendor = connection.vendor

            try:
                # Start transaction
                cursor.execute("BEGIN;")

                # Disable foreign key checks (database-specific)
                if db_vendor == 'sqlite':
                    cursor.execute('PRAGMA foreign_keys=OFF;')
                elif db_vendor == 'postgresql':
                    cursor.execute('SET CONSTRAINTS ALL DEFERRED;')
                elif db_vendor == 'mysql':
                    cursor.execute('SET FOREIGN_KEY_CHECKS = 0;')

                # Delete data from all tables in reverse dependency order
                cleared_tables = []
                for model in reversed(all_models):
                    table_name = model._meta.db_table
                    try:
                        cursor.execute(f'DELETE FROM "{table_name}";')
                        cleared_tables.append(table_name)
                        self.stdout.write(f'  ✅ Cleared table: {table_name}')
                    except Exception as e:
                        self.stdout.write(f'  ⚠️  Could not clear {table_name}: {e}')

                # Reset sequences (database-specific)
                if db_vendor == 'sqlite':
                    try:
                        cursor.execute("DELETE FROM sqlite_sequence;")
                        self.stdout.write('  ✅ Reset SQLite sequences')
                    except Exception as e:
                        self.stdout.write(f'  ⚠️  Could not reset sequences: {e}')
                elif db_vendor == 'postgresql':
                    try:
                        # Get all sequences and reset them to 1
                        cursor.execute("""
                            SELECT schemaname, sequencename
                            FROM pg_sequences
                            WHERE schemaname = 'public'
                        """)
                        sequences = cursor.fetchall()

                        for schema, seq_name in sequences:
                            try:
                                cursor.execute(f'ALTER SEQUENCE "{seq_name}" RESTART WITH 1;')
                                self.stdout.write(f'    ✅ Reset sequence: {seq_name}')
                            except Exception as e:
                                self.stdout.write(f'    ⚠️  Could not reset {seq_name}: {e}')

                        self.stdout.write('  ✅ Reset PostgreSQL sequences')
                    except Exception as e:
                        # Fallback method
                        self.stdout.write(f'  ⚠️  Primary method failed: {e}')
                        try:
                            # Alternative approach - reset sequences based on table names
                            for model in all_models:
                                table_name = model._meta.db_table
                                seq_name = f"{table_name}_id_seq"
                                try:
                                    cursor.execute(f'ALTER SEQUENCE "{seq_name}" RESTART WITH 1;')
                                    self.stdout.write(f'    ✅ Reset sequence: {seq_name}')
                                except Exception:
                                    # Some tables might not have sequences, that's okay
                                    pass
                        except Exception as fallback_e:
                            self.stdout.write(f'  ❌ Could not reset sequences: {fallback_e}')

                # Re-enable foreign key checks (database-specific)
                if db_vendor == 'sqlite':
                    cursor.execute('PRAGMA foreign_keys=ON;')
                elif db_vendor == 'postgresql':
                    # PostgreSQL doesn't need explicit re-enabling, constraints are restored after transaction
                    pass
                elif db_vendor == 'mysql':
                    cursor.execute('SET FOREIGN_KEY_CHECKS = 1;')

                # Commit the transaction
                cursor.execute("COMMIT;")
                self.stdout.write(f'  ✅ Successfully cleared {len(cleared_tables)} tables')

            except Exception as e:
                # Rollback on error
                try:
                    cursor.execute("ROLLBACK;")
                except Exception:
                    pass
                self.stdout.write(self.style.ERROR(f'❌ Database reset failed: {e}'))
                raise

        self.stdout.write(self.style.SUCCESS('🗑️  Database wiped successfully!'))

        # Create super admin user
        User = get_user_model()

        # Credentials come from the environment; if no password is supplied a
        # random one is generated and shown ONCE below.
        username = os.environ.get('SUPERADMIN_USERNAME', 'superadmin')
        email = os.environ.get('SUPERADMIN_EMAIL', 'admin@example.com')
        password = os.environ.get('SUPERADMIN_PASSWORD')
        generated = not password
        if generated:
            password = get_random_string(24)

        super_admin = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            first_name='Super',
            last_name='Admin',
            role='super_admin',
            is_superuser=True,
            is_staff=True,
            is_approved=True,
        )

        self.stdout.write(
            self.style.SUCCESS(
                f'👑 Super admin created successfully!\n'
                f'   Username: {super_admin.username}\n'
                f'   Email: {super_admin.email}\n'
                f'   Role: {super_admin.get_role_display()}'
            )
        )
        if generated:
            self.stdout.write(
                self.style.WARNING(
                    f'   Generated password (shown once, store it safely): {password}'
                )
            )

        self.stdout.write(
            self.style.WARNING(
                '\n🔒 IMPORTANT: Change the password after first login!'
            )
        )