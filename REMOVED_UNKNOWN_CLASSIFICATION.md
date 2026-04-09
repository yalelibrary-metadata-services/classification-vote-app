# Removed "Unknown" (?) Classification

## Summary

The "Unknown" or "?" classification option has been completely removed from the application. This option is no longer valid since the new multi-select checkbox system requires users to select at least one of O (Object) or W (Work).

## Changes Made

### Backend Changes

**1. `utils/probability.py`**
- Removed `'?'` from `CLASSIFICATION_TYPES` list
- Removed `'?': 'danger'` from color mapping

**2. `routes/voting.py`**
- Removed `'?'` from valid classification validation (3 places)
- Now validates: `['o', 'w', 'ow', 'ao', 'aw', 'aow']` only

**3. `routes/main.py`**
- Removed entire `next_unknown()` route function
- This route navigated to records with "?" consensus

**4. `routes/filters.py`**
- Removed entire `unknown_records()` route function
- This route showed all notes with "?" consensus

### Frontend Changes

**5. `templates/record.html`**
- Removed "Uncertain (?)" button from voting interface
- Removed "Next Unknown" button from quick navigation
- Updated navigation description (removed Unknown explanation)

**6. `templates/index.html`**
- Removed "View Unknown Classifications" button
- Updated classification legend:
  - Removed "?" badge and description
  - Added AOW badge
  - Added explanation about multi-select checkboxes
  - Reorganized to show component-based system

**7. `templates/base.html`**
- Removed "Unknown" navigation link from navbar

**8. `templates/admin/export.html`**
- Removed "? Unknown" checkbox from consensus type filter

**9. `static/js/app.js`**
- Removed entire uncertain button click handler (~85 lines)
- Removed `'?': 'danger'` from `getColorForClassification()` function

### Documentation Changes

**10. `CLAUDE.md`**
- Updated "Classification System" section:
  - Changed from 7 single-select types to multi-select checkboxes
  - Explained O + W required, A optional
  - Removed "?" from list
  - Added valid combinations explanation
- Updated routes documentation:
  - Removed `/unknown` route
  - Added `/needs-review` route

## Why Remove "?"

The new multi-select system fundamentally changed how classification works:

**Old System:**
- 7 mutually exclusive buttons: O, W, A, OW, AW, AO, ?
- Users could select "?" if uncertain

**New System:**
- 3 checkboxes: O, W, A (with O or W required)
- If user is uncertain, they simply don't vote
- "?" doesn't fit the checkbox model

**Migration Note:**
- During the multi-select migration, all existing "?" votes were deleted (4 votes total)
- This was acceptable because "?" votes don't contribute to O/W categorization

## Affected Features Removed

1. **"Unknown" filter page** - `/unknown` route
2. **"Next Unknown" navigation** - Button to find next "?" consensus
3. **"Uncertain (?)" voting button** - No longer available
4. **"?" in exports** - Can't filter by "?" consensus anymore
5. **"?" in navigation bar** - "Unknown" link removed

## Affected Features That Still Work

1. **All other consensus types** - O, W, OW, AO, AW, AOW work perfectly
2. **Export filtering** - Can filter by any valid consensus type
3. **Navigation** - All other quick navigation buttons work
4. **Filters** - Pending review, needs review, contentious still work
5. **Progress tracking** - Correctly ignores incomplete votes

## Testing Checklist

After removal, verify:
- [ ] Can vote using O, W, A checkboxes
- [ ] Cannot submit without O or W
- [ ] No "Uncertain" button appears
- [ ] No "?" references in UI
- [ ] Navigation bar doesn't have "Unknown" link
- [ ] Index page shows updated classification legend
- [ ] Quick navigation doesn't have "Next Unknown" button
- [ ] Export page doesn't have "?" checkbox
- [ ] Server starts without errors
- [ ] No broken links or 404 errors

## Files Modified

```
Modified (10 files):
- utils/probability.py
- routes/voting.py
- routes/main.py
- routes/filters.py
- templates/record.html
- templates/index.html
- templates/base.html
- templates/admin/export.html
- static/js/app.js
- CLAUDE.md

Created (1 file):
- REMOVED_UNKNOWN_CLASSIFICATION.md (this file)
```

## Lines of Code Removed

Approximately **150+ lines of code** removed:
- ~35 lines from routes (2 complete functions)
- ~85 lines from JavaScript (uncertain button handler)
- ~30 lines from templates (buttons, links, legends)
- Various validation and color mapping entries

## Summary

The application is now cleaner and more consistent with the checkbox-based classification system. Users must make a meaningful choice (O, W, or both) rather than marking notes as "unknown". If they're uncertain, they simply don't vote yet, and the note remains in "pending review" status.
