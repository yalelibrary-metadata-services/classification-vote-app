#!/usr/bin/env python3
"""
Migration script to convert voting system to multi-select O/W with optional A.

This script:
1. Adds needs_review column to votes table
2. Flags existing 'a' only votes as needs_review=True
3. Deletes existing '?' votes (treated as no vote)

Usage:
    python migrate_multiselect_voting.py
"""

from app import create_app
from models import db
from sqlalchemy import text

def migrate():
    """Migrate votes table for multi-select voting system"""
    app = create_app()
    with app.app_context():
        try:
            # Check if column already exists
            result = db.session.execute(text(
                "SELECT COUNT(*) FROM pragma_table_info('votes') WHERE name='needs_review'"
            ))
            count = result.scalar()

            if count > 0:
                print("✓ needs_review column already exists in votes table")
                return

            # Add the needs_review column
            print("Adding needs_review column to votes table...")
            db.session.execute(text(
                "ALTER TABLE votes ADD COLUMN needs_review BOOLEAN DEFAULT FALSE"
            ))
            db.session.commit()
            print("✓ Successfully added needs_review column")

            # Flag existing 'a' only votes as needing review
            print("\nFlagging 'a' only votes as needs_review...")
            result = db.session.execute(text(
                "UPDATE votes SET needs_review = TRUE WHERE classification = 'a'"
            ))
            db.session.commit()
            flagged_count = result.rowcount
            print(f"✓ Flagged {flagged_count} votes as needs_review")

            # Delete existing '?' votes (treated as no vote)
            print("\nDeleting '?' votes...")
            result = db.session.execute(text(
                "DELETE FROM votes WHERE classification = '?'"
            ))
            db.session.commit()
            deleted_count = result.rowcount
            print(f"✓ Deleted {deleted_count} '?' votes")

            print("\n" + "="*60)
            print("Migration completed successfully!")
            print("="*60)
            print(f"Summary:")
            print(f"  - Added needs_review column to votes table")
            print(f"  - Flagged {flagged_count} 'a' only votes as incomplete")
            print(f"  - Deleted {deleted_count} '?' votes")
            print(f"\nUsers with incomplete votes will see a warning to resubmit.")

        except Exception as e:
            print(f"✗ Error during migration: {e}")
            db.session.rollback()
            raise

if __name__ == '__main__':
    migrate()
