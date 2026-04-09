#!/usr/bin/env python3
"""
Migration script to add password_hash column to users table.

This script adds the password_hash column to existing users.
Existing users will have password_hash=NULL until they login,
at which point they will set their password.

Usage:
    python migrate_add_passwords.py
"""

from app import create_app
from models import db
from sqlalchemy import text

def migrate():
    """Add password_hash column to users table"""
    app = create_app()
    with app.app_context():
        try:
            # Check if column already exists
            result = db.session.execute(text(
                "SELECT COUNT(*) FROM pragma_table_info('users') WHERE name='password_hash'"
            ))
            count = result.scalar()

            if count > 0:
                print("✓ password_hash column already exists in users table")
                return

            # Add the column
            print("Adding password_hash column to users table...")
            db.session.execute(text(
                "ALTER TABLE users ADD COLUMN password_hash VARCHAR(255)"
            ))
            db.session.commit()
            print("✓ Successfully added password_hash column")
            print("\nNote: Existing users will be prompted to set their password on next login.")

        except Exception as e:
            print(f"✗ Error during migration: {e}")
            db.session.rollback()
            raise

if __name__ == '__main__':
    migrate()
