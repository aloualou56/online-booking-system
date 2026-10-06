#!/usr/bin/env python
"""
Temporarily switch to SQLite database for testing/development.
This will:
1. Backup your current DATABASE_URL
2. Remove DATABASE_URL to use SQLite
3. Run migrations
4. Create super admin
"""

import os
import sys
import subprocess

def run_command(command, description):
    """Run a command and print its output"""
    print(f"\n🔄 {description}...")
    print(f"Running: {command}")

    try:
        result = subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
        if result.stdout:
            print(result.stdout)
        print(f"✅ {description} completed successfully!")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Error during {description}:")
        print(f"Return code: {e.returncode}")
        if e.stderr:
            print(f"Error output: {e.stderr}")
        if e.stdout:
            print(f"Output: {e.stdout}")
        return False

def main():
    print("🔧 SWITCHING TO SQLITE FOR TESTING")
    print("=" * 50)
    print("This will temporarily use SQLite instead of PostgreSQL")
    print("Your PostgreSQL data will NOT be affected")
    print("=" * 50)

    # Check if DATABASE_URL exists
    db_url = os.environ.get('DATABASE_URL')
    if db_url:
        print("\n💾 DATABASE_URL is set")
        print("This will be temporarily ignored")

    # Temporarily rename DATABASE_URL env variable
    if 'DATABASE_URL' in os.environ:
        os.environ['DATABASE_URL_BACKUP'] = os.environ['DATABASE_URL']
        del os.environ['DATABASE_URL']
        print("✅ Temporarily disabled PostgreSQL connection")

    # Run migrations with SQLite
    if not run_command("python manage.py migrate", "Setting up SQLite database"):
        print("❌ Migration failed!")
        return

    # Create super admin
    if not run_command(
        "python manage.py reset_database --yes-i-am-sure",
        "Creating super admin with SQLite"
    ):
        print("❌ Super admin creation failed!")
        return

    print("\n🎉 SQLITE SETUP COMPLETE! 🎉")
    print("=" * 50)
    print("✅ SQLite database ready")
    print("✅ Super admin created (see SUPERADMIN_* environment variables)")
    print("\nYou can now:")
    print("1. Start the server: python manage.py runserver")
    print("2. Test the login and database reset features")
    print("3. When ready, restore PostgreSQL by setting DATABASE_URL back")
    print("\n🔒 SECURITY NOTE: This is for testing only!")

if __name__ == "__main__":
    main()