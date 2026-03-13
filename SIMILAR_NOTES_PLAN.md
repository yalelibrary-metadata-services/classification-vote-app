# Similar Notes Feature - Implementation Plan

## Overview
Add ability to vote on "similar" notes (e.g., 85%+ matching) in addition to exact identical notes.

## User Story
As a user, when I see a note like:
- "This document is part of CO 384/30 from The National Archives, UK."

I want to find and vote on similar notes like:
- "This document is part of CO 384/31 from The National Archives, UK."
- "This document is part of CO 384/32 from The National Archives, UK."

Without having to vote on each one individually.

## Technical Approach

### Option 1: Fuzzy String Matching (Recommended)
**Library**: `fuzzywuzzy` or `rapidfuzz` (faster)
**Similarity Algorithm**: Token sort ratio (handles word order variations)
**Threshold**: 85% similarity (configurable)

**Pros**:
- Handles various types of similarity (typos, number variations, word order)
- Battle-tested library
- Fast enough for real-time use
- Works across different note patterns

**Cons**:
- Requires new dependency
- More compute than exact matching

### Option 2: Pattern-Based Matching
**Approach**: Normalize notes by replacing numbers/dates with placeholders
**Example**: "CO 384/30" → "CO {NUM}/{NUM}"

**Pros**:
- No external dependencies
- Very fast
- Perfect for structured notes

**Cons**:
- Only works for specific patterns
- Misses other types of similarity (typos, synonyms)
- Requires pattern definition

### Option 3: Hybrid (Best of Both)
Use pattern matching for known patterns, fuzzy matching as fallback.

## Recommended Implementation: Fuzzy Matching

### Phase 1: Backend - Similarity Detection

#### File: `utils/similarity.py` (new)
```python
from rapidfuzz import fuzz
from models import Note

DEFAULT_SIMILARITY_THRESHOLD = 85

def find_similar_notes(note_text, threshold=DEFAULT_SIMILARITY_THRESHOLD, limit=100):
    """
    Find notes similar to the given text.

    Args:
        note_text: Text to compare against
        threshold: Minimum similarity percentage (0-100)
        limit: Maximum number of similar notes to return

    Returns:
        List of dicts with keys:
            - note_id: ID of similar note
            - text: Note text
            - similarity: Similarity score (0-100)
            - differences: Highlighted differences
    """
    all_notes = Note.query.all()
    similar_notes = []

    for note in all_notes:
        # Skip exact matches (handled by identical notes feature)
        if note.text == note_text:
            continue

        # Calculate similarity using token sort ratio
        # This handles word order and partial matches well
        similarity = fuzz.token_sort_ratio(note_text, note.text)

        if similarity >= threshold:
            similar_notes.append({
                'note_id': note.id,
                'text': note.text,
                'similarity': similarity,
                'record_bib': note.record.bib_id,
                'note_index': note.note_index
            })

    # Sort by similarity (descending)
    similar_notes.sort(key=lambda x: x['similarity'], reverse=True)

    return similar_notes[:limit]


def get_text_differences(text1, text2):
    """
    Highlight differences between two texts.
    Returns HTML with <mark> tags around differences.
    """
    # Could use difflib for more sophisticated diff
    # For now, simple approach
    import difflib

    # Get character-level diff
    diff = difflib.unified_diff(
        text1.split(),
        text2.split(),
        lineterm=''
    )

    # Format for display
    # This is simplified - could be enhanced
    return ' '.join(diff)
```

#### File: `routes/voting.py` - Add endpoint
```python
@voting_bp.route('/find-similar-notes', methods=['POST'])
@login_required
def find_similar_notes():
    """Find notes similar to the given text"""
    from utils.similarity import find_similar_notes as find_similar

    data = request.json
    note_text = data.get('note_text')
    threshold = data.get('threshold', 85)

    if not note_text:
        return jsonify({'error': 'Note text required'}), 400

    similar_notes = find_similar(note_text, threshold=threshold)

    return jsonify({
        'success': True,
        'similar_notes': similar_notes,
        'count': len(similar_notes)
    })


@voting_bp.route('/vote-similar', methods=['POST'])
@login_required
def vote_similar():
    """Vote on selected similar notes"""
    data = request.json
    note_ids = data.get('note_ids', [])

    # Handle component array or direct classification
    if 'components' in data:
        components = data.get('components', [])
        if 'o' not in components and 'w' not in components:
            return jsonify({'error': 'At least one of O or W must be selected'}), 400
        components = sorted([c.lower() for c in components if c.lower() in ['a', 'o', 'w']])
        classification = ''.join(components)
    else:
        classification = data.get('classification')

    # Validate
    if classification not in ['o', 'w', 'ow', 'ao', 'aw', 'aow', '?']:
        return jsonify({'error': 'Invalid classification'}), 400

    if not note_ids:
        return jsonify({'error': 'No notes selected'}), 400

    user_id = session.get('user_id')
    votes_created = 0
    votes_updated = 0

    try:
        for note_id in note_ids:
            existing_vote = Vote.query.filter_by(note_id=note_id, user_id=user_id).first()

            if existing_vote:
                existing_vote.classification = classification
                existing_vote.needs_review = False
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
```

### Phase 2: Frontend UI

#### Option A: Modal Dialog (Recommended)
```html
<!-- In record.html, add button next to identical notes checkbox -->
<button class="btn btn-sm btn-outline-info mt-2 find-similar-btn w-100"
        data-note-text="{{ note.text }}">
    <i class="fas fa-search"></i> Find Similar Notes
</button>

<!-- Modal to show similar notes -->
<div class="modal fade" id="similarNotesModal" tabindex="-1">
  <div class="modal-dialog modal-lg">
    <div class="modal-content">
      <div class="modal-header">
        <h5 class="modal-title">Similar Notes Found</h5>
        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
      </div>
      <div class="modal-body">
        <p class="text-muted">Select which notes to apply your classification to:</p>

        <div class="alert alert-info">
          <strong>Original Note:</strong><br>
          <span id="originalNoteText"></span>
        </div>

        <div id="similarNotesList">
          <!-- Populated by JavaScript -->
        </div>
      </div>
      <div class="modal-footer">
        <span class="me-auto text-muted">
          <span id="selectedCount">0</span> notes selected
        </span>
        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
        <button type="button" class="btn btn-primary" id="applyToSimilarBtn">
          Apply Classification
        </button>
      </div>
    </div>
  </div>
</div>
```

#### JavaScript: `static/js/app.js`
```javascript
// Find Similar Notes button handler
document.querySelectorAll('.find-similar-btn').forEach(button => {
    button.addEventListener('click', function() {
        const noteText = this.dataset.noteText;
        const noteCard = this.closest('.note-card');

        // Show loading
        this.disabled = true;
        this.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Searching...';

        // Find similar notes
        fetch('/find-similar-notes', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                note_text: noteText,
                threshold: 85
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                showSimilarNotesModal(noteText, data.similar_notes, noteCard);
            } else {
                showNotification('Error finding similar notes', 'error');
            }
        })
        .finally(() => {
            this.disabled = false;
            this.innerHTML = '<i class="fas fa-search"></i> Find Similar Notes';
        });
    });
});

function showSimilarNotesModal(originalText, similarNotes, noteCard) {
    // Populate modal
    document.getElementById('originalNoteText').textContent = originalText;

    const listContainer = document.getElementById('similarNotesList');

    if (similarNotes.length === 0) {
        listContainer.innerHTML = '<p class="text-muted">No similar notes found (85%+ similarity)</p>';
    } else {
        let html = '<div class="list-group">';

        similarNotes.forEach(note => {
            html += `
                <label class="list-group-item">
                    <input class="form-check-input me-2 similar-note-checkbox"
                           type="checkbox"
                           value="${note.note_id}"
                           data-record="${note.record_bib}">
                    <div class="d-flex justify-content-between align-items-start">
                        <div class="flex-grow-1">
                            <strong>Record ${note.record_bib}, Note ${note.note_index}</strong>
                            <span class="badge bg-success ms-2">${note.similarity}% similar</span>
                            <br>
                            <small class="text-muted">${note.text}</small>
                        </div>
                    </div>
                </label>
            `;
        });

        html += '</div>';
        html += '<button class="btn btn-sm btn-outline-secondary mt-2" id="selectAllSimilar">Select All</button>';

        listContainer.innerHTML = html;

        // Select all button
        document.getElementById('selectAllSimilar').addEventListener('click', function() {
            document.querySelectorAll('.similar-note-checkbox').forEach(cb => {
                cb.checked = true;
            });
            updateSelectedCount();
        });

        // Update count when checkboxes change
        document.querySelectorAll('.similar-note-checkbox').forEach(cb => {
            cb.addEventListener('change', updateSelectedCount);
        });
    }

    // Show modal
    const modal = new bootstrap.Modal(document.getElementById('similarNotesModal'));
    modal.show();

    // Store note card reference for later
    document.getElementById('applyToSimilarBtn').dataset.noteCard = noteCard.dataset.noteIndex;
}

function updateSelectedCount() {
    const count = document.querySelectorAll('.similar-note-checkbox:checked').length;
    document.getElementById('selectedCount').textContent = count;
}

// Apply classification to similar notes
document.getElementById('applyToSimilarBtn').addEventListener('click', function() {
    const noteIndex = this.dataset.noteCard;
    const noteCard = document.querySelector(`.note-card[data-note-index="${noteIndex}"]`);

    // Get selected note IDs
    const selectedNotes = Array.from(
        document.querySelectorAll('.similar-note-checkbox:checked')
    ).map(cb => parseInt(cb.value));

    if (selectedNotes.length === 0) {
        showNotification('Please select at least one note', 'warning');
        return;
    }

    // Get classification from checkboxes
    const checkboxes = noteCard.querySelectorAll('.classification-checkbox:checked');
    const components = Array.from(checkboxes).map(cb => cb.value);

    if (components.length === 0 || (!components.includes('o') && !components.includes('w'))) {
        showNotification('Please select at least O or W', 'error');
        return;
    }

    components.sort();

    // Show loading
    this.disabled = true;
    this.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Applying...';

    // Apply votes
    fetch('/vote-similar', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            note_ids: selectedNotes,
            components: components
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showNotification(
                `Applied to ${data.total_notes} notes! (${data.votes_created} new, ${data.votes_updated} updated)`,
                'success'
            );

            // Close modal
            bootstrap.Modal.getInstance(document.getElementById('similarNotesModal')).hide();

            // Optionally reload to show updated counts
            setTimeout(() => location.reload(), 1500);
        } else {
            showNotification('Error: ' + data.error, 'error');
        }
    })
    .finally(() => {
        this.disabled = false;
        this.innerHTML = 'Apply Classification';
    });
});
```

### Phase 3: Installation

#### 1. Install rapidfuzz
```bash
pip install rapidfuzz
pip freeze > requirements.txt
```

#### 2. Add to requirements.txt
```
rapidfuzz>=3.0.0
```

## User Experience Flow

1. User navigates to a note with text like "This document is part of CO 384/30..."
2. User clicks "Find Similar Notes" button
3. Modal appears showing:
   - Original note text
   - List of similar notes with similarity scores
   - Checkboxes to select which notes to include
   - "Select All" button
4. User selects O, W, A checkboxes for classification
5. User reviews similar notes and selects which ones to apply to
6. User clicks "Apply Classification"
7. Vote is applied to all selected notes
8. Success notification shows count of votes applied

## Settings & Configuration

Could add admin settings for:
- Similarity threshold (default 85%)
- Maximum similar notes to show (default 100)
- Enable/disable feature per user or globally

## Performance Considerations

- **Caching**: Cache similarity calculations for frequently compared notes
- **Indexing**: Consider adding text search index if database grows large
- **Background Processing**: For very large databases, run similarity search as background job
- **Pagination**: Limit initial results, load more on demand

## Alternative Approaches

### Simpler Option: Pattern Templates
For very specific use cases, could add pattern templates:
- "CO {NUM}/{NUM}" → Matches "CO 384/30", "CO 384/31", etc.
- "Page {NUM}" → Matches "Page 1", "Page 2", etc.

Users could select from predefined patterns or create custom patterns.

## Cost/Benefit Analysis

**Development Time**: 4-6 hours
**Value**: High - significantly speeds up voting for similar notes
**Complexity**: Medium - requires fuzzy matching library
**Maintenance**: Low - library handles complexity

## Next Steps

1. Install rapidfuzz
2. Implement `utils/similarity.py`
3. Add `/find-similar-notes` and `/vote-similar` endpoints
4. Add UI button and modal to `record.html`
5. Add JavaScript handlers to `app.js`
6. Test with real data
7. Iterate on similarity threshold based on user feedback
