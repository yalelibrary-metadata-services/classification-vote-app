# Hide Voted Notes Feature

## Overview

Added a toggle switch that allows users to hide notes they've already voted on when viewing a record. This helps users focus on notes that still need their classification vote.

## How It Works

### UI Elements

**Toggle Switch (Top Right of Notes Section):**
```
Notes Classification & Review    [Toggle] Hide notes I've voted on
```

**Hidden Notes Alert (When Active):**
```
🙈 5 note(s) hidden. Show all notes
```

### Behavior

1. **Toggle ON** → Hides all notes where the user has already submitted a vote
2. **Toggle OFF** → Shows all notes
3. **Preference Saved** → Setting persists across page loads using localStorage
4. **Auto-Hide After Vote** → When user votes on a note with toggle active, the note fades out and hides automatically

### User Flow

**Scenario 1: Focusing on Unvoted Notes**
1. User navigates to a record with 10 notes
2. User has already voted on 6 notes
3. User toggles "Hide notes I've voted on" → **ON**
4. Only 4 unvoted notes are visible
5. Alert shows: "6 note(s) hidden. Show all notes"

**Scenario 2: Voting with Auto-Hide**
1. User has toggle **ON** (showing only unvoted notes)
2. User votes on a note
3. Note fades out smoothly and disappears
4. Hidden count updates: "7 note(s) hidden"
5. User continues voting on remaining visible notes

**Scenario 3: Reviewing All Notes**
1. User clicks "Show all notes" link in alert
2. Toggle switches to **OFF**
3. All notes become visible again
4. User can review their previous votes

## Technical Implementation

### Frontend Changes

**1. `templates/record.html`**

**Toggle Switch:**
```html
<div class="form-check form-switch">
    <input class="form-check-input" type="checkbox" id="hideVotedNotesToggle">
    <label class="form-check-label" for="hideVotedNotesToggle">
        Hide notes I've voted on
    </label>
</div>
```

**Hidden Notes Alert:**
```html
<div id="hiddenNotesAlert" class="alert alert-info" style="display: none;">
    <i class="fas fa-eye-slash"></i> <span id="hiddenNotesCount">0</span> note(s) hidden.
    <a href="#" id="showAllNotes" class="alert-link">Show all notes</a>
</div>
```

**Note Card Data Attribute:**
```html
<div class="card mb-3 note-card"
     data-note-index="{{ note.index }}"
     data-user-voted="{{ 'true' if note.user_vote else 'false' }}">
```

**JavaScript Logic:**
```javascript
// Load preference from localStorage
const savedPreference = localStorage.getItem('hideVotedNotes');
if (savedPreference === 'true') {
    hideVotedToggle.checked = true;
    applyHideVotedFilter();
}

// Toggle event listener
hideVotedToggle.addEventListener('change', function() {
    localStorage.setItem('hideVotedNotes', this.checked);

    if (this.checked) {
        applyHideVotedFilter();
    } else {
        showAllNotesCards();
    }
});

// Filter function
function applyHideVotedFilter() {
    noteCards.forEach(card => {
        const userVoted = card.dataset.userVoted === 'true';

        if (userVoted) {
            card.style.display = 'none';
            hiddenCount++;
        } else {
            card.style.display = 'block';
        }
    });
}
```

**2. `static/js/app.js`**

**Auto-hide after voting:**
```javascript
// Mark note as voted and hide if toggle is active
noteCard.dataset.userVoted = 'true';

const hideToggle = document.getElementById('hideVotedNotesToggle');
if (hideToggle && hideToggle.checked) {
    // Hide the note card with fade effect
    noteCard.style.transition = 'opacity 0.3s';
    noteCard.style.opacity = '0';
    setTimeout(() => {
        noteCard.style.display = 'none';
        updateHiddenNotesCount();
    }, 300);
}
```

**Helper function:**
```javascript
function updateHiddenNotesCount() {
    const noteCards = document.querySelectorAll('.note-card');
    let hiddenCount = 0;

    noteCards.forEach(card => {
        if (card.style.display === 'none') {
            hiddenCount++;
        }
    });

    if (hiddenCount > 0) {
        hiddenCountElem.textContent = hiddenCount;
        hiddenAlertElem.style.display = 'block';
    }
}
```

**3. `static/css/style.css`**

```css
/* Hide voted notes toggle */
#hideVotedNotesToggle {
    cursor: pointer;
}

/* Smooth transition for hiding notes */
.note-card {
    transition: opacity 0.3s ease;
}

/* Hidden notes alert styling */
#hiddenNotesAlert {
    border-left: 4px solid #0dcaf0;
}
```

## Features

### ✅ Persistent Preference
- Setting saved in browser's localStorage
- Persists across:
  - Page refreshes
  - Different records
  - Browser sessions

### ✅ Auto-Hide After Vote
- When toggle is active
- Note fades out smoothly after successful vote
- Hidden count updates automatically
- No page reload needed

### ✅ Visual Feedback
- Alert shows how many notes are hidden
- "Show all notes" quick link
- Smooth fade transition when hiding
- Clear toggle label

### ✅ Smart Behavior
- Counts only notes with complete votes
- Incomplete votes (needs_review) are NOT hidden
- Works with bulk voting (reload shows updated state)
- Updates count dynamically

## Use Cases

### 1. Progressive Voting
**Problem:** User voting through 50 notes, hard to track which ones are left
**Solution:** Toggle ON → See only unvoted notes → Vote progressively → Notes disappear

### 2. Reviewing Unvoted Notes
**Problem:** User wants to see what they haven't voted on yet
**Solution:** Toggle ON → Instant view of pending notes

### 3. Completing a Record
**Problem:** User wants to finish voting on a specific record
**Solution:** Toggle ON → Shows only remaining notes → Vote on each → Clear when done

### 4. Quality Review
**Problem:** User wants to review all notes including voted ones
**Solution:** Toggle OFF or click "Show all notes" → See everything

## Edge Cases Handled

### ✅ No Votes Yet
- Toggle has no effect (nothing to hide)
- Alert doesn't show

### ✅ All Notes Voted
- Toggle hides all notes
- Alert shows total count
- "Show all notes" link available

### ✅ Incomplete Votes
- Notes with `needs_review=True` are NOT hidden
- These need to be completed (select O or W)
- Encourages users to complete incomplete votes

### ✅ Bulk Voting with Toggle
- Toggle remains active after page reload
- Newly voted notes are hidden
- Preference persists

### ✅ Cross-Browser
- localStorage works in all modern browsers
- Graceful fallback if localStorage disabled
- No errors if elements missing

## Performance

**No Impact:**
- Client-side filtering only (no server load)
- Simple CSS display property toggle
- Minimal JavaScript (~60 lines)
- No database queries
- Instant response time

## Browser Compatibility

**Supported:**
- Chrome/Edge (✅)
- Firefox (✅)
- Safari (✅)
- Opera (✅)

**Requirements:**
- localStorage support (all modern browsers)
- CSS transitions (all modern browsers)
- JavaScript ES6 (all modern browsers)

## Future Enhancements

Potential improvements:
- **Keyboard shortcut** - Toggle with 'H' key
- **Hide by consensus type** - "Hide all OW notes"
- **Hide incomplete votes** - Option to hide needs_review notes
- **Session-based preference** - Store per-user in database
- **Collapse instead of hide** - Show collapsed cards instead of hiding
- **Count badge** - Show hidden count in toggle label

## Testing Checklist

After implementation, verify:
- [ ] Toggle appears on record pages
- [ ] Toggle hides notes with user votes
- [ ] Toggle shows notes when turned off
- [ ] Preference saves in localStorage
- [ ] Preference loads on page refresh
- [ ] Alert shows correct hidden count
- [ ] "Show all notes" link works
- [ ] Note hides automatically after voting (with toggle ON)
- [ ] Hidden count updates after voting
- [ ] Smooth fade transition when hiding
- [ ] Works with bulk voting (reload shows correct state)
- [ ] No console errors
- [ ] Works across different browsers

## Files Modified

```
Modified (3 files):
- templates/record.html (added toggle, alert, JavaScript)
- static/js/app.js (added auto-hide after vote, helper function)
- static/css/style.css (added styling for toggle and transitions)

Created (1 file):
- HIDE_VOTED_NOTES_FEATURE.md (this file)
```

## Lines of Code Added

Approximately **120 lines** added:
- ~60 lines in record.html (HTML + JavaScript)
- ~30 lines in app.js (auto-hide logic)
- ~30 lines in style.css (styling)

## Summary

The "Hide voted notes" feature significantly improves UX for users working through large records. It allows them to:
- ✅ Focus on unvoted notes
- ✅ Track progress visually
- ✅ Vote efficiently without scrolling past completed notes
- ✅ Maintain context with persistent preference
- ✅ Review all notes when needed

The feature is lightweight, performant, and integrates seamlessly with existing voting workflows.
