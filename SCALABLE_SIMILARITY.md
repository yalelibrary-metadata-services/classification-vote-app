# Scalable Similarity Search for 100k+ Notes

## Problem
Naive fuzzy matching (compare against all notes) is O(n) and takes 1-2 seconds for 100k notes.

## Solutions (Ranked by Practicality)

---

## Option 1: Smart Pre-filtering (Recommended)
**Performance**: 50-200ms for 100k notes
**Complexity**: Low
**Infrastructure**: None needed

### Approach
Only compare against notes that share significant tokens (words).

```python
from collections import defaultdict
from rapidfuzz import fuzz

class SimilarityIndex:
    """
    Fast similarity search using inverted index.
    Only compares notes that share at least one token.
    """
    def __init__(self):
        self.token_to_notes = defaultdict(set)  # token -> set of note_ids
        self.note_cache = {}  # note_id -> note_text

    def index_note(self, note_id, text):
        """Add note to index"""
        tokens = self._tokenize(text)
        for token in tokens:
            self.token_to_notes[token].add(note_id)
        self.note_cache[note_id] = text

    def find_similar(self, text, threshold=85, limit=100):
        """
        Find similar notes efficiently.

        1. Tokenize input text
        2. Find all notes that share at least one token (candidate set)
        3. Only run fuzzy match on candidates
        4. Sort by similarity
        """
        tokens = self._tokenize(text)

        # Get candidate notes (share at least one token)
        candidates = set()
        for token in tokens:
            candidates.update(self.token_to_notes.get(token, []))

        # Fuzzy match only candidates (not all notes!)
        similar_notes = []
        for note_id in candidates:
            note_text = self.note_cache[note_id]

            # Skip exact matches
            if note_text == text:
                continue

            similarity = fuzz.token_sort_ratio(text, note_text)

            if similarity >= threshold:
                similar_notes.append({
                    'note_id': note_id,
                    'text': note_text,
                    'similarity': similarity
                })

        # Sort by similarity
        similar_notes.sort(key=lambda x: x['similarity'], reverse=True)
        return similar_notes[:limit]

    def _tokenize(self, text):
        """Extract significant tokens (words)"""
        # Lowercase, split on whitespace/punctuation
        import re
        tokens = re.findall(r'\w+', text.lower())

        # Filter out very common words (stopwords)
        stopwords = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'from', 'is', 'are', 'was', 'were'}
        tokens = [t for t in tokens if t not in stopwords and len(t) > 2]

        return set(tokens)

# Global index (rebuild on startup or periodically)
similarity_index = SimilarityIndex()

def rebuild_similarity_index():
    """Rebuild index from database (run on startup)"""
    from models import Note

    similarity_index = SimilarityIndex()

    # Stream notes in batches to avoid loading all at once
    batch_size = 1000
    offset = 0

    while True:
        notes = Note.query.offset(offset).limit(batch_size).all()
        if not notes:
            break

        for note in notes:
            similarity_index.index_note(note.id, note.text)

        offset += batch_size

    return similarity_index
```

### Performance
- **Candidate selection**: O(tokens × avg_notes_per_token) ≈ O(100-1000)
- **Fuzzy matching**: Only 100-1000 candidates instead of 100k
- **Total time**: 50-200ms (100x faster!)
- **Memory**: ~100-200MB for index (acceptable)
- **Tradeoff**: Might miss notes with no overlapping tokens (rare)

### When to Rebuild Index
- On application startup
- When new notes are added (incremental update)
- Nightly rebuild for consistency

---

## Option 2: PostgreSQL Full-Text Search
**Performance**: 10-50ms for 100k notes
**Complexity**: Medium
**Infrastructure**: PostgreSQL with trigram extension

### Approach
Use PostgreSQL's built-in similarity search with trigram matching.

```python
# In models.py - add index
from sqlalchemy import Index, func

class Note(db.Model):
    # ... existing fields ...

    __table_args__ = (
        # Existing indexes...

        # Add trigram index for similarity search
        Index('idx_note_text_trgm', 'text', postgresql_using='gin',
              postgresql_ops={'text': 'gin_trgm_ops'}),
    )

# Migration to enable extension
# migrations/enable_trigram.py
def upgrade():
    op.execute('CREATE EXTENSION IF NOT EXISTS pg_trgm')

# In utils/similarity.py
def find_similar_notes(note_text, threshold=0.3, limit=100):
    """
    Use PostgreSQL trigram similarity.
    threshold: 0.0-1.0 (0.3 ≈ 70% similar)
    """
    from sqlalchemy import func
    from models import Note

    similar_notes = Note.query.filter(
        func.similarity(Note.text, note_text) > threshold,
        Note.text != note_text  # Exclude exact match
    ).order_by(
        func.similarity(Note.text, note_text).desc()
    ).limit(limit).all()

    results = []
    for note in similar_notes:
        similarity_score = db.session.query(
            func.similarity(note.text, note_text)
        ).scalar()

        results.append({
            'note_id': note.id,
            'text': note.text,
            'similarity': int(similarity_score * 100),
            'record_bib': note.record.bib_id,
            'note_index': note.note_index
        })

    return results
```

### Pros
- Very fast (database-level index)
- Handles large datasets easily
- No memory overhead in application
- Integrated with existing database

### Cons
- Requires PostgreSQL (not SQLite)
- Migration needed
- Different similarity algorithm (trigram vs token-based)

---

## Option 3: Pre-computed Similarity Clusters
**Performance**: <10ms for 100k notes
**Complexity**: High
**Infrastructure**: Background job system

### Approach
Pre-compute similarity clusters offline, store in database.

```python
# New model
class SimilarityCluster(db.Model):
    """Pre-computed groups of similar notes"""
    id = db.Column(db.Integer, primary_key=True)
    representative_note_id = db.Column(db.Integer, db.ForeignKey('notes.id'))
    member_note_ids = db.Column(db.JSON)  # List of similar note IDs
    avg_similarity = db.Column(db.Float)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# Background job (run nightly)
def compute_similarity_clusters():
    """
    Group similar notes into clusters.
    Uses hierarchical clustering or community detection.
    """
    from sklearn.cluster import DBSCAN
    from rapidfuzz import fuzz

    notes = Note.query.all()

    # Compute pairwise similarities (expensive, one-time)
    n = len(notes)
    similarity_matrix = np.zeros((n, n))

    for i in range(n):
        for j in range(i+1, n):
            sim = fuzz.token_sort_ratio(notes[i].text, notes[j].text) / 100.0
            similarity_matrix[i][j] = sim
            similarity_matrix[j][i] = sim

    # Cluster similar notes
    distance_matrix = 1 - similarity_matrix
    clustering = DBSCAN(eps=0.15, min_samples=2, metric='precomputed')
    labels = clustering.fit_predict(distance_matrix)

    # Store clusters
    for cluster_id in set(labels):
        if cluster_id == -1:  # Noise
            continue

        cluster_notes = [notes[i].id for i, label in enumerate(labels) if label == cluster_id]

        cluster = SimilarityCluster(
            representative_note_id=cluster_notes[0],
            member_note_ids=cluster_notes
        )
        db.session.add(cluster)

    db.session.commit()

# Fast lookup
def find_similar_notes(note_id):
    """Instant lookup from pre-computed clusters"""
    cluster = SimilarityCluster.query.filter(
        func.json_contains(SimilarityCluster.member_note_ids, note_id)
    ).first()

    if cluster:
        return Note.query.filter(Note.id.in_(cluster.member_note_ids)).all()

    return []
```

### Pros
- Lightning fast queries (<10ms)
- No computation at request time
- Scalable to millions of notes

### Cons
- Complex setup
- Requires background job system
- Clusters may become stale
- High initial computation cost

---

## Option 4: Elasticsearch / Vector Search
**Performance**: 10-50ms for millions of notes
**Complexity**: High
**Infrastructure**: Elasticsearch or vector database

### Approach
Use specialized search infrastructure.

```python
# Index notes in Elasticsearch
from elasticsearch import Elasticsearch

es = Elasticsearch(['http://localhost:9200'])

def index_note(note_id, text):
    """Index note for similarity search"""
    es.index(index='notes', id=note_id, body={
        'text': text,
        'text_vector': compute_embedding(text)  # Optional: ML embeddings
    })

def find_similar_notes(text, threshold=0.7, limit=100):
    """Use Elasticsearch more_like_this query"""
    response = es.search(index='notes', body={
        'query': {
            'more_like_this': {
                'fields': ['text'],
                'like': text,
                'min_term_freq': 1,
                'min_doc_freq': 1,
                'max_query_terms': 25,
                'min_score': threshold
            }
        },
        'size': limit
    })

    return [hit['_source'] for hit in response['hits']['hits']]
```

### Pros
- Extremely fast and scalable
- Built for this use case
- Supports advanced features (typo tolerance, stemming, etc.)

### Cons
- Requires separate infrastructure
- Operational complexity
- Overkill for <1M notes

---

## Recommendation by Database Size

| Notes | Recommended Approach | Est. Response Time |
|-------|---------------------|-------------------|
| <10k | Naive fuzzy matching | 100-500ms |
| 10k-100k | **Smart pre-filtering** | 50-200ms |
| 100k-500k | PostgreSQL trigram | 10-50ms |
| 500k+ | Pre-computed clusters | <10ms |
| 1M+ | Elasticsearch | 10-50ms |

## For Your Case (100k notes)

### Best Choice: Smart Pre-filtering (Option 1)

**Why:**
- No infrastructure changes needed
- Works with existing SQLite/PostgreSQL
- Fast enough (50-200ms)
- Simple to implement and maintain
- Easy to understand and debug

**Implementation Plan:**
1. Build index on application startup (one-time, ~10-30 seconds)
2. Rebuild index incrementally when new notes added
3. Optional: Cache index to disk for faster startup

**Code:**
```python
# In app.py
from utils.similarity import rebuild_similarity_index

def create_app():
    app = Flask(__name__)
    # ... existing setup ...

    with app.app_context():
        # Build similarity index on startup
        from utils.similarity import similarity_index
        rebuild_similarity_index()

    return app

# In routes/voting.py
@voting_bp.route('/find-similar-notes', methods=['POST'])
@login_required
def find_similar_notes():
    from utils.similarity import similarity_index

    data = request.json
    note_text = data.get('note_text')
    threshold = data.get('threshold', 85)

    # Fast lookup using pre-built index
    similar_notes = similarity_index.find_similar(note_text, threshold=threshold)

    return jsonify({
        'success': True,
        'similar_notes': similar_notes,
        'count': len(similar_notes)
    })
```

### If You Migrate to PostgreSQL Later

Switch to Option 2 (PostgreSQL trigram) for even better performance (10-50ms).

### Performance Monitoring

Add timing logs to track performance:
```python
import time

start = time.time()
similar_notes = similarity_index.find_similar(text)
elapsed = time.time() - start

logger.info(f"Similarity search took {elapsed*1000:.2f}ms, found {len(similar_notes)} results")
```

## Summary

✅ **For 100k notes**: Smart pre-filtering gives ~100ms response time with minimal complexity

✅ **Can scale further**: Easy to upgrade to PostgreSQL trigram or pre-computed clusters later

✅ **Trade-off**: Slight accuracy loss (misses notes with zero token overlap) but very rare in practice

Would you like me to implement the smart pre-filtering approach?
