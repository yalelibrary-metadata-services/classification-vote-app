# Classification Vote Web App

A Flask web application for collaborative voting on note classifications in manuscript records. Multiple users can vote on classifications, with automatic consensus calculation and contentious note detection.

## Features

### Multi-User Voting System
- **Collaborative classification**: Multiple users can vote on the same notes
- **Component-based voting**: Select O, W, and/or A checkboxes to build a classification
- **Consensus calculation**: Automatic calculation of consensus based on vote distribution
- **Vote probability**: Shows percentage agreement for each classification
- **Component breakdown**: Per-note display of O/W/A component percentages across all votes
- **Contentious detection**: Flags notes where consensus is below configurable threshold
- **Vote history**: Track who voted for which classifications
- **Vote updates**: Users can change their vote at any time

### Classification Types
Six classification types built from O, W, A components:
- **Work (W)**: Content related to the work itself
- **Object (O)**: Physical description of the manuscript
- **Object/Work (OW)**: Combined physical and content description
- **Administrative/Work (AW)**: Combined administrative and content information
- **Administrative/Object (AO)**: Combined administrative and physical information
- **Administrative/Object/Work (AOW)**: All three components

**Note:** At least one of O or W must be selected. A cannot be selected alone.

### User Features
- **Password authentication**: Secure login with username and password
- **Vote privacy**: Other users' votes hidden by default, optional to view
- **Hide voted notes**: Toggle to hide notes you've already voted on (preference saved in browser)
- **Bulk voting on identical notes**: Vote on all identical notes at once (checkbox checked by default)
- **Similar notes**: Find and bulk-vote on notes with similar text (fuzzy matching)
- **Translation**: Built-in Google Translate integration for foreign language notes
- **Progress tracking**: Visual progress meters showing your voting progress and overall completion
- **Smart navigation**: "Next Unclassified" button automatically finds notes you haven't voted on
- **Needs Review**: Flag for incomplete classifications (A selected without O or W)

### Admin Features
Login with username "Admin" (case-insensitive) to access:
- **Dashboard**: Statistics on votes, users, and classifications with recent activity
- **User Management**: Edit usernames, merge duplicate accounts, and reset passwords
- **XML Import**: Upload XML files to populate the database
- **XML Export**: Export classifications with configurable confidence threshold, minimum votes, and consensus type filter
- **Settings**: Adjust contentious threshold and minimum vote requirements

### Filtering and Navigation
- **Unclassified**: Jump to the first record with notes nobody has voted on
- **Pending Review**: Records where the current user hasn't voted
- **Contentious**: Records with low consensus agreement
- **Needs Review**: Notes where your vote is incomplete (A-only, missing O or W)
- **Identical Notes**: Indicator showing how many records share the same note text
- **Similar Notes**: Fuzzy search to find notes with similar (but not identical) text

## Setup

### 1. Install UV
If you don't have UV installed:
```bash
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Or with pip
pip install uv
```

### 2. Install Dependencies
```bash
# Create virtual environment and install packages
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
uv pip install -r requirements.txt
```

### 3. Run the Application
```bash
# The database will be initialized automatically on first run
python app.py
```

Open your browser to `http://localhost:5000`

On startup the app builds a similarity index from all notes in the database. This enables fast fuzzy search (50–200ms for 100k notes).

### 4. Migrate Existing Database (If Upgrading)
If you have an existing database and are upgrading to the password-enabled version:
```bash
python migrate_add_passwords.py
```

### 5. Import Data (Optional)
If you have an existing `data.xml` file:
```bash
python migrate_existing_data.py
```

Or use the admin interface to upload XML files after logging in.

### Port 5000 Issues (macOS)
If you encounter a "Port 5000 is in use" error on macOS, this is because AirPlay Receiver uses port 5000 by default.

**Option 1: Use a different port**
```bash
python -c "from app import app; app.run(debug=True, port=8080)"
```
Then visit `http://localhost:8080`

**Option 2: Disable AirPlay Receiver**
Go to **System Preferences → General → AirDrop & Handoff** and turn off "AirPlay Receiver"

## Usage

### For Regular Users

1. **Login**: Enter your username and password
   - New users: Your password will be saved automatically
   - Existing users: Enter your password to login
2. **Browse records**: Click "Start with Unclassified" to begin classifying
3. **Classify notes**:
   - Check the O, W, and/or A checkboxes (at least O or W required)
   - Click "Submit Classification"
   - Optionally click "Show Other Votes" to see what others voted
   - Use the translate button (🌐) for foreign language notes
4. **Bulk voting on identical notes**: The "Vote on all X identical notes" checkbox is checked by default
5. **Similar notes**: Click "Find Similar Notes" to find and bulk-vote on notes with similar text
6. **Hide voted notes**: Use the toggle at the top to hide notes you've already classified
7. **Navigate**: Use "Next Unclassified" to move to the next record you haven't fully voted on
8. **Track progress**: View your personal voting progress and overall project completion at the top of each record

### For Administrators

1. **Login** as "Admin" (or "admin", "ADMIN" — case insensitive) with your password
2. **Access admin panel**: Click "Admin" in the navigation menu
3. **View statistics**: See total votes, users, classification distribution, and recent activity
4. **Manage users**: Edit usernames, merge duplicate accounts, or reset passwords
   - Merging transfers all votes from one account to another
5. **Import XML**: Upload data.xml files to populate the database
6. **Export XML**: Download classifications with custom filters:
   - Confidence threshold (minimum consensus probability)
   - Minimum votes per note
   - Consensus type filter (select which types to include: O, W, OW, AO, AW, AOW)
7. **Configure settings**:
   - Contentious threshold (default 70%)
   - Minimum votes required for contentious detection (default 3)

### Understanding Consensus

- **Consensus**: The classification with the most votes
- **Confidence**: Percentage of votes for the consensus classification
- **Contentious**: Notes marked when consensus is below threshold with minimum votes
  - Example: With 70% threshold and 3 min votes, a note with 2 votes for "W" and 1 vote for "O" shows 67% confidence and is marked contentious

## Database Structure

The application uses SQLite with the following tables:

- **users**: User accounts (username, password_hash, is_admin)
- **records**: Manuscript records (bib_id, title, source_user_id, source_filename)
- **notes**: Individual notes within records (text, note_index)
- **votes**: User votes on notes (note_id, user_id, classification, needs_review)
- **reviews**: Approval/validation of classifications (note_id, user_id, approval)
- **settings**: Configurable system settings (contentious threshold, min votes, export filters)

Database file: `instance/classification.db`

## XML Format

### Import Format
```xml
<?xml version='1.0' encoding='utf-8'?>
<records>
  <record bib="unique_id">
    <title>Record title</title>
    <note type="w">Note content</note>
    <note type="o">Another note</note>
  </record>
</records>
```

### Export Format
```xml
<?xml version='1.0' encoding='utf-8'?>
<records>
  <record bib="unique_id">
    <title>Record title</title>
    <note type="w" consensus_probability="0.85" vote_count="12">Note content</note>
    <note type="o" consensus_probability="0.67" vote_count="9">Another note</note>
  </record>
</records>
```

Only notes meeting both the confidence threshold and minimum vote requirement are exported. Records with no qualifying notes are excluded from the export.

## Development

### Project Structure
```
classification-vote/
├── app.py                 # Application factory and initialization
├── models.py              # SQLAlchemy database models
├── auth.py                # Authentication blueprint
├── config.py              # Configuration settings
├── routes/
│   ├── main.py           # Main browsing and record routes
│   ├── voting.py         # Vote submission endpoints
│   ├── filters.py        # Filter views (contentious, pending, needs-review)
│   └── admin.py          # Admin interface routes
├── utils/
│   ├── probability.py    # Vote distribution and consensus calculation
│   ├── similarity.py     # Inverted-index fuzzy similarity search
│   ├── xml_parser.py     # XML import functionality
│   └── xml_exporter.py   # XML export functionality
├── templates/            # Jinja2 HTML templates
├── static/
│   ├── js/app.js        # Client-side voting and navigation
│   └── css/style.css    # Custom styling
└── instance/
    └── classification.db # SQLite database
```

### Adding New Features
- Routes: Add to appropriate blueprint in `routes/`
- Models: Update `models.py` and create migration
- UI: Modify templates in `templates/`
- Client logic: Update `static/js/app.js`

## Troubleshooting

### Database Issues
```bash
# Reset database (WARNING: destroys all data)
rm instance/classification.db
# Database will be recreated automatically when you run the app
python app.py
```

### Port Conflicts
```bash
# Check what's using port 5000
lsof -i :5000

# Use alternative port
python -c "from app import app; app.run(debug=True, port=8080)"
```

### Import Errors
- Ensure XML file is well-formed
- Check that `<record bib="...">` attributes are unique
- Verify note text is properly encoded (UTF-8)

## License

MIT License - see LICENSE file for details
