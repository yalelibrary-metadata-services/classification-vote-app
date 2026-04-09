#!/usr/bin/env python3
"""
Sample 2000 records from the database while ensuring:
- Each user has some records they've voted on
- Some records have no votes at all
- Performance improvement by reducing data size

Usage:
    python sample_database.py
"""

from app import create_app
from models import db, Record, Note, Vote, User
import random

def sample_database(target_records=2000, records_per_user=150, unvoted_records=400):
    """
    Sample records from database.

    Args:
        target_records: Total number of records to keep (default 2000)
        records_per_user: Number of records per user to ensure (default 150)
        unvoted_records: Number of records with no votes to keep (default 400)
    """
    app = create_app()
    with app.app_context():
        print("Starting database sampling...")
        print(f"Current stats:")

        total_records = Record.query.count()
        total_notes = Note.query.count()
        total_votes = Vote.query.count()
        total_users = User.query.count()

        print(f"  Records: {total_records}")
        print(f"  Notes: {total_notes}")
        print(f"  Votes: {total_votes}")
        print(f"  Users: {total_users}")

        if total_records <= target_records:
            print(f"\nDatabase already has {total_records} records (target: {target_records}). No sampling needed.")
            return

        # Get all users with votes
        users = db.session.query(User.id).join(Vote).distinct().all()
        user_ids = [u[0] for u in users]
        print(f"\nUsers with votes: {len(user_ids)}")

        selected_record_ids = set()

        # 1. Get records where each user has voted
        print("\nStep 1: Selecting records for each user...")
        for user_id in user_ids:
            # Get record IDs where this user has voted
            record_ids = db.session.query(Record.id)\
                .join(Note)\
                .join(Vote)\
                .filter(Vote.user_id == user_id)\
                .distinct()\
                .all()
            record_ids = [r[0] for r in record_ids]

            # Sample up to records_per_user for this user
            sample_count = min(records_per_user, len(record_ids))
            sampled = random.sample(record_ids, sample_count)
            selected_record_ids.update(sampled)
            print(f"  User {user_id}: {len(record_ids)} total, sampled {sample_count}")

        print(f"  Total records with user votes: {len(selected_record_ids)}")

        # 2. Get records with no votes at all
        print("\nStep 2: Selecting unvoted records...")
        unvoted_record_ids = db.session.query(Record.id)\
            .outerjoin(Note)\
            .outerjoin(Vote)\
            .filter(Vote.id == None)\
            .all()
        unvoted_record_ids = [r[0] for r in unvoted_record_ids]

        # Sample unvoted records (avoid duplicates)
        available_unvoted = [rid for rid in unvoted_record_ids if rid not in selected_record_ids]
        unvoted_sample_count = min(unvoted_records, len(available_unvoted))
        if available_unvoted:
            sampled_unvoted = random.sample(available_unvoted, unvoted_sample_count)
            selected_record_ids.update(sampled_unvoted)
            print(f"  Unvoted records: {len(available_unvoted)} available, sampled {unvoted_sample_count}")

        # 3. Fill remaining with random records
        if len(selected_record_ids) < target_records:
            print("\nStep 3: Filling remaining with random records...")
            all_record_ids = [r[0] for r in db.session.query(Record.id).all()]
            available_random = [rid for rid in all_record_ids if rid not in selected_record_ids]

            remaining_needed = target_records - len(selected_record_ids)
            random_sample_count = min(remaining_needed, len(available_random))

            if available_random:
                sampled_random = random.sample(available_random, random_sample_count)
                selected_record_ids.update(sampled_random)
                print(f"  Added {random_sample_count} random records")

        print(f"\nTotal records selected: {len(selected_record_ids)}")

        # 4. Delete records not in selected set
        print("\nStep 4: Deleting non-selected records...")
        records_to_delete = Record.query.filter(~Record.id.in_(selected_record_ids)).all()
        delete_count = len(records_to_delete)

        print(f"  Will delete {delete_count} records...")

        # Confirm before deletion
        response = input("\nProceed with deletion? (yes/no): ")
        if response.lower() != 'yes':
            print("Aborted.")
            return

        # Delete in batches to avoid memory issues
        batch_size = 100
        for i in range(0, delete_count, batch_size):
            batch = records_to_delete[i:i+batch_size]
            for record in batch:
                db.session.delete(record)
            db.session.commit()
            print(f"  Deleted batch {i//batch_size + 1}/{(delete_count + batch_size - 1)//batch_size}")

        # Get final stats
        final_records = Record.query.count()
        final_notes = Note.query.count()
        final_votes = Vote.query.count()

        print("\nFinal stats:")
        print(f"  Records: {final_records} (was {total_records})")
        print(f"  Notes: {final_notes} (was {total_notes})")
        print(f"  Votes: {final_votes} (was {total_votes})")
        print(f"\nDatabase sampling complete!")

if __name__ == '__main__':
    # Set seed for reproducibility
    random.seed(42)
    sample_database()
