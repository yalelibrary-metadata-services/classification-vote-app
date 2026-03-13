import xml.etree.ElementTree as ET
from xml.dom import minidom
from models import Record, Note
from utils.probability import calculate_vote_distribution


def export_to_xml(confidence_threshold=0.60, min_votes=1, include_stats=True, consensus_filter=None):
    """
    Export database to XML with consensus classifications.

    Args:
        confidence_threshold: Only include notes with probability >= threshold
        min_votes: Only include notes with at least this many votes
        include_stats: Add vote_count and consensus_probability attributes
        consensus_filter: List of consensus types to include (e.g., ['aw', 'aow']), None = all

    Returns:
        XML string (bytes)
    """
    root = ET.Element('records')

    records = Record.query.order_by(Record.bib_id).all()

    for record in records:
        # Notes
        notes = Note.query.filter_by(record_id=record.id)\
                          .order_by(Note.note_index).all()

        # Collect notes that match criteria
        matching_notes = []
        for note in notes:
            distribution = calculate_vote_distribution(note.id)

            # Check if note meets all criteria
            if not distribution['consensus']:
                continue

            # Check confidence threshold and minimum votes
            if distribution['consensus_probability'] < confidence_threshold:
                continue

            if distribution['total'] < min_votes:
                continue

            # Check consensus filter if provided
            if consensus_filter is not None:
                # Normalize consensus_filter to lowercase for comparison
                consensus_filter_lower = [c.lower() for c in consensus_filter]
                if distribution['consensus'].lower() not in consensus_filter_lower:
                    continue

            matching_notes.append((note, distribution))

        # Only create record element if it has matching notes
        if matching_notes:
            record_elem = ET.SubElement(root, 'record')
            record_elem.set('bib', record.bib_id)

            # Title
            title_elem = ET.SubElement(record_elem, 'title')
            title_elem.text = record.title

            # Add matching notes
            for note, distribution in matching_notes:
                note_elem = ET.SubElement(record_elem, 'note')
                note_elem.text = note.text
                note_elem.set('type', distribution['consensus'])

                if include_stats:
                    note_elem.set('consensus_probability',
                                 f"{distribution['consensus_probability']:.2f}")
                    note_elem.set('vote_count', str(distribution['total']))

    # Pretty print XML
    xml_string = ET.tostring(root, encoding='utf-8')
    dom = minidom.parseString(xml_string)
    pretty_xml = dom.toprettyxml(indent='  ', encoding='utf-8')

    return pretty_xml


def export_to_file(filepath, confidence_threshold=0.60, min_votes=1, include_stats=True, consensus_filter=None):
    """
    Export to XML file.

    Args:
        filepath: Path to save XML file
        confidence_threshold: Only include notes with probability >= threshold
        min_votes: Only include notes with at least this many votes
        include_stats: Add vote_count and consensus_probability attributes
        consensus_filter: List of consensus types to include (e.g., ['aw', 'aow']), None = all

    Returns:
        filepath
    """
    xml_content = export_to_xml(confidence_threshold, min_votes, include_stats, consensus_filter)

    with open(filepath, 'wb') as f:
        f.write(xml_content)

    return filepath
