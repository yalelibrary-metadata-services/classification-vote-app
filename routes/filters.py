from collections import Counter, defaultdict

from flask import Blueprint, render_template, session
from sqlalchemy import func
from sqlalchemy.orm import joinedload
from models import db, Record, Note, Vote
from auth import login_required
from utils.probability import (
    calculate_vote_distribution, CLASSIFICATION_TYPES,
    get_contentious_threshold, get_min_votes_for_contentious
)

filters_bp = Blueprint('filters', __name__)


@filters_bp.route('/pending-review')
@login_required
def pending_review():
    """Show notes where current user hasn't voted yet"""
    from sqlalchemy import exists, and_
    user_id = session.get('user_id')

    user_voted = exists().where(and_(Vote.note_id == Note.id, Vote.user_id == user_id))

    notes = db.session.query(Note)\
        .join(Record)\
        .filter(~user_voted)\
        .options(joinedload(Note.record))\
        .order_by(Record.bib_id, Note.note_index)\
        .all()

    threshold = get_contentious_threshold()
    min_votes = get_min_votes_for_contentious()

    # Get note counts per record in one query
    record_ids = list({n.record_id for n in notes})
    note_counts = dict(
        db.session.query(Note.record_id, func.count(Note.id))
                  .filter(Note.record_id.in_(record_ids))
                  .group_by(Note.record_id)
                  .all()
    ) if record_ids else {}

    records_dict = defaultdict(list)
    for note in notes:
        distribution = calculate_vote_distribution(note.id)
        records_dict[note.record].append({
            'text': note.text[:150] + ('...' if len(note.text) > 150 else ''),
            'text_full': note.text,
            'index': note.note_index,
            'distribution': distribution,
        })

    pending_records = [
        {
            'bib': record.bib_id,
            'title': record.title,
            'pending_notes': pending_notes,
            'total_notes': note_counts.get(record.id, 0),
            'pending_count': len(pending_notes),
        }
        for record, pending_notes in sorted(records_dict.items(), key=lambda x: x[0].bib_id)
    ]

    return render_template('pending_review.html',
                           pending_records=pending_records,
                           total_pending_records=len(pending_records))


@filters_bp.route('/contentious')
@login_required
def contentious_records():
    """Show notes where consensus is below threshold with sufficient votes"""

    contentious = []
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
            contentious.append({
                'bib': record.bib_id,
                'title': record.title,
                'contentious_notes': contentious_notes,
                'total_notes': len(notes),
                'contentious_count': len(contentious_notes)
            })

    return render_template('contentious.html',
                           contentious_records=contentious,
                           total_contentious_records=len(contentious))


@filters_bp.route('/needs-review')
@login_required
def needs_review():
    """Show notes where current user's vote is incomplete (A-only)"""
    user_id = session.get('user_id')

    # Single query: notes where user has a needs_review vote, with all votes+users+record eager-loaded
    notes = db.session.query(Note)\
        .join(Vote, (Vote.note_id == Note.id) & (Vote.user_id == user_id) & (Vote.needs_review == True))\
        .options(
            joinedload('record'),
            joinedload(Note.votes).joinedload(Vote.user),
        )\
        .order_by(Note.record_id, Note.note_index)\
        .all()

    if not notes:
        return render_template('needs_review.html', needs_review_records=[], total_needs_review_records=0)

    # Note counts per record in one query
    record_ids = list({n.record_id for n in notes})
    note_counts = dict(
        db.session.query(Note.record_id, func.count(Note.id))
                  .filter(Note.record_id.in_(record_ids))
                  .group_by(Note.record_id)
                  .all()
    )

    threshold = get_contentious_threshold()
    min_votes = get_min_votes_for_contentious()

    records_dict = defaultdict(list)
    for note in notes:
        votes = note.votes
        user_vote_obj = next((v for v in votes if v.user_id == user_id), None)

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
            distribution = {
                'votes': dict(vote_counts),
                'total': total,
                'probabilities': probabilities,
                'consensus': consensus,
                'consensus_probability': consensus_prob,
                'is_contentious': total >= min_votes and consensus_prob < threshold,
            }
        else:
            distribution = {
                'votes': {}, 'total': 0, 'probabilities': {},
                'consensus': None, 'consensus_probability': 0.0, 'is_contentious': False,
            }

        records_dict[note.record].append({
            'text': note.text,
            'index': note.note_index,
            'distribution': distribution,
            'current_vote': user_vote_obj.classification if user_vote_obj else '',
        })

    needs_review_records = [
        {
            'bib': record.bib_id,
            'title': record.title,
            'review_notes': review_notes,
            'total_notes': note_counts.get(record.id, 0),
            'review_count': len(review_notes),
        }
        for record, review_notes in sorted(records_dict.items(), key=lambda x: x[0].bib_id)
    ]

    return render_template('needs_review.html',
                           needs_review_records=needs_review_records,
                           total_needs_review_records=len(needs_review_records))
