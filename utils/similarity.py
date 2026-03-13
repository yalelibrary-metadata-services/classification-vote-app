"""
Fast similarity search using inverted index.
Scales efficiently to 100k+ notes by pre-filtering candidates.
"""

from collections import defaultdict
import re
from rapidfuzz import fuzz

# Common English stopwords to filter out
STOPWORDS = {
    'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'from',
    'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had',
    'do', 'does', 'did', 'will', 'would', 'could', 'should', 'may', 'might',
    'this', 'that', 'these', 'those', 'it', 'its', 'of', 'for', 'with', 'by'
}


class SimilarityIndex:
    """
    Fast similarity search using inverted index.
    Only compares notes that share at least one significant token.

    Performance: O(candidates) instead of O(all_notes)
    For 100k notes: ~50-200ms instead of ~1-2 seconds
    """

    def __init__(self):
        self.token_to_notes = defaultdict(set)  # token -> set of note_ids
        self.note_cache = {}  # note_id -> (note_text, record_bib, note_index)
        self.indexed_count = 0

    def index_note(self, note_id, text, record_bib=None, note_index=None):
        """
        Add a note to the similarity index.

        Args:
            note_id: Unique note identifier
            text: Note text to index
            record_bib: Optional record bib_id for metadata
            note_index: Optional note index for metadata
        """
        tokens = self._tokenize(text)

        # Add to inverted index
        for token in tokens:
            self.token_to_notes[token].add(note_id)

        # Cache note data
        self.note_cache[note_id] = {
            'text': text,
            'record_bib': record_bib,
            'note_index': note_index
        }

        self.indexed_count += 1

    def find_similar(self, text, threshold=85, limit=100, exclude_user_id=None):
        """
        Find notes similar to the given text.

        Args:
            text: Text to find similar notes for
            threshold: Minimum similarity percentage (0-100)
            limit: Maximum number of results to return
            exclude_user_id: If provided, exclude notes the user has already voted on

        Returns:
            List of dicts with keys:
                - note_id: ID of similar note
                - text: Note text
                - similarity: Similarity score (0-100)
                - record_bib: Record bib_id (if available)
                - note_index: Note index (if available)
        """
        if not text or not text.strip():
            return []

        tokens = self._tokenize(text)

        if not tokens:
            # No significant tokens (all stopwords)
            return []

        # Get candidate notes (share at least one token)
        candidates = set()
        for token in tokens:
            candidates.update(self.token_to_notes.get(token, set()))

        # If excluding notes user has voted on, get those note IDs
        user_voted_note_ids = set()
        if exclude_user_id:
            from models import Vote
            user_votes = Vote.query.filter_by(user_id=exclude_user_id).all()
            user_voted_note_ids = {vote.note_id for vote in user_votes}

        # Fuzzy match only candidates (not all notes!)
        similar_notes = []

        for note_id in candidates:
            note_data = self.note_cache.get(note_id)
            if not note_data:
                continue

            note_text = note_data['text']

            # Skip exact matches
            if note_text == text:
                continue

            # Skip notes the user has already voted on
            if exclude_user_id and note_id in user_voted_note_ids:
                continue

            # Calculate similarity using token sort ratio
            # This handles word order differences well
            similarity = fuzz.token_sort_ratio(text, note_text)

            if similarity >= threshold:
                similar_notes.append({
                    'note_id': note_id,
                    'text': note_text,
                    'similarity': similarity,
                    'record_bib': note_data.get('record_bib'),
                    'note_index': note_data.get('note_index')
                })

        # Sort by similarity (descending)
        similar_notes.sort(key=lambda x: x['similarity'], reverse=True)

        return similar_notes[:limit]

    def _tokenize(self, text):
        """
        Extract significant tokens (words) from text.

        Args:
            text: Text to tokenize

        Returns:
            Set of lowercase tokens, excluding stopwords and short words
        """
        # Extract words (alphanumeric sequences)
        tokens = re.findall(r'\w+', text.lower())

        # Filter out stopwords and very short words
        significant_tokens = {
            token for token in tokens
            if token not in STOPWORDS and len(token) > 2
        }

        return significant_tokens

    def clear(self):
        """Clear the index"""
        self.token_to_notes.clear()
        self.note_cache.clear()
        self.indexed_count = 0

    def stats(self):
        """Get index statistics"""
        return {
            'indexed_notes': self.indexed_count,
            'unique_tokens': len(self.token_to_notes),
            'cache_size_mb': self._estimate_memory_usage()
        }

    def _estimate_memory_usage(self):
        """Estimate memory usage in MB (rough approximation)"""
        import sys

        # Estimate inverted index size
        index_size = sum(
            sys.getsizeof(token) + sys.getsizeof(note_ids)
            for token, note_ids in self.token_to_notes.items()
        )

        # Estimate cache size
        cache_size = sum(
            sys.getsizeof(note_id) + sys.getsizeof(data['text'])
            for note_id, data in self.note_cache.items()
        )

        total_bytes = index_size + cache_size
        return round(total_bytes / (1024 * 1024), 2)


# Global similarity index instance
similarity_index = SimilarityIndex()


def rebuild_similarity_index():
    """
    Rebuild the similarity index from database.
    Should be called on application startup or when notes change significantly.

    Returns:
        dict with rebuild statistics
    """
    from models import Note
    import time

    start_time = time.time()

    # Clear existing index
    similarity_index.clear()

    # Stream notes in batches to avoid loading all at once
    batch_size = 1000
    offset = 0
    total_indexed = 0

    while True:
        notes = Note.query.offset(offset).limit(batch_size).all()
        if not notes:
            break

        for note in notes:
            similarity_index.index_note(
                note_id=note.id,
                text=note.text,
                record_bib=note.record.bib_id,
                note_index=note.note_index
            )
            total_indexed += 1

        offset += batch_size

    elapsed_time = time.time() - start_time

    stats = similarity_index.stats()
    stats['rebuild_time_seconds'] = round(elapsed_time, 2)
    stats['notes_per_second'] = round(total_indexed / elapsed_time) if elapsed_time > 0 else 0

    return stats


def add_note_to_index(note_id, text, record_bib=None, note_index=None):
    """
    Add a single note to the index (incremental update).
    Use this when a new note is created to avoid full rebuild.

    Args:
        note_id: Unique note identifier
        text: Note text
        record_bib: Optional record bib_id
        note_index: Optional note index
    """
    similarity_index.index_note(note_id, text, record_bib, note_index)
