from flask import Blueprint, request, jsonify, session
from datetime import datetime
from models import db, Record, Note, Vote
from auth import login_required
from utils.probability import calculate_vote_distribution, get_identical_note_ids

voting_bp = Blueprint('voting', __name__)


@voting_bp.route('/vote', methods=['POST'])
@login_required
def vote():
    """
    Handle classification vote submission.
    Allows users to create or update their vote for a note.
    """
    data = request.json
    bib_id = data.get('bib_id')
    note_index = data.get('note_index')

    # Handle component array or direct classification
    if 'components' in data:
        components = data.get('components', [])
        # Validate at least one of o/w
        if 'o' not in components and 'w' not in components:
            return jsonify({'error': 'At least one of O or W must be selected'}), 400
        # Sort alphabetically and join: ['w', 'a', 'o'] → 'aow'
        components = sorted([c.lower() for c in components if c.lower() in ['a', 'o', 'w']])
        classification = ''.join(components)
    else:
        classification = data.get('classification')

    # Validate classification
    if classification not in ['o', 'w', 'ow', 'ao', 'aw', 'aow']:
        return jsonify({'error': 'Invalid classification'}), 400

    # Validate note_index
    try:
        note_index = int(note_index)
    except (TypeError, ValueError):
        return jsonify({'error': 'Invalid note index'}), 400

    # Get record by bib_id
    record = Record.query.filter_by(bib_id=bib_id).first()
    if not record:
        return jsonify({'error': 'Record not found'}), 404

    # Get note by record_id and note_index
    note = Note.query.filter_by(record_id=record.id, note_index=note_index).first()
    if not note:
        return jsonify({'error': 'Note not found'}), 404

    user_id = session.get('user_id')

    # Check if user already voted - update or create
    existing_vote = Vote.query.filter_by(note_id=note.id, user_id=user_id).first()

    if existing_vote:
        # Update existing vote
        existing_vote.classification = classification
        existing_vote.needs_review = False  # Clear incomplete flag
        existing_vote.voted_at = datetime.utcnow()
    else:
        # Create new vote
        new_vote = Vote(
            note_id=note.id,
            user_id=user_id,
            classification=classification,
            needs_review=False
        )
        db.session.add(new_vote)

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Database error: {str(e)}'}), 500

    # Calculate new distribution
    distribution = calculate_vote_distribution(note.id)

    # Get voters grouped by classification
    votes = Vote.query.filter_by(note_id=note.id).all()
    voters = {}
    for vote in votes:
        username = vote.user.username if vote.user else 'Unknown'
        if vote.classification not in voters:
            voters[vote.classification] = []
        voters[vote.classification].append(username)

    return jsonify({
        'success': True,
        'classification': classification,
        'distribution': distribution,
        'consensus': distribution['consensus'],
        'consensus_probability': distribution['consensus_probability'],
        'is_contentious': distribution['is_contentious'],
        'voters': voters
    })


@voting_bp.route('/vote-identical', methods=['POST'])
@login_required
def vote_identical():
    """
    Handle bulk classification vote for all identical notes.
    Applies the same classification to all notes with matching text.
    """
    data = request.json
    note_text = data.get('note_text')

    # Handle component array or direct classification
    if 'components' in data:
        components = data.get('components', [])
        # Validate at least one of o/w
        if 'o' not in components and 'w' not in components:
            return jsonify({'error': 'At least one of O or W must be selected'}), 400
        # Sort alphabetically and join: ['w', 'a', 'o'] → 'aow'
        components = sorted([c.lower() for c in components if c.lower() in ['a', 'o', 'w']])
        classification = ''.join(components)
    else:
        classification = data.get('classification')

    # Validate classification
    if classification not in ['o', 'w', 'ow', 'ao', 'aw', 'aow']:
        return jsonify({'error': 'Invalid classification'}), 400

    if not note_text:
        return jsonify({'error': 'Note text required'}), 400

    user_id = session.get('user_id')

    # Get all notes with matching text
    note_ids = get_identical_note_ids(note_text)

    if not note_ids:
        return jsonify({'error': 'No matching notes found'}), 404

    votes_created = 0
    votes_updated = 0

    try:
        for note_id in note_ids:
            # Check if user already voted - update or create
            existing_vote = Vote.query.filter_by(note_id=note_id, user_id=user_id).first()

            if existing_vote:
                existing_vote.classification = classification
                existing_vote.needs_review = False  # Clear incomplete flag
                existing_vote.voted_at = datetime.utcnow()
                votes_updated += 1
            else:
                new_vote = Vote(
                    note_id=note_id,
                    user_id=user_id,
                    classification=classification,
                    needs_review=False
                )
                db.session.add(new_vote)
                votes_created += 1

        db.session.commit()

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Database error: {str(e)}'}), 500

    return jsonify({
        'success': True,
        'classification': classification,
        'total_notes': len(note_ids),
        'votes_created': votes_created,
        'votes_updated': votes_updated
    })


@voting_bp.route('/find-similar-notes', methods=['POST'])
@login_required
def find_similar_notes():
    """
    Find notes similar to the given text using fuzzy matching.
    Uses pre-built inverted index for fast searching (50-200ms for 100k notes).
    Excludes notes the current user has already voted on.
    """
    from utils.similarity import similarity_index
    import time

    data = request.json
    note_text = data.get('note_text')
    threshold = data.get('threshold', 85)  # Default 85% similarity

    if not note_text:
        return jsonify({'error': 'Note text required'}), 400

    # Validate threshold
    try:
        threshold = int(threshold)
        if not 0 <= threshold <= 100:
            threshold = 85
    except (TypeError, ValueError):
        threshold = 85

    # Find similar notes using index, excluding notes the user has already voted on
    user_id = session.get('user_id')
    start_time = time.time()
    similar_notes = similarity_index.find_similar(
        note_text,
        threshold=threshold,
        limit=100,
        exclude_user_id=user_id
    )
    elapsed_time = (time.time() - start_time) * 1000  # Convert to ms

    return jsonify({
        'success': True,
        'similar_notes': similar_notes,
        'count': len(similar_notes),
        'search_time_ms': round(elapsed_time, 2),
        'threshold': threshold
    })


@voting_bp.route('/vote-similar', methods=['POST'])
@login_required
def vote_similar():
    """
    Apply classification vote to multiple selected similar notes.
    Similar to vote-identical but allows user to select specific notes.
    """
    data = request.json
    note_ids = data.get('note_ids', [])

    # Handle component array or direct classification
    if 'components' in data:
        components = data.get('components', [])
        # Validate at least one of o/w
        if 'o' not in components and 'w' not in components:
            return jsonify({'error': 'At least one of O or W must be selected'}), 400
        # Sort alphabetically and join
        components = sorted([c.lower() for c in components if c.lower() in ['a', 'o', 'w']])
        classification = ''.join(components)
    else:
        classification = data.get('classification')

    # Validate classification
    if classification not in ['o', 'w', 'ow', 'ao', 'aw', 'aow']:
        return jsonify({'error': 'Invalid classification'}), 400

    if not note_ids:
        return jsonify({'error': 'No notes selected'}), 400

    # Validate note_ids are integers
    try:
        note_ids = [int(nid) for nid in note_ids]
    except (TypeError, ValueError):
        return jsonify({'error': 'Invalid note IDs'}), 400

    user_id = session.get('user_id')
    votes_created = 0
    votes_updated = 0

    try:
        for note_id in note_ids:
            # Check if user already voted - update or create
            existing_vote = Vote.query.filter_by(note_id=note_id, user_id=user_id).first()

            if existing_vote:
                existing_vote.classification = classification
                existing_vote.needs_review = False  # Clear incomplete flag
                existing_vote.voted_at = datetime.utcnow()
                votes_updated += 1
            else:
                new_vote = Vote(
                    note_id=note_id,
                    user_id=user_id,
                    classification=classification,
                    needs_review=False
                )
                db.session.add(new_vote)
                votes_created += 1

        db.session.commit()

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Database error: {str(e)}'}), 500

    return jsonify({
        'success': True,
        'classification': classification,
        'total_notes': len(note_ids),
        'votes_created': votes_created,
        'votes_updated': votes_updated
    })


