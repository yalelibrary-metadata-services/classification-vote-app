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


PENDING_REVIEW_LIMIT = 50


@filters_bp.route('/pending-review')
@login_required
def pending_review():
    """Show notes where current user hasn't voted yet (capped at first 50 records)"""
    from sqlalchemy import exists, and_
    user_id = session.get('user_id')

    user_voted = exists().where(and_(Vote.note_id == Note.id, Vote.user_id == user_id))

    # Find the first N record IDs that have unvoted notes
    record_ids = [r for (r,) in
        db.session.query(Note.record_id)
                  .join(Record)
                  .filter(~user_voted)
                  .distinct()
                  .order_by(Record.bib_id)
                  .limit(PENDING_REVIEW_LIMIT)
                  .all()
    ]

    if not record_ids:
        return render_template('pending_review.html', pending_records=[],
                               total_pending_records=0, truncated=False)

    # Load only the unvoted notes for those records, with votes eager-loaded
    notes = db.session.query(Note)\
        .join(Record)\
        .filter(Note.record_id.in_(record_ids))\
        .filter(~user_voted)\
        .options(joinedload(Note.record), joinedload(Note.votes))\
        .order_by(Record.bib_id, Note.note_index)\
        .all()

    threshold = get_contentious_threshold()
    min_votes = get_min_votes_for_contentious()

    note_counts = dict(
        db.session.query(Note.record_id, func.count(Note.id))
                  .filter(Note.record_id.in_(record_ids))
                  .group_by(Note.record_id)
                  .all()
    )

    records_dict = defaultdict(list)
    for note in notes:
        votes = note.votes
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

    # Count total pending records for the truncation notice
    total_pending = db.session.query(Note.record_id)\
        .join(Record)\
        .filter(~user_voted)\
        .distinct()\
        .count()

    return render_template('pending_review.html',
                           pending_records=pending_records,
                           total_pending_records=total_pending,
                           truncated=total_pending > PENDING_REVIEW_LIMIT)


@filters_bp.route('/contentious')
@login_required
def contentious_records():
    """Show notes where consensus is below threshold with sufficient votes"""
    threshold = get_contentious_threshold()
    min_votes = get_min_votes_for_contentious()

    # Load all notes that have at least min_votes votes, with votes+record eager-loaded
    notes = db.session.query(Note)\
        .join(Vote, Vote.note_id == Note.id)\
        .options(joinedload(Note.record), joinedload(Note.votes))\
        .group_by(Note.id)\
        .having(func.count(Vote.id) >= min_votes)\
        .order_by(Note.record_id, Note.note_index)\
        .all()

    # Note counts per record in one query
    record_ids = list({n.record_id for n in notes})
    note_counts = dict(
        db.session.query(Note.record_id, func.count(Note.id))
                  .filter(Note.record_id.in_(record_ids))
                  .group_by(Note.record_id)
                  .all()
    ) if record_ids else {}

    records_dict = defaultdict(list)
    for note in notes:
        votes = note.votes
        vote_counts = Counter(v.classification for v in votes)
        total = len(votes)
        probabilities = {c: count / total for c, count in vote_counts.items()}
        sorted_cls = sorted(
            vote_counts.items(),
            key=lambda x: (-x[1], CLASSIFICATION_TYPES.index(x[0]) if x[0] in CLASSIFICATION_TYPES else 999)
        )
        consensus = sorted_cls[0][0]
        consensus_prob = probabilities[consensus]

        if total >= min_votes and consensus_prob < threshold:
            distribution = {
                'votes': dict(vote_counts),
                'total': total,
                'probabilities': probabilities,
                'consensus': consensus,
                'consensus_probability': consensus_prob,
                'is_contentious': True,
            }
            records_dict[note.record].append({
                'text': note.text[:150] + ('...' if len(note.text) > 150 else ''),
                'text_full': note.text,
                'index': note.note_index,
                'distribution': distribution,
            })

    contentious = [
        {
            'bib': record.bib_id,
            'title': record.title,
            'contentious_notes': contentious_notes,
            'total_notes': note_counts.get(record.id, 0),
            'contentious_count': len(contentious_notes),
        }
        for record, contentious_notes in sorted(records_dict.items(), key=lambda x: x[0].bib_id)
    ]

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
            joinedload(Note.record),
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
