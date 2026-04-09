from collections import Counter
from models import Vote, Setting

# Classification types in priority order for tie-breaking
CLASSIFICATION_TYPES = ['w', 'o', 'ow', 'aw', 'ao', 'aow']

def calculate_vote_distribution(note_id):
    """
    Calculate vote distribution and consensus for a note.

    Args:
        note_id: ID of the note to calculate distribution for

    Returns:
        dict with keys:
            - votes: Dict of classification -> count (e.g., {'w': 3, 'o': 2})
            - total: Total number of votes
            - probabilities: Dict of classification -> probability (e.g., {'w': 0.60, 'o': 0.40})
            - consensus: Classification with highest votes (None if no votes)
            - consensus_probability: Probability of consensus classification
            - is_contentious: True if consensus is below threshold with min votes
    """
    votes = Vote.query.filter_by(note_id=note_id).all()

    if not votes:
        return {
            'votes': {},
            'total': 0,
            'probabilities': {},
            'consensus': None,
            'consensus_probability': 0.0,
            'is_contentious': False
        }

    # Count votes by classification
    vote_counts = Counter([v.classification for v in votes])
    total_votes = len(votes)

    # Calculate probabilities
    probabilities = {
        classification: count / total_votes
        for classification, count in vote_counts.items()
    }

    # Determine consensus (highest vote count, break ties alphabetically by priority)
    # Sort by count (descending), then by priority order (ascending)
    sorted_classifications = sorted(
        vote_counts.items(),
        key=lambda x: (-x[1], CLASSIFICATION_TYPES.index(x[0]) if x[0] in CLASSIFICATION_TYPES else 999)
    )
    consensus = sorted_classifications[0][0]
    consensus_probability = probabilities[consensus]

    # Check if contentious
    threshold = get_contentious_threshold()
    min_votes = get_min_votes_for_contentious()
    is_contentious = (total_votes >= min_votes and consensus_probability < threshold)

    return {
        'votes': dict(vote_counts),
        'total': total_votes,
        'probabilities': probabilities,
        'consensus': consensus,
        'consensus_probability': consensus_probability,
        'is_contentious': is_contentious,
        'component_breakdown': get_component_breakdown(note_id)
    }


def get_component_breakdown(note_id):
    """
    Calculate how many votes include each component (O, W, A).

    Args:
        note_id: ID of the note to analyze

    Returns:
        dict with keys:
            - o_count: Number of votes containing 'o'
            - w_count: Number of votes containing 'w'
            - a_count: Number of votes containing 'a'
            - o_percentage: Percentage of votes with 'o'
            - w_percentage: Percentage of votes with 'w'
            - a_percentage: Percentage of votes with 'a'
    """
    votes = Vote.query.filter_by(note_id=note_id).all()
    if not votes:
        return {
            'o_count': 0,
            'w_count': 0,
            'a_count': 0,
            'o_percentage': 0,
            'w_percentage': 0,
            'a_percentage': 0
        }

    total = len(votes)
    o_count = sum(1 for v in votes if 'o' in v.classification.lower())
    w_count = sum(1 for v in votes if 'w' in v.classification.lower())
    a_count = sum(1 for v in votes if 'a' in v.classification.lower())

    return {
        'o_count': o_count,
        'w_count': w_count,
        'a_count': a_count,
        'o_percentage': round((o_count / total) * 100) if total > 0 else 0,
        'w_percentage': round((w_count / total) * 100) if total > 0 else 0,
        'a_percentage': round((a_count / total) * 100) if total > 0 else 0,
    }


def get_contentious_threshold():
    """Get contentious threshold from settings table (default 0.70)"""
    setting = Setting.query.filter_by(key='contentious_threshold').first()
    if setting:
        try:
            return float(setting.value)
        except ValueError:
            return 0.70
    return 0.70


def get_min_votes_for_contentious():
    """Get minimum votes required before marking as contentious (default 3)"""
    setting = Setting.query.filter_by(key='min_votes_contentious').first()
    if setting:
        try:
            return int(setting.value)
        except ValueError:
            return 3
    return 3


def update_contentious_threshold(new_threshold):
    """
    Update the contentious threshold setting.

    Args:
        new_threshold: Float between 0 and 1
    """
    from models import db

    if not 0 < new_threshold < 1:
        raise ValueError("Threshold must be between 0 and 1")

    setting = Setting.query.filter_by(key='contentious_threshold').first()
    if not setting:
        setting = Setting(
            key='contentious_threshold',
            value=str(new_threshold),
            description='Minimum consensus probability to avoid contentious marking'
        )
        db.session.add(setting)
    else:
        setting.value = str(new_threshold)

    db.session.commit()


def update_min_votes_for_contentious(new_min_votes):
    """
    Update the minimum votes for contentious setting.

    Args:
        new_min_votes: Integer >= 1
    """
    from models import db

    if new_min_votes < 1:
        raise ValueError("Minimum votes must be at least 1")

    setting = Setting.query.filter_by(key='min_votes_contentious').first()
    if not setting:
        setting = Setting(
            key='min_votes_contentious',
            value=str(new_min_votes),
            description='Minimum number of votes required before marking as contentious'
        )
        db.session.add(setting)
    else:
        setting.value = str(new_min_votes)

    db.session.commit()


def get_user_vote_for_note(user_id, note_id):
    """
    Get a user's current vote for a note, if any.

    Args:
        user_id: ID of the user
        note_id: ID of the note

    Returns:
        Classification string if user has voted, None otherwise
    """
    vote = Vote.query.filter_by(user_id=user_id, note_id=note_id).first()
    return vote.classification if vote else None


def format_vote_display(distribution):
    """
    Format vote distribution for UI display.

    Args:
        distribution: Dict from calculate_vote_distribution()

    Returns:
        String like "W: 50% (3), O: 33% (2), A: 17% (1)"
    """
    if not distribution['votes']:
        return "No votes yet"

    # Sort by count (descending)
    sorted_votes = sorted(
        distribution['votes'].items(),
        key=lambda x: x[1],
        reverse=True
    )

    parts = []
    for classification, count in sorted_votes:
        prob = distribution['probabilities'][classification]
        parts.append(f"{classification.upper()}: {prob:.0%} ({count})")

    return ", ".join(parts)


def get_classification_color(classification):
    """
    Get Bootstrap color class for a classification type.

    Args:
        classification: Classification string ('w', 'o', 'a', etc.)

    Returns:
        Bootstrap color class string
    """
    colors = {
        'w': 'info',
        'o': 'warning',
        'a': 'success',
        'ow': 'secondary',
        'aw': 'dark',
        'ao': 'primary',
        'aow': 'purple'
    }
    return colors.get(classification, 'secondary')


def count_identical_notes(note_text):
    """
    Count how many notes have identical text.

    Args:
        note_text: The text to search for

    Returns:
        Integer count of notes with matching text
    """
    from models import Note
    return Note.query.filter_by(text=note_text).count()


def get_identical_note_ids(note_text):
    """
    Get all note IDs with identical text.

    Args:
        note_text: The text to search for

    Returns:
        List of note IDs
    """
    from models import Note
    notes = Note.query.filter_by(text=note_text).all()
    return [note.id for note in notes]


def get_min_votes_for_export():
    """Get minimum votes required for export (default 1)"""
    setting = Setting.query.filter_by(key='min_votes_export').first()
    if setting:
        try:
            return int(setting.value)
        except ValueError:
            return 1
    return 1


def update_min_votes_for_export(new_min_votes):
    """
    Update the minimum votes for export setting.

    Args:
        new_min_votes: Integer >= 0
    """
    from models import db

    if new_min_votes < 0:
        raise ValueError("Minimum votes must be at least 0")

    setting = Setting.query.filter_by(key='min_votes_export').first()
    if not setting:
        setting = Setting(
            key='min_votes_export',
            value=str(new_min_votes),
            description='Minimum number of votes required to include note in export'
        )
        db.session.add(setting)
    else:
        setting.value = str(new_min_votes)

    db.session.commit()
