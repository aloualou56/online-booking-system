#!/usr/bin/env python
"""
Restore PostgreSQL database connection.
Run this after testing with SQLite to go back to PostgreSQL.
"""

import os
import sys

def main():
    print("🔧 RESTORING POSTGRESQL CONNECTION")
    print("=" * 50)

    # Check if we have a backup
    db_backup = os.environ.get('DATABASE_URL_BACKUP')
    if not db_backup:
        print("❌ No DATABASE_URL backup found!")
        print("Please manually set your DATABASE_URL environment variable")
        return

    print("💾 Restoring DATABASE_URL from DATABASE_URL_BACKUP")

    # Restore DATABASE_URL
    os.environ['DATABASE_URL'] = db_backup
    del os.environ['DATABASE_URL_BACKUP']

    print("✅ PostgreSQL connection restored!")
    print("\nNext steps:")
    print("1. Start PostgreSQL service if not running")
    print("2. Run: python manage.py migrate")
    print("3. Run: python manage.py reset_database --yes-i-am-sure")

if __name__ == "__main__":
    main()