from collections import Counter

from flask import Blueprint, render_template, redirect, url_for, session, flash
from sqlalchemy import exists, and_
from sqlalchemy.orm import joinedload
from models import db, Record, Note, Vote
from auth import login_required
from utils.probability import (
    count_identical_notes, CLASSIFICATION_TYPES,
    get_contentious_threshold, get_min_votes_for_contentious
)

main_bp = Blueprint('main', __name__)


@main_bp.route('/')
@login_required
def index():
    """Display all records"""
    from sqlalchemy import func
    rows = db.session.query(Record, func.count(Note.id).label('note_count'))\
                     .outerjoin(Note, Note.record_id == Record.id)\
                     .group_by(Record.id)\
                     .order_by(Record.bib_id)\
                     .all()

    records_data = [
        {'bib': record.bib_id, 'title': record.title, 'notes': note_count}
        for record, note_count in rows
    ]

    total_records = len(rows)
    total_notes = sum(n for _, n in rows)
    total_votes = Vote.query.count()

    notes_with_vote_counts = db.session.query(func.count(Vote.id))\
        .join(Note)\
        .group_by(Note.id)\
        .all()
    avg_votes = (sum(c for (c,) in notes_with_vote_counts) / len(notes_with_vote_counts)
                 if notes_with_vote_counts else 0)

    classification_dist = db.session.query(
        Vote.classification,
        func.count(Vote.id).label('count')
    ).group_by(Vote.classification).order_by(func.count(Vote.id).desc()).all()

    stats = {
        'total_records': total_records,
        'total_notes': total_notes,
        'total_votes': total_votes,
        'avg_votes_per_note': avg_votes,
    }

    return render_template('index.html', records=records_data, stats=stats,
                           classification_dist=classification_dist)


@main_bp.route('/record/<bib_id>')
@login_required
def record_detail(bib_id):
    """Display detail view for a specific record with classification interface"""
    record = Record.query.filter_by(bib_id=bib_id).first_or_404()

    # Eagerly load notes → votes → users to avoid N+1 queries
    notes = Note.query.filter_by(record_id=record.id)\
                      .order_by(Note.note_index)\
                      .options(joinedload(Note.votes).joinedload(Vote.user))\
                      .all()

    user_id = session.get('user_id')

    # Fetch settings once, not once per note
    threshold = get_contentious_threshold()
    min_votes = get_min_votes_for_contentious()

    notes_data = []
    for note in notes:
        votes = note.votes  # already loaded

        # Compute distribution inline from preloaded votes
        if votes:
            vote_counts = Counter(v.classification for v in votes)
            total = len(votes)
            probabilities = {c: count / total for c, count in vote_counts.items()}
            sorted_cls = sorted(
                vote_counts.items(),
                key=lambda x: (-x[1], CLASSIFICATION_TYPES.index(x[0]) if x[0] in CLASSIFICATION_TYPES else 999)
            )
            consensus = sorted_cls[0][0]
            consensus_prob = probabilities[consensus]
            is_contentious = total >= min_votes and consensus_prob < threshold

            o_count = sum(1 for v in votes if 'o' in v.classification)
            w_count = sum(1 for v in votes if 'w' in v.classification)
            a_count = sum(1 for v in votes if 'a' in v.classification)

            distribution = {
                'votes': dict(vote_counts),
                'total': total,
                'probabilities': probabilities,
                'consensus': consensus,
                'consensus_probability': consensus_prob,
                'is_contentious': is_contentious,
                'component_breakdown': {
                    'o_count': o_count, 'w_count': w_count, 'a_count': a_count,
                    'o_percentage': round(o_count / total * 100),
                    'w_percentage': round(w_count / total * 100),
                    'a_percentage': round(a_count / total * 100),
                }
            }
        else:
            distribution = {
                'votes': {}, 'total': 0, 'probabilities': {},
                'consensus': None, 'consensus_probability': 0.0, 'is_contentious': False,
                'component_breakdown': {
                    'o_count': 0, 'w_count': 0, 'a_count': 0,
                    'o_percentage': 0, 'w_percentage': 0, 'a_percentage': 0,
                }
            }

        # User vote from preloaded data
        user_vote_obj = next((v for v in votes if v.user_id == user_id), None)
        user_vote = user_vote_obj.classification if user_vote_obj else None
        user_needs_review = user_vote_obj.needs_review if user_vote_obj else False

        # Voters grouped by classification from preloaded data (users already loaded)
        voters = {}
        for vote in votes:
            username = vote.user.username if vote.user else 'Unknown'
            if vote.classification not in voters:
                voters[vote.classification] = []
            voters[vote.classification].append(username)

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

    # Targeted prev/next queries instead of loading all records
    prev_record = Record.query.filter(Record.bib_id < bib_id).order_by(Record.bib_id.desc()).first()
    next_record = Record.query.filter(Record.bib_id > bib_id).order_by(Record.bib_id).first()
    current_index = Record.query.filter(Record.bib_id <= bib_id).count() - 1
    total_records = Record.query.count()

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
                         current_index=current_index,
                         total_records=total_records,
                         user_voted_notes=user_voted_notes,
                         total_notes=total_notes,
                         user_progress=user_progress,
                         notes_with_votes=notes_with_votes,
                         overall_progress=overall_progress)


@main_bp.route('/start-unclassified')
@login_required
def start_unclassified():
    """Redirect to first record with unclassified notes (no votes)"""
    note = db.session.query(Note)\
                     .outerjoin(Vote)\
                     .filter(Vote.id == None)\
                     .first()

    if note:
        record = Record.query.get(note.record_id)
        return redirect(url_for('main.record_detail', bib_id=record.bib_id))

    first_record = Record.query.order_by(Record.bib_id).first()
    if first_record:
        return redirect(url_for('main.record_detail', bib_id=first_record.bib_id))

    return redirect(url_for('main.index'))


@main_bp.route('/next-unclassified/<current_bib>')
@login_required
def next_unclassified(current_bib):
    """Navigate to next record with unclassified notes"""
    note = db.session.query(Note)\
                     .join(Record)\
                     .outerjoin(Vote)\
                     .filter(Vote.id == None)\
                     .filter(Record.bib_id > current_bib)\
                     .order_by(Record.bib_id, Note.note_index)\
                     .first()

    if note:
        return redirect(url_for('main.record_detail', bib_id=note.record.bib_id))

    # Wrap around to beginning
    note = db.session.query(Note)\
                     .join(Record)\
                     .outerjoin(Vote)\
                     .filter(Vote.id == None)\
                     .filter(Record.bib_id < current_bib)\
                     .order_by(Record.bib_id, Note.note_index)\
                     .first()

    if note:
        return redirect(url_for('main.record_detail', bib_id=note.record.bib_id))

    return redirect(url_for('main.record_detail', bib_id=current_bib))


@main_bp.route('/next-pending-review/<current_bib>')
@login_required
def next_pending_review(current_bib):
    """Navigate to next record with notes pending review by current user (any unvoted notes)"""
    user_id = session.get('user_id')

    user_voted = exists().where(and_(Vote.note_id == Note.id, Vote.user_id == user_id))

    note = db.session.query(Note)\
                     .join(Record)\
                     .filter(~user_voted)\
                     .filter(Record.bib_id > current_bib)\
                     .order_by(Record.bib_id, Note.note_index)\
                     .first()

    if note:
        return redirect(url_for('main.record_detail', bib_id=note.record.bib_id))

    # Wrap around
    note = db.session.query(Note)\
                     .join(Record)\
                     .filter(~user_voted)\
                     .filter(Record.bib_id < current_bib)\
                     .order_by(Record.bib_id, Note.note_index)\
                     .first()

    if note:
        return redirect(url_for('main.record_detail', bib_id=note.record.bib_id))

    return redirect(url_for('main.record_detail', bib_id=current_bib))


@main_bp.route('/next-with-other-votes/<current_bib>')
@login_required
def next_with_other_votes(current_bib):
    """Navigate to next record with notes that others have voted on but current user hasn't"""
    user_id = session.get('user_id')

    user_voted = exists().where(and_(Vote.note_id == Note.id, Vote.user_id == user_id))
    other_voted = exists().where(and_(Vote.note_id == Note.id, Vote.user_id != user_id))

    note = db.session.query(Note)\
                     .join(Record)\
                     .filter(~user_voted)\
                     .filter(other_voted)\
                     .filter(Record.bib_id > current_bib)\
                     .order_by(Record.bib_id, Note.note_index)\
                     .first()

    if note:
        return redirect(url_for('main.record_detail', bib_id=note.record.bib_id))

    # Wrap around
    note = db.session.query(Note)\
                     .join(Record)\
                     .filter(~user_voted)\
                     .filter(other_voted)\
                     .filter(Record.bib_id < current_bib)\
                     .order_by(Record.bib_id, Note.note_index)\
                     .first()

    if note:
        return redirect(url_for('main.record_detail', bib_id=note.record.bib_id))

    return redirect(url_for('main.record_detail', bib_id=current_bib))


@main_bp.route('/next-my-vote/<current_bib>/<classification>')
@login_required
def next_my_vote(current_bib, classification):
    """Navigate to next record with notes the user voted a specific way"""
    user_id = session.get('user_id')

    valid_classifications = ['o', 'w', 'ow', 'a', 'ao', 'aw', 'aow']
    if classification.lower() not in valid_classifications:
        return redirect(url_for('main.index'))

    classification = classification.lower()

    # Build the base query: notes where user voted this classification
    def find_note(bib_filter):
        return db.session.query(Note)\
                         .join(Record)\
                         .join(Vote, and_(Vote.note_id == Note.id, Vote.user_id == user_id))\
                         .filter(Vote.classification == classification)\
                         .filter(bib_filter)\
                         .order_by(Record.bib_id, Note.note_index)\
                         .first()

    if current_bib == '0':
        note = find_note(Record.bib_id >= '0')
        if note:
            return redirect(url_for('main.record_detail', bib_id=note.record.bib_id))
        flash(f'No records found where you voted {classification.upper()}', 'info')
        return redirect(url_for('main.index'))

    # Verify current record exists
    if not Record.query.filter_by(bib_id=current_bib).first():
        return redirect(url_for('main.index'))

    note = find_note(Record.bib_id > current_bib)
    if note:
        return redirect(url_for('main.record_detail', bib_id=note.record.bib_id))

    # Wrap around
    note = find_note(Record.bib_id < current_bib)
    if note:
        return redirect(url_for('main.record_detail', bib_id=note.record.bib_id))

    flash(f'No records found where you voted {classification.upper()}', 'info')
    return redirect(url_for('main.record_detail', bib_id=current_bib))
