from flask import Blueprint, render_template, redirect, url_for, session, flash
from sqlalchemy.orm import joinedload
from models import db, Record, Note, Vote
from auth import login_required
from utils.probability import calculate_vote_distribution, get_user_vote_for_note, count_identical_notes

main_bp = Blueprint('main', __name__)


@main_bp.route('/')
@login_required
def index():
    """Display all records"""
    records = Record.query.order_by(Record.bib_id).all()

    # Enhance with note counts
    records_data = []
    for record in records:
        note_count = Note.query.filter_by(record_id=record.id).count()
        records_data.append({
            'bib': record.bib_id,
            'title': record.title,
            'notes': note_count
        })

    return render_template('index.html', records=records_data)


@main_bp.route('/record/<bib_id>')
@login_required
def record_detail(bib_id):
    """Display detail view for a specific record with classification interface"""
    record = Record.query.filter_by(bib_id=bib_id).first_or_404()

    # Eagerly load notes with their votes to avoid N+1 queries
    notes = Note.query.filter_by(record_id=record.id)\
                      .order_by(Note.note_index)\
                      .options(joinedload(Note.votes))\
                      .all()

    user_id = session.get('user_id')

    # Build notes data with distributions
    notes_data = []
    for note in notes:
        distribution = calculate_vote_distribution(note.id)

        # Get user's vote object (not just classification)
        user_vote_obj = Vote.query.filter_by(note_id=note.id, user_id=user_id).first()
        user_vote = user_vote_obj.classification if user_vote_obj else None
        user_needs_review = user_vote_obj.needs_review if user_vote_obj else False

        # Get voters grouped by classification
        votes = Vote.query.filter_by(note_id=note.id).all()
        voters = {}
        for vote in votes:
            username = vote.user.username if vote.user else 'Unknown'
            if vote.classification not in voters:
                voters[vote.classification] = []
            voters[vote.classification].append(username)

        # Count identical notes
        identical_count = count_identical_notes(note.text)

        notes_data.append({
            'text': note.text,
            'index': note.note_index,
            'distribution': distribution,
            'user_vote': user_vote,
            'user_needs_review': user_needs_review,
            'voters': voters,
            'identical_count': identical_count
        })

    # Find navigation (prev/next records)
    records = Record.query.order_by(Record.bib_id).all()
    current_index = next((i for i, r in enumerate(records) if r.bib_id == bib_id), None)

    prev_record = records[current_index - 1] if current_index and current_index > 0 else None
    next_record = records[current_index + 1] if current_index is not None and current_index < len(records) - 1 else None

    # Calculate user's voting progress (exclude incomplete votes)
    total_notes = Note.query.count()
    user_voted_notes = db.session.query(Note.id)\
                                  .join(Vote)\
                                  .filter(Vote.user_id == user_id, Vote.needs_review == False)\
                                  .distinct()\
                                  .count()
    user_progress = (user_voted_notes / total_notes * 100) if total_notes > 0 else 0

    # Calculate overall completion progress (notes with at least one vote)
    notes_with_votes = db.session.query(Note.id)\
                                  .join(Vote)\
                                  .distinct()\
                                  .count()
    overall_progress = (notes_with_votes / total_notes * 100) if total_notes > 0 else 0

    return render_template('record.html',
                         record={'bib': record.bib_id, 'title': record.title, 'notes': notes_data},
                         prev_record={'bib': prev_record.bib_id} if prev_record else None,
                         next_record={'bib': next_record.bib_id} if next_record else None,
                         current_index=current_index if current_index is not None else 0,
                         total_records=len(records),
                         user_voted_notes=user_voted_notes,
                         total_notes=total_notes,
                         user_progress=user_progress,
                         notes_with_votes=notes_with_votes,
                         overall_progress=overall_progress)


@main_bp.route('/start-unclassified')
@login_required
def start_unclassified():
    """Redirect to first record with unclassified notes (no votes)"""
    # Find first note with no votes
    note = db.session.query(Note)\
                     .outerjoin(Vote)\
                     .filter(Vote.id == None)\
                     .first()

    if note:
        record = Record.query.get(note.record_id)
        return redirect(url_for('main.record_detail', bib_id=record.bib_id))

    # No unclassified notes, go to first record
    first_record = Record.query.order_by(Record.bib_id).first()
    if first_record:
        return redirect(url_for('main.record_detail', bib_id=first_record.bib_id))

    return redirect(url_for('main.index'))


@main_bp.route('/next-unclassified/<current_bib>')
@login_required
def next_unclassified(current_bib):
    """Navigate to next record with unclassified notes"""
    current_record = Record.query.filter_by(bib_id=current_bib).first_or_404()

    # Find next note without votes after current record
    note = db.session.query(Note)\
                     .join(Record)\
                     .outerjoin(Vote)\
                     .filter(Vote.id == None)\
                     .filter(Record.bib_id > current_bib)\
                     .order_by(Record.bib_id, Note.note_index)\
                     .first()

    if note:
        record = Record.query.get(note.record_id)
        return redirect(url_for('main.record_detail', bib_id=record.bib_id))

    # Wrap around to beginning
    note = db.session.query(Note)\
                     .join(Record)\
                     .outerjoin(Vote)\
                     .filter(Vote.id == None)\
                     .filter(Record.bib_id < current_bib)\
                     .order_by(Record.bib_id, Note.note_index)\
                     .first()

    if note:
        record = Record.query.get(note.record_id)
        return redirect(url_for('main.record_detail', bib_id=record.bib_id))

    # No more unclassified records, stay on current
    return redirect(url_for('main.record_detail', bib_id=current_bib))


@main_bp.route('/next-pending-review/<current_bib>')
@login_required
def next_pending_review(current_bib):
    """Navigate to next record with notes pending review by current user (any unvoted notes)"""
    current_record = Record.query.filter_by(bib_id=current_bib).first_or_404()
    user_id = session.get('user_id')

    # Find notes where current user hasn't voted yet
    records = Record.query.filter(Record.bib_id > current_bib)\
                          .order_by(Record.bib_id).all()

    for record in records:
        notes = Note.query.filter_by(record_id=record.id).all()
        for note in notes:
            user_vote = Vote.query.filter_by(note_id=note.id, user_id=user_id).first()
            if not user_vote:
                return redirect(url_for('main.record_detail', bib_id=record.bib_id))

    # Wrap around
    records = Record.query.filter(Record.bib_id < current_bib)\
                          .order_by(Record.bib_id).all()

    for record in records:
        notes = Note.query.filter_by(record_id=record.id).all()
        for note in notes:
            user_vote = Vote.query.filter_by(note_id=note.id, user_id=user_id).first()
            if not user_vote:
                return redirect(url_for('main.record_detail', bib_id=record.bib_id))

    # No more unvoted notes
    return redirect(url_for('main.record_detail', bib_id=current_bib))


@main_bp.route('/next-with-other-votes/<current_bib>')
@login_required
def next_with_other_votes(current_bib):
    """Navigate to next record with notes that others have voted on but current user hasn't"""
    current_record = Record.query.filter_by(bib_id=current_bib).first_or_404()
    user_id = session.get('user_id')

    # Find notes where others have voted but current user hasn't
    records = Record.query.filter(Record.bib_id > current_bib)\
                          .order_by(Record.bib_id).all()

    for record in records:
        notes = Note.query.filter_by(record_id=record.id).all()
        for note in notes:
            # Check if current user has voted
            user_vote = Vote.query.filter_by(note_id=note.id, user_id=user_id).first()
            if not user_vote:
                # Check if others have voted
                other_votes = Vote.query.filter(
                    Vote.note_id == note.id,
                    Vote.user_id != user_id
                ).first()
                if other_votes:
                    return redirect(url_for('main.record_detail', bib_id=record.bib_id))

    # Wrap around
    records = Record.query.filter(Record.bib_id < current_bib)\
                          .order_by(Record.bib_id).all()

    for record in records:
        notes = Note.query.filter_by(record_id=record.id).all()
        for note in notes:
            # Check if current user has voted
            user_vote = Vote.query.filter_by(note_id=note.id, user_id=user_id).first()
            if not user_vote:
                # Check if others have voted
                other_votes = Vote.query.filter(
                    Vote.note_id == note.id,
                    Vote.user_id != user_id
                ).first()
                if other_votes:
                    return redirect(url_for('main.record_detail', bib_id=record.bib_id))

    # No more notes with others' votes pending user review
    return redirect(url_for('main.record_detail', bib_id=current_bib))


@main_bp.route('/next-my-vote/<current_bib>/<classification>')
@login_required
def next_my_vote(current_bib, classification):
    """Navigate to next record with notes the user voted a specific way"""
    user_id = session.get('user_id')

    # Validate classification
    valid_classifications = ['o', 'w', 'ow', 'a', 'ao', 'aw', 'aow']
    if classification.lower() not in valid_classifications:
        # Invalid classification - go to index
        return redirect(url_for('main.index'))

    classification = classification.lower()

    # Handle special case: current_bib = '0' means start from beginning
    if current_bib == '0':
        # Find first record with matching user vote
        records = Record.query.order_by(Record.bib_id).all()
        for record in records:
            notes = Note.query.filter_by(record_id=record.id).all()
            for note in notes:
                user_vote = Vote.query.filter_by(note_id=note.id, user_id=user_id).first()
                if user_vote and user_vote.classification.lower() == classification:
                    return redirect(url_for('main.record_detail', bib_id=record.bib_id))

        # No records found
        flash(f'No records found where you voted {classification.upper()}', 'info')
        return redirect(url_for('main.index'))

    # Verify current record exists
    current_record = Record.query.filter_by(bib_id=current_bib).first()
    if not current_record:
        return redirect(url_for('main.index'))

    # Find next record after current with matching user vote
    records = Record.query.filter(Record.bib_id > current_bib)\
                          .order_by(Record.bib_id).all()

    for record in records:
        notes = Note.query.filter_by(record_id=record.id).all()
        for note in notes:
            user_vote = Vote.query.filter_by(note_id=note.id, user_id=user_id).first()
            if user_vote and user_vote.classification.lower() == classification:
                return redirect(url_for('main.record_detail', bib_id=record.bib_id))

    # Wrap around to beginning
    records = Record.query.filter(Record.bib_id < current_bib)\
                          .order_by(Record.bib_id).all()

    for record in records:
        notes = Note.query.filter_by(record_id=record.id).all()
        for note in notes:
            user_vote = Vote.query.filter_by(note_id=note.id, user_id=user_id).first()
            if user_vote and user_vote.classification.lower() == classification:
                return redirect(url_for('main.record_detail', bib_id=record.bib_id))

    # No records found with that vote classification - stay on current page
    flash(f'No records found where you voted {classification.upper()}', 'info')
    return redirect(url_for('main.record_detail', bib_id=current_bib))
