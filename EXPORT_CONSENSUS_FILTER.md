# Export with Consensus Filtering

## Feature Description

The export functionality now supports filtering by specific consensus types. This allows you to export only notes that have reached consensus on specific classifications.

## How It Works

### UI (Admin Export Page)

**Consensus Type Filter Section:**
- ☐ O - Object only
- ☐ W - Work only
- ☐ OW - Object/Work
- ☐ AO - Administrative/Object
- ☐ AW - Administrative/Work
- ☐ AOW - Administrative/Object/Work
- ☐ ? - Unknown

**Buttons:**
- "Select All" - Check all consensus types
- "Deselect All" - Uncheck all consensus types

**Default Behavior:**
- If NO checkboxes are selected → Export ALL consensus types
- If ANY checkboxes are selected → Export ONLY those types

### Export Logic

All filters work together with AND logic:

```
Export a note IF:
  - Consensus probability >= confidence_threshold (e.g., 70%)
  AND
  - Vote count >= min_votes (e.g., 3 votes)
  AND
  - Consensus type IN selected_types (e.g., ['aw', 'aow'])
```

### Filename Convention

Exported files include the consensus filter in the filename:

**Examples:**
- `classification_export_20260123_143022.xml` - All types
- `classification_export_AW_20260123_143022.xml` - Only AW notes
- `classification_export_AW_AOW_20260123_143022.xml` - AW and AOW notes
- `classification_export_O_W_OW_20260123_143022.xml` - Only object/work related

## Use Cases

### 1. Export Administrative Notes Only
**Filter:** Select AW, AOW, AO
**Use Case:** Send administrative notes to cataloging team

### 2. Export Content Notes Only
**Filter:** Select W, OW, AW, AOW
**Use Case:** Extract content-related notes for research analysis

### 3. Export Physical Description Notes Only
**Filter:** Select O, OW, AO, AOW
**Use Case:** Generate report of physical descriptions

### 4. Export Pure Classifications Only
**Filter:** Select O, W (uncheck combinations)
**Use Case:** Export notes with clear single-category consensus

### 5. Export Uncertain Notes
**Filter:** Select ? (Unknown)
**Use Case:** Generate list of notes needing review

### 6. Export All Administrative Combinations
**Filter:** Select AO, AW, AOW
**Use Case:** Any note that has administrative component

## Example Workflow

### Scenario: Export AW and AOW notes for administrative review

1. Navigate to Admin → Export
2. Set confidence threshold: 70% (high confidence)
3. Set minimum votes: 3 (good consensus)
4. Check: ☑ AW and ☑ AOW
5. Keep "Include statistics" checked
6. Click "Generate and Download XML"

**Result:** File `classification_export_AW_AOW_20260123_143022.xml` containing:
- Only notes with AW or AOW consensus
- With at least 70% agreement
- With at least 3 votes
- Including vote statistics in XML attributes

### Scenario: Export all work-related notes (any combination with W)

1. Navigate to Admin → Export
2. Set confidence threshold: 60% (moderate confidence)
3. Set minimum votes: 2
4. Check: ☑ W, ☑ OW, ☑ AW, ☑ AOW
5. Click "Generate and Download XML"

**Result:** File `classification_export_AW_AOW_OW_W_20260123_143022.xml` containing:
- All notes that include Work classification
- Either pure W, or combined with O/A

## Technical Implementation

### Backend Changes

**File: `utils/xml_exporter.py`**
```python
def export_to_xml(confidence_threshold=0.60, min_votes=1,
                  include_stats=True, consensus_filter=None):
    """
    consensus_filter: List of consensus types (e.g., ['aw', 'aow']) or None for all
    """
    # ... existing code ...

    # New filtering logic
    if consensus_filter is not None:
        consensus_filter_lower = [c.lower() for c in consensus_filter]
        if distribution['consensus'].lower() not in consensus_filter_lower:
            continue  # Skip this note
```

**File: `routes/admin.py`**
```python
# Get consensus filter from form checkboxes
consensus_filter = request.form.getlist('consensus_types')
if not consensus_filter:
    consensus_filter = None  # Export all types

# Add to filename
if consensus_filter:
    consensus_str = '_'.join(sorted(consensus_filter)).upper()
    filename = f'classification_export_{consensus_str}_{timestamp}.xml'
```

### Frontend Changes

**File: `templates/admin/export.html`**
- Added consensus type checkboxes with badges
- Added Select All / Deselect All buttons
- Updated documentation section

## Testing

### Test Results

**Test Query:** First 100 notes in database
```
Consensus distribution:
  A: 49 notes   (incomplete votes - flagged as needs_review)
  AW: 16 notes
  O: 26 notes
  OW: 1 note
  W: 8 notes
```

**Export with filter: ['aw', 'aow']**
```
Result: 153 AW notes exported (across entire database)
Confirmed: Only AW notes included, others filtered out
```

### Manual Testing Checklist

- [ ] No checkboxes selected → Exports all consensus types
- [ ] Select AW only → Exports only AW notes
- [ ] Select AW + AOW → Exports both AW and AOW notes
- [ ] Select All → Works same as no checkboxes (all types)
- [ ] Filename includes selected consensus types
- [ ] Export respects confidence threshold AND min votes AND consensus filter
- [ ] Deselect All → Same as no checkboxes (all types)

## Performance

No performance impact:
- Filtering happens during export loop (already iterating all notes)
- Simple string comparison: `O(1)` per note
- Export time scales with total notes, not filter complexity

## Future Enhancements

Potential additions:
- **Preset filters**: Save common filter combinations (e.g., "Administrative only")
- **Negation**: "Export everything EXCEPT ?" option
- **Statistics preview**: "This will export ~250 notes" before download
- **Multiple exports**: Export each type to separate file automatically
- **Component-based filter**: "Export all notes with A component" (AO + AW + AOW)

## Migration Notes

This is a **backwards-compatible** addition:
- Existing code passes `consensus_filter=None` → exports all types
- No database changes required
- No changes to XML format
- Old export links/scripts continue to work

## Summary

✅ **Export now supports consensus-based filtering**
✅ **Flexible selection: choose any combination of types**
✅ **Clear filename convention includes filter**
✅ **Works with existing confidence and vote filters**
✅ **No performance impact**
✅ **Backwards compatible**

This feature is particularly useful for:
- Sending different note types to different teams
- Generating type-specific reports
- Quality control on specific categories
- Analyzing classification patterns by type
