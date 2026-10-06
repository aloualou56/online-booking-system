#!/usr/bin/env python
"""
Database reset script for Reserva platform.
This script will:
1. Reset the entire database (DELETE ALL DATA!)
2. Create migrations
3. Apply migrations
4. Create the super admin user (see SUPERADMIN_* environment variables)

WARNING: This will delete ALL existing data!
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
        print(f"Error output: {e.stderr}")
        return False

def main():
    """Main reset procedure"""
    print("🚨 RESERVA DATABASE RESET SCRIPT 🚨")
    print("=" * 50)
    print("This will DELETE ALL DATA and create a fresh database!")
    print("Super admin will be created from the environment variables")
    print("SUPERADMIN_USERNAME / SUPERADMIN_EMAIL / SUPERADMIN_PASSWORD.")
    print("If SUPERADMIN_PASSWORD is not set, a random password is generated and printed once.")
    print("=" * 50)

    # Safety confirmation
    confirm = input("\nType 'RESET' to confirm you want to delete all data: ")
    if confirm != 'RESET':
        print("❌ Reset cancelled.")
        return

    # Step 1: Apply any pending migrations first
    if not run_command("python manage.py migrate", "Applying existing migrations"):
        print("⚠️ Migration failed, continuing with reset...")

    # Step 2: Reset database and create super admin
    if not run_command(
        "python manage.py reset_database --yes-i-am-sure",
        "Resetting database and creating super admin"
    ):
        print("❌ Database reset failed!")
        return

    # Step 3: Apply migrations for the new UserEmail model
    if not run_command("python manage.py migrate", "Applying new migrations"):
        print("❌ Migration failed!")
        return

    print("\n🎉 DATABASE RESET COMPLETE! 🎉")
    print("=" * 50)
    print("✅ Database wiped and recreated")
    print("✅ Super admin created")
    print("✅ Multiple email support enabled")
    print("✅ Profile page updated (role hidden)")
    print("\nYou can now:")
    print("1. Start the server: python manage.py runserver")
    print("2. Login with the super admin credentials printed above")
    print("3. Change the password after first login")
    print("\n🔒 SECURITY NOTE: Change the super admin password immediately!")

if __name__ == "__main__":
    main()