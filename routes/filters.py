from flask import Blueprint, render_template, session
from models import Record, Note, Vote
from auth import login_required
from utils.probability import calculate_vote_distribution

filters_bp = Blueprint('filters', __name__)


@filters_bp.route('/pending-review')
@login_required
def pending_review():
    """Show notes where current user hasn't voted yet"""
    user_id = session.get('user_id')

    pending_records = []
    records = Record.query.order_by(Record.bib_id).all()

    for record in records:
        notes = Note.query.filter_by(record_id=record.id).order_by(Note.note_index).all()
        pending_notes = []

        for note in notes:
            # User hasn't voted on this note yet
            user_vote = Vote.query.filter_by(note_id=note.id, user_id=user_id).first()

            if not user_vote:
                distribution = calculate_vote_distribution(note.id)
                pending_notes.append({
                    'text': note.text[:150] + ('...' if len(note.text) > 150 else ''),
                    'text_full': note.text,
                    'index': note.note_index,
                    'distribution': distribution
                })

        if pending_notes:
            pending_records.append({
                'bib': record.bib_id,
                'title': record.title,
                'pending_notes': pending_notes,
                'total_notes': len(notes),
                'pending_count': len(pending_notes)
            })

    return render_template('pending_review.html',
                         pending_records=pending_records,
                         total_pending_records=len(pending_records))


@filters_bp.route('/contentious')
@login_required
def contentious_records():
    """Show notes where consensus is below threshold with sufficient votes"""

    contentious_records = []
    records = Record.query.order_by(Record.bib_id).all()

    for record in records:
        notes = Note.query.filter_by(record_id=record.id).order_by(Note.note_index).all()
        contentious_notes = []

        for note in notes:
            distribution = calculate_vote_distribution(note.id)
            if distribution['is_contentious']:
                contentious_notes.append({
                    'text': note.text[:150] + ('...' if len(note.text) > 150 else ''),
                    'text_full': note.text,
                    'index': note.note_index,
                    'distribution': distribution
                })

        if contentious_notes:
            contentious_records.append({
                'bib': record.bib_id,
                'title': record.title,
                'contentious_notes': contentious_notes,
                'total_notes': len(notes),
                'contentious_count': len(contentious_notes)
            })

    return render_template('contentious.html',
                         contentious_records=contentious_records,
                         total_contentious_records=len(contentious_records))


@filters_bp.route('/needs-review')
@login_required
def needs_review():
    """Show notes where current user's vote needs review (incomplete votes)"""
    user_id = session.get('user_id')

    needs_review_records = []
    records = Record.query.order_by(Record.bib_id).all()

    for record in records:
        notes = Note.query.filter_by(record_id=record.id).order_by(Note.note_index).all()
        review_notes = []

        for note in notes:
            # Check if user has incomplete vote
            user_vote = Vote.query.filter_by(note_id=note.id, user_id=user_id).first()

            if user_vote and user_vote.needs_review:
                distribution = calculate_vote_distribution(note.id)
                review_notes.append({
                    'text': note.text[:150] + ('...' if len(note.text) > 150 else ''),
                    'text_full': note.text,
                    'index': note.note_index,
                    'distribution': distribution,
                    'current_vote': user_vote.classification
                })

        if review_notes:
            needs_review_records.append({
                'bib': record.bib_id,
                'title': record.title,
                'review_notes': review_notes,
                'total_notes': len(notes),
                'review_count': len(review_notes)
            })

    return render_template('needs_review.html',
                         needs_review_records=needs_review_records,
                         total_needs_review_records=len(needs_review_records))
