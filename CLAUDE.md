# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Setup
```bash
# Create virtual environment
uv venv
source .venv/bin/activate

# Install dependencies
uv pip install -r requirements.txt

# Database is initialized automatically on first run
python app.py
```

### Running the Application
```bash
# Start development server (default port 5000)
source .venv/bin/activate
python app.py

# If port 5000 is in use (common on macOS due to AirPlay Receiver):
python -c "from app import app; app.run(debug=True, port=8080)"

# App runs on http://localhost:5000 or http://localhost:8080
```

### Database Operations
```bash
# Reset database (WARNING: destroys all data)
rm instance/classification.db
# Database recreates automatically on next run

# Migrate existing database to add password support
python migrate_add_passwords.py

# Import existing XML data
python migrate_existing_data.py
```

## Architecture Overview

This is a Flask web application for collaborative multi-user voting on note classifications in manuscript records. The application uses a modular Blueprint-based architecture with SQLite database backend.

### System Architecture

**Application Factory Pattern:**
- `app.py` - Creates and configures the Flask application
- Registers blueprints for modular route organization
- Initializes SQLAlchemy database connection
- Configures session management
- **Builds similarity index on startup** from all notes in the database (streams in batches, reports timing/stats)

**Database Layer (SQLAlchemy ORM):**
- `models.py` - Database models and relationships
  - `User` - User accounts with password_hash and admin flag
  - `Record` - Manuscript records with bib_id, source_user_id, source_filename
  - `Note` - Individual notes within records
  - `Vote` - User votes on note classifications; `needs_review=True` for A-only votes missing O/W
  - `Review` - Approval/validation of classifications (approval: y, n, ?)
  - `Setting` - Configurable system settings
- SQLite database: `instance/classification.db`
- One vote per user per note (unique constraint)
- Cascading deletes for data integrity

**Authentication System:**
- `auth.py` - Password-based authentication
- Passwords stored as secure hashes using werkzeug.security
- New users: password set on account creation
- Existing users: password validated on login
- Legacy users: can set password on first login after migration
- Session-based with 7-day persistence
- Auto-grants admin to username "Admin" (case-insensitive)
- Decorators: `@login_required`, `@admin_required`

**Route Blueprints:**

1. **`routes/main.py`** - Record browsing and navigation
   - `/` - Index page with statistics dashboard (total records/notes/votes, classification distribution, record list)
   - `/record/<bib_id>` - Record detail with voting interface
   - `/start-unclassified` - Jump to first record with unvoted notes
   - `/next-unclassified/<bib>` - Navigate to next record with unvoted notes (wraps around)
   - `/next-pending-review/<bib>` - Navigate to next record with notes unvoted by current user
   - `/next-with-other-votes/<bib>` - Navigate to next record where others voted but current user hasn't
   - `/next-my-vote/<bib>/<classification>` - Navigate to next record where user voted a specific classification

2. **`routes/voting.py`** - Vote submission endpoints
   - `POST /vote` - Submit or update single note vote
     - Accepts `components` array (O/W/A) or direct `classification`
     - Validates at least one of O or W is selected
     - Sets `needs_review=False` on successful vote
     - Returns vote distribution, consensus, and voter data
   - `POST /vote-identical` - Bulk vote on all notes with identical text
   - `POST /find-similar-notes` - Find notes with similar text via inverted index fuzzy search
     - Configurable similarity threshold (default 85%)
     - Excludes notes user has already voted on
     - Returns up to 100 results sorted by similarity
   - `POST /vote-similar` - Bulk vote on user-selected similar notes

3. **`routes/filters.py`** - Filtered views
   - `/pending-review` - Records with notes the current user hasn't voted on (capped at 50 records for performance; shows total count separately)
   - `/needs-review` - Notes where current user's vote is marked `needs_review=True` (A-only, missing O or W)
   - `/contentious` - Records with notes below consensus threshold

4. **`routes/admin.py`** - Admin interface (requires `@admin_required`)
   - `/admin/dashboard` - Statistics, top contributors, classification distribution, recent activity (last 20 votes)
   - `/admin/users` - User management list with vote counts
   - `/admin/users/<id>/edit` - Edit username or merge with existing user (transfers all votes)
   - `/admin/users/<id>/reset-password` - Reset user password (sets password_hash to NULL)
   - `/admin/upload` - XML import interface
   - `/admin/export` - XML export with confidence filter, minimum votes, and consensus type filter
   - `/admin/settings` - Configure contentious threshold and min votes

**Business Logic:**

- `utils/probability.py` - Core voting logic
  - `calculate_vote_distribution(note_id)` - Computes consensus from votes
  - `get_component_breakdown(note_id)` - Count O/W/A component votes with percentages
  - `get_user_vote_for_note(user_id, note_id)` - Retrieves user's vote
  - `count_identical_notes(note_text)` - Finds duplicate notes
  - `get_identical_note_ids(note_text)` - Returns IDs of matching notes
  - `get_contentious_threshold()`, `get_min_votes_for_contentious()` - Cached settings accessors
  - `get_min_votes_for_export()` - Export settings accessor
  - Consensus: highest vote count, ties broken by priority order (w, o, ow, aw, ao, aow)
  - Contentious: consensus probability < threshold AND total_votes >= min_votes

- `utils/similarity.py` - Fast fuzzy similarity search
  - `SimilarityIndex` class with inverted index (token-based pre-filtering)
  - `find_similar(text, threshold, limit, exclude_user_id)` - 50–200ms for 100k notes
  - Uses `rapidfuzz.fuzz.token_sort_ratio()` for matching
  - `rebuild_similarity_index()` - Streams notes in batches, returns timing stats
  - `add_note_to_index()` - Incremental update called when new notes are imported

- `utils/xml_parser.py` - XML import functionality
  - Parses XML records and notes into database
  - Optionally creates initial votes from existing `type` attributes
  - Idempotent: skips duplicate records
  - `clear_database()` - Deletes all votes/reviews/notes/records, preserves users and settings

- `utils/xml_exporter.py` - XML export functionality
  - Exports records with consensus classifications
  - Filters by confidence threshold AND minimum votes
  - `consensus_filter` list to include only specific types (e.g., `['aw', 'aow']`)
  - Optional vote statistics as attributes
  - Excludes records with no qualifying notes

**Frontend:**
- `templates/` - Jinja2 templates with Bootstrap 5
  - `base.html` - Base template with navigation; shows needs_review_count in nav
  - `index.html` - Landing page with statistics dashboard (cards for totals, classification distribution table, record list)
  - `record.html` - Main voting interface with:
    - Two progress bars (user's voting progress, overall completion)
    - Per-note multiselect checkboxes (O, W, A) with Submit button (disabled until O or W checked)
    - "Hide notes I've voted on" toggle (persisted in localStorage)
    - Component breakdown display (O/W/A percentages across all votes)
    - "Find Similar Notes" button → modal with fuzzy search results and bulk-vote
    - Identical notes checkbox for bulk voting (checked by default)
    - Show/hide other votes toggle
  - `login.html` - Login page with username and password fields
  - `pending_review.html` - Unvoted records (capped at 50, shows total count)
  - `needs_review.html` - User's incomplete votes (A-only, can complete)
  - `contentious.html` - Records with contentious notes
  - `admin/` - Admin interface templates (dashboard, users, export, upload, settings)
- `static/js/app.js` - Client-side JavaScript
  - Component-based vote submission (O/W/A checkboxes)
  - Validates at least O or W before enabling Submit
  - Dynamic UI updates for vote distributions and component breakdowns
  - Vote visibility toggle (hidden by default)
  - "Hide voted notes" toggle with localStorage persistence and auto-hide after voting
  - Bulk voting for identical notes (checkbox state preserved)
  - Similar notes modal: search, display with scores, select-and-bulk-vote
  - Keyboard navigation: left/right arrow keys for prev/next record
  - Toast notification system (auto-dismiss after 3 seconds)
- `static/css/style.css` - Custom styling

### Classification System

The app uses multiselect checkboxes where users check O, W, and/or A components:
- **O** (Object) - Physical description of the manuscript
- **W** (Work) - Content related to the work itself
- **A** (Administrative) - Cataloging or processing information (optional)

Valid combinations (stored as consensus):
- **O** - Object only
- **W** - Work only
- **OW** - Object/Work (both O and W selected)
- **AO** - Administrative/Object (A and O selected)
- **AW** - Administrative/Work (A and W selected)
- **AOW** - Administrative/Object/Work (all three selected)

**Note:** At least one of O or W must be selected. A cannot be selected alone.

### Multi-User Voting Flow

1. **User logs in** with username and password
2. **Navigates to record** with notes needing classification (typically using "Next Unclassified" button)
3. **Submits vote** by checking O/W/A checkboxes and clicking "Submit Classification"
4. **AJAX request** sent to `/vote` endpoint with:
   - `bib_id` - Record identifier
   - `note_index` - Note position within record
   - `components` - Array of selected components (e.g., `["O", "W"]`)
5. **Backend processing**:
   - Validates at least O or W is selected
   - Creates or updates vote in database
   - Sets `needs_review=False`
   - Calculates new vote distribution and component breakdown
   - Determines consensus (highest vote count, priority tie-break)
   - Checks if contentious (< threshold with >= min votes)
   - Retrieves all voters for the note
6. **JSON response** returned with:
   - Vote distribution (counts and probabilities)
   - Component breakdown (O/W/A percentages)
   - Consensus classification and confidence
   - Contentious flag
   - Voter data (grouped by classification)
7. **Frontend updates**:
   - Vote distribution and component breakdown display
   - "Who Voted?" section
   - Button highlighting for user's vote
   - Auto-hides voted note card if "Hide voted notes" toggle is active
   - Success notification

### Bulk Voting for Identical Notes

1. **Checkbox is checked by default** for notes with identical matches
2. **User submits vote** by selecting O/W/A and clicking "Submit Classification"
3. **AJAX request** sent to `/vote-identical` endpoint with:
   - `note_text` - Full text of the note
   - `classification` - Selected classification type
4. **Backend processing**:
   - Finds all notes with matching text
   - Creates or updates vote for each note
   - Commits all changes in single transaction
5. **JSON response** with:
   - Total notes affected
   - New votes created
   - Existing votes updated
6. **Notification** shows bulk operation summary

### Similar Notes Feature

1. **User clicks "Find Similar Notes"** on a note
2. **AJAX request** to `/find-similar-notes` with the note text
3. **Backend** uses pre-built `SimilarityIndex` to find fuzzy matches (50–200ms)
   - Token-based pre-filtering via inverted index
   - `rapidfuzz.fuzz.token_sort_ratio()` for scoring
   - Default threshold: 85%; returns up to 100 results
   - Excludes notes the current user has already voted on
4. **Modal displays** similar notes with similarity scores and checkboxes
5. **User selects** notes and clicks "Apply Vote" to bulk-vote all selected notes
6. **AJAX request** to `/vote-similar` applies the classification to all selected note IDs

### Consensus Calculation Algorithm

```python
# Count votes per classification
vote_counts = {'w': 3, 'o': 2, 'ao': 1}  # Example
total_votes = 6

# Calculate probabilities
probabilities = {
    'w': 3/6 = 0.50,   # 50%
    'o': 2/6 = 0.33,   # 33%
    'ao': 1/6 = 0.17   # 17%
}

# Determine consensus (highest count, priority tie-break: w > o > ow > aw > ao > aow)
consensus = 'w'
consensus_probability = 0.50

# Check if contentious
threshold = 0.70   # 70% from settings
min_votes = 3      # From settings
is_contentious = (total_votes >= 3 and 0.50 < 0.70)  # True
```

### Key Features

**Component Breakdown:**
- Each note shows O/W/A component percentages across all votes
- Separate from the consensus display — gives finer-grained view of voter agreement

**Vote Privacy:**
- Other users' votes hidden by default
- "Show Other Votes" button toggles visibility
- Prevents vote bias before user makes decision

**Hide Voted Notes:**
- Toggle at top of record page hides notes the user has already voted on
- Preference saved in localStorage
- After submitting a vote, card auto-hides if toggle is active
- Alert shows count of hidden notes and "Show all notes" link

**Identical Notes Detection:**
- Badge shows "X identical" count
- Checkbox allows bulk voting on all identical notes
- Checkbox is checked by default and state is preserved after voting

**Similar Notes Detection:**
- Inverted index built on startup for fast fuzzy search
- Token stopword filtering improves match quality
- Scales to 100k+ notes with sub-200ms response times

**Translation Integration:**
- Translate button (🌐) next to each note
- Opens Google Translate in new tab
- Auto-detects source language, pre-fills note text via URL encoding

**Contentious Detection:**
- Configurable threshold (default 70%)
- Configurable minimum votes (default 3)
- Visual badge on contentious notes
- Dedicated filter page for contentious records

**Needs Review:**
- Votes with A selected but no O or W are marked `needs_review=True`
- Dedicated filter page lists the user's incomplete votes
- Badge count in navigation

**Admin Auto-Grant:**
- Username "Admin" (case-insensitive) automatically gets `is_admin=True`
- Applied to both new and existing users

**Progress Tracking:**
- **Your voting progress**: Percentage of notes you've voted on (excludes needs_review votes)
- **Overall completion progress**: Percentage of notes with at least one vote
- Real-time updates as votes are submitted

**Pending Review Pagination:**
- Capped at 50 records for performance on large datasets
- Total count displayed separately; banner shown when results are truncated

**User Management (Admin):**
- **Edit usernames**: Rename user accounts
- **Merge users**: Transfer all votes from one account to another
- **Reset password**: Sets password_hash to NULL, forces set-password on next login

**Statistics Dashboard (Index):**
- Total records, notes, votes, average votes per note
- Classification distribution across all notes
- Record list with note counts

### Database Schema

```sql
-- Users table
CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    password_hash VARCHAR(255),
    is_admin BOOLEAN DEFAULT FALSE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Records table
CREATE TABLE records (
    id INTEGER PRIMARY KEY,
    bib_id VARCHAR(50) UNIQUE NOT NULL,
    title TEXT NOT NULL,
    source_user_id INTEGER REFERENCES users(id),
    source_filename VARCHAR(255),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Notes table
CREATE TABLE notes (
    id INTEGER PRIMARY KEY,
    record_id INTEGER NOT NULL REFERENCES records(id),
    note_index INTEGER NOT NULL,
    text TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(record_id, note_index)
);

-- Votes table
CREATE TABLE votes (
    id INTEGER PRIMARY KEY,
    note_id INTEGER NOT NULL REFERENCES notes(id),
    user_id INTEGER NOT NULL REFERENCES users(id),
    classification VARCHAR(3) NOT NULL,
    needs_review BOOLEAN DEFAULT FALSE,
    voted_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(note_id, user_id)
);

-- Reviews table
CREATE TABLE reviews (
    id INTEGER PRIMARY KEY,
    note_id INTEGER NOT NULL REFERENCES notes(id),
    user_id INTEGER NOT NULL REFERENCES users(id),
    approval VARCHAR(1) NOT NULL,  -- 'y', 'n', '?'
    reviewed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(note_id, user_id)
);

-- Settings table
CREATE TABLE settings (
    id INTEGER PRIMARY KEY,
    key VARCHAR(50) UNIQUE NOT NULL,
    value VARCHAR(255) NOT NULL,
    description TEXT,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### Key Files Reference

**Core Application:**
- `app.py` - Application factory; builds similarity index on startup
- `models.py` - Database models (User, Record, Note, Vote, Review, Setting)
- `auth.py` - Authentication system
- `config.py` - Configuration settings

**Route Blueprints:**
- `routes/main.py` - Main routes (index with stats, record detail, navigation)
- `routes/voting.py` - Vote endpoints (single, identical, similar)
- `routes/filters.py` - Filter views (pending, needs-review, contentious)
- `routes/admin.py` - Admin interface

**Utilities:**
- `utils/probability.py` - Vote calculations, consensus, component breakdown
- `utils/similarity.py` - Inverted index fuzzy search (SimilarityIndex class)
- `utils/xml_parser.py` - XML import
- `utils/xml_exporter.py` - XML export with consensus type filter

**Frontend:**
- `templates/record.html` - Main voting UI (multiselect checkboxes, hide-voted toggle, similar notes modal)
- `static/js/app.js` - Client-side logic (component voting, similar notes, hide voted, toast notifications)
- `static/css/style.css` - Custom styling

**Data:**
- `instance/classification.db` - SQLite database
- `data.xml` - XML import/export format

### Common Development Tasks

**Adding a new classification type:**
1. Update validation in `routes/voting.py`
2. Add color mapping in `utils/probability.py`
3. Update template in `templates/record.html` (checkboxes section)
4. Update JavaScript in `static/js/app.js` (color function)

**Adding a new filter view:**
1. Create route in `routes/filters.py`
2. Add navigation link in `templates/base.html`
3. Create template in `templates/`
4. Use `calculate_vote_distribution()` for consensus data

**Modifying consensus algorithm:**
1. Edit `calculate_vote_distribution()` in `utils/probability.py`
2. Rebuild and verify with existing data
3. Consider migration for existing data

**Adding admin features:**
1. Create route in `routes/admin.py` with `@admin_required`
2. Add link to `templates/admin/dashboard.html`
3. Create template in `templates/admin/`

**Modifying the similarity index:**
1. Edit `utils/similarity.py`
2. Index is rebuilt on each app startup — no manual rebuild needed for schema changes
3. `add_note_to_index()` is called incrementally when notes are imported

### Performance Considerations

**Database Queries:**
- Use `joinedload()` for eager loading votes
- Avoid N+1 queries in record lists
- Index on foreign keys (note_id, user_id)

**Similarity Search:**
- Inverted index pre-filters candidate notes (token overlap)
- Stopword filtering improves signal-to-noise ratio
- Scales to 100k+ notes with 50–200ms response times
- Index lives in memory; rebuilt on every startup

**Pagination:**
- Pending review capped at 50 records to avoid slow loads
- Total count computed separately for accurate display

### Common Issues

**Port 5000 Conflicts (macOS):**
- AirPlay Receiver service uses port 5000
- Solution: `python -c "from app import app; app.run(debug=True, port=8080)"`
- Alternative: Disable AirPlay Receiver in System Preferences

**Database Locked Errors:**
- SQLite WAL mode is enabled automatically on startup
- For high-concurrency workloads, consider PostgreSQL

**Vote Display Not Updating:**
- Check browser console for JavaScript errors
- Verify voters data included in JSON response
- Ensure `updateVotersDisplay()` called after vote

**Import Failures:**
- Verify XML is well-formed UTF-8
- Check for duplicate bib_id attributes
- Ensure special characters are properly encoded

### Testing

**Manual Testing Checklist:**
1. Login as regular user and admin with passwords
2. Create new user account (password auto-saved)
3. Vote on notes using O/W/A checkboxes, verify distribution updates
4. Try submitting A-only (should be blocked — button disabled)
5. Change vote, verify update works
6. Bulk vote on identical notes (checkbox should stay checked)
7. Use "Find Similar Notes" modal and bulk-vote from it
8. Toggle "Hide voted notes" and verify notes hide after voting
9. Verify progress meters update after voting
10. Check contentious detection with different thresholds
11. Check "Needs Review" filter shows A-only votes
12. Import XML file
13. Export with different confidence thresholds, minimum votes, and consensus filters
14. Test translation button
15. Use "Next Unclassified" navigation
16. Test user management (rename, merge users, reset password)
17. Check all filter views (pending, contentious, needs-review)
18. Verify index page statistics dashboard

**Database Testing:**
```python
# Test vote creation
from app import app, db
from models import User, Note, Vote

with app.app_context():
    user = User.query.first()
    note = Note.query.first()
    vote = Vote(note_id=note.id, user_id=user.id, classification='w')
    db.session.add(vote)
    db.session.commit()
```

### Security Considerations

**Authentication:**
- Passwords stored as secure hashes (pbkdf2:sha256)
- Passwords never stored in plain text
- Legacy users set password on next login after migration
- Suitable for team environments with moderate security needs

**Admin Access:**
- Auto-grant based on username "Admin" (case-insensitive)
- Anyone can create admin account by using "Admin" username
- Fine for internal tools, not for public deployment

**Input Validation:**
- Classification types validated server-side
- At least O or W required (enforced client and server side)
- Username length limited to 50 characters
- Note text properly escaped in templates

**SQL Injection:**
- Protected by SQLAlchemy ORM

### Future Enhancements

**Potential Features:**
- Email notifications for contentious notes
- Comment system for discussing classifications
- Vote change history/audit log
- Export to CSV for analysis
- REST API for external integrations
- PostgreSQL support for better concurrency
- Real-time updates with WebSockets
- Mobile-responsive improvements

**Performance Improvements:**
- Redis caching layer for vote distributions
- Background job queue for bulk operations and index rebuilds
- Frontend pagination for large record sets

### Migration Notes

**From XML-based single-user system:**
1. Old system stored classifications directly in XML
2. New system uses database with voting
3. Migration script: `migrate_existing_data.py`
4. Preserves existing classifications as "Admin" votes
5. XML import/export maintains compatibility

**Adding password support to existing database:**
1. Run migration: `python migrate_add_passwords.py`
2. Adds `password_hash` column to users table
3. Existing users set password on next login
4. Safe to run multiple times (checks if column exists)
