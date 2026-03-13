from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file, session
from werkzeug.utils import secure_filename
from sqlalchemy import func
from auth import admin_required
from models import db, Record, Note, Vote, User, Setting
from utils.probability import get_contentious_threshold, update_contentious_threshold, update_min_votes_for_contentious
import os
import tempfile
from datetime import datetime

admin_bp = Blueprint('admin', __name__)


@admin_bp.route('/dashboard')
@admin_required
def dashboard():
    """Admin dashboard with statistics"""

    # Basic statistics
    stats = {
        'total_records': Record.query.count(),
        'total_notes': Note.query.count(),
        'total_votes': Vote.query.count(),
        'total_users': User.query.count(),
    }

    # Calculate average votes per note
    notes_with_votes = db.session.query(
        func.count(Vote.id)
    ).join(Note).group_by(Note.id).all()

    if notes_with_votes:
        stats['avg_votes_per_note'] = sum([count for (count,) in notes_with_votes]) / len(notes_with_votes)
    else:
        stats['avg_votes_per_note'] = 0

    # Top contributors
    top_contributors = db.session.query(
        User.username,
        func.count(Vote.id).label('vote_count')
    ).join(Vote).group_by(User.id).order_by(
        func.count(Vote.id).desc()
    ).limit(10).all()

    # Classification distribution
    classification_dist = db.session.query(
        Vote.classification,
        func.count(Vote.id).label('count')
    ).group_by(Vote.classification).order_by(
        func.count(Vote.id).desc()
    ).all()

    # Recent activity (last 20 votes)
    recent_votes = db.session.query(Vote, User, Note, Record)\
        .select_from(Vote)\
        .join(User)\
        .join(Note)\
        .join(Record)\
        .order_by(Vote.voted_at.desc())\
        .limit(20).all()

    recent_activity = []
    for vote, user, note, record in recent_votes:
        recent_activity.append({
            'username': user.username,
            'classification': vote.classification,
            'record_bib': record.bib_id,
            'voted_at': vote.voted_at
        })

    return render_template('admin/dashboard.html',
                         stats=stats,
                         top_contributors=top_contributors,
                         classification_dist=classification_dist,
                         recent_activity=recent_activity)


@admin_bp.route('/upload', methods=['GET', 'POST'])
@admin_required
def upload_xml():
    """Upload and import XML file"""

    if request.method == 'POST':
        # Check if file was uploaded
        if 'xml_file' not in request.files:
            flash('No file uploaded', 'danger')
            return redirect(request.url)

        file = request.files['xml_file']

        if file.filename == '':
            flash('No file selected', 'danger')
            return redirect(request.url)

        if not file.filename.endswith('.xml'):
            flash('Only XML files are allowed', 'danger')
            return redirect(request.url)

        # Save temporarily
        temp_path = os.path.join(tempfile.gettempdir(), secure_filename(file.filename))
        try:
            file.save(temp_path)
        except Exception as e:
            flash(f'Error saving file: {str(e)}', 'danger')
            return redirect(request.url)

        # Import with optional initial votes
        create_initial_votes = request.form.get('create_votes') == 'on'
        admin_user = User.query.filter_by(username=session['username']).first()

        # Import using xml_parser utility
        from utils.xml_parser import import_xml_file

        try:
            stats = import_xml_file(
                temp_path,
                admin_user_id=admin_user.id if create_initial_votes else None
            )

            # Clean up temp file
            os.remove(temp_path)

            # Show results
            if stats['errors']:
                flash(f"Import completed with {len(stats['errors'])} errors. "
                      f"Created: {stats['records_created']} records, {stats['notes_created']} notes, "
                      f"{stats['votes_created']} votes.", 'warning')
                for error in stats['errors'][:10]:  # Show first 10 errors
                    flash(error, 'warning')
            else:
                flash(f"Successfully imported {stats['records_created']} records, "
                      f"{stats['notes_created']} notes, {stats['votes_created']} votes", 'success')

        except Exception as e:
            if os.path.exists(temp_path):
                os.remove(temp_path)
            flash(f'Import error: {str(e)}', 'danger')

        return redirect(url_for('admin.dashboard'))

    return render_template('admin/upload.html')


@admin_bp.route('/export', methods=['GET', 'POST'])
@admin_required
def export_xml():
    """Export database to XML"""

    if request.method == 'POST':
        try:
            confidence = float(request.form.get('confidence_threshold', 0.60))
            min_votes = int(request.form.get('min_votes', 1))
            include_stats = request.form.get('include_stats') == 'on'

            # Get consensus filter from form (multiple checkboxes)
            consensus_filter = request.form.getlist('consensus_types')
            # If empty list, set to None (export all)
            if not consensus_filter:
                consensus_filter = None

            # Validate confidence
            if not 0 <= confidence <= 1:
                flash('Confidence threshold must be between 0 and 1', 'danger')
                return redirect(request.url)

            # Validate min_votes
            if min_votes < 0:
                flash('Minimum votes must be at least 0', 'danger')
                return redirect(request.url)

            # Generate filename with timestamp
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

            # Add consensus filter to filename if specified
            if consensus_filter:
                consensus_str = '_'.join(sorted(consensus_filter)).upper()
                filename = f'classification_export_{consensus_str}_{timestamp}.xml'
            else:
                filename = f'classification_export_{timestamp}.xml'

            filepath = os.path.join(tempfile.gettempdir(), filename)

            # Export using xml_exporter utility
            from utils.xml_exporter import export_to_file

            export_to_file(filepath, confidence, min_votes, include_stats, consensus_filter)

            # Send file
            return send_file(
                filepath,
                as_attachment=True,
                download_name=filename,
                mimetype='application/xml'
            )

        except Exception as e:
            flash(f'Export error: {str(e)}', 'danger')
            return redirect(request.url)

    # Get current threshold and min votes for defaults
    from utils.probability import get_min_votes_for_export
    current_threshold = get_contentious_threshold()
    current_min_votes = get_min_votes_for_export()

    return render_template('admin/export.html',
                         default_threshold=current_threshold,
                         default_min_votes=current_min_votes)


@admin_bp.route('/settings', methods=['GET', 'POST'])
@admin_required
def settings():
    """Manage system settings"""

    if request.method == 'POST':
        try:
            threshold = float(request.form.get('contentious_threshold', 0.70))
            min_votes = int(request.form.get('min_votes_contentious', 3))

            if not 0 < threshold < 1:
                flash('Threshold must be between 0 and 1', 'danger')
                return redirect(request.url)

            if min_votes < 1:
                flash('Minimum votes must be at least 1', 'danger')
                return redirect(request.url)

            update_contentious_threshold(threshold)
            update_min_votes_for_contentious(min_votes)
            flash(f'Settings updated: Contentious threshold {threshold:.0%}, Minimum votes {min_votes}', 'success')

        except ValueError as e:
            flash(f'Invalid value: {str(e)}', 'danger')
        except Exception as e:
            flash(f'Error updating settings: {str(e)}', 'danger')

        return redirect(url_for('admin.settings'))

    from utils.probability import get_min_votes_for_contentious
    current_threshold = get_contentious_threshold()
    current_min_votes = get_min_votes_for_contentious()

    return render_template('admin/settings.html',
                         contentious_threshold=current_threshold,
                         min_votes_contentious=current_min_votes)


@admin_bp.route('/users')
@admin_required
def manage_users():
    """List all users with vote counts"""

    # Get all users with their vote counts
    users_data = db.session.query(
        User.id,
        User.username,
        User.is_admin,
        User.created_at,
        func.count(Vote.id).label('vote_count')
    ).outerjoin(Vote).group_by(User.id).order_by(User.username).all()

    users = []
    for user_id, username, is_admin, created_at, vote_count in users_data:
        users.append({
            'id': user_id,
            'username': username,
            'is_admin': is_admin,
            'created_at': created_at,
            'vote_count': vote_count
        })

    return render_template('admin/users.html', users=users)


@admin_bp.route('/users/<int:user_id>/edit', methods=['POST'])
@admin_required
def edit_user(user_id):
    """Edit a user's username"""

    user = User.query.get_or_404(user_id)
    new_username = request.form.get('new_username', '').strip()

    if not new_username:
        flash('Username cannot be empty', 'danger')
        return redirect(url_for('admin.manage_users'))

    if len(new_username) > 50:
        flash('Username must be 50 characters or less', 'danger')
        return redirect(url_for('admin.manage_users'))

    old_username = user.username

    # Check if new username already exists
    existing_user = User.query.filter_by(username=new_username).first()

    if existing_user and existing_user.id != user_id:
        # Combine users: transfer all votes from old user to existing user
        try:
            # Update all votes from old user to point to existing user
            Vote.query.filter_by(user_id=user_id).update({'user_id': existing_user.id})

            # Delete the old user
            db.session.delete(user)
            db.session.commit()

            flash(f'Successfully merged user "{old_username}" into "{new_username}". All votes have been transferred.', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Error merging users: {str(e)}', 'danger')
    else:
        # Simply update the username
        try:
            user.username = new_username
            db.session.commit()
            flash(f'Successfully renamed user from "{old_username}" to "{new_username}"', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating username: {str(e)}', 'danger')

    return redirect(url_for('admin.manage_users'))


@admin_bp.route('/users/<int:user_id>/reset-password', methods=['POST'])
@admin_required
def reset_user_password(user_id):
    """Reset a user's password to NULL so they can set a new one on next login"""

    user = User.query.get_or_404(user_id)
    username = user.username

    try:
        # Set password_hash to NULL
        user.password_hash = None
        db.session.commit()
        flash(f'Password reset for user "{username}". They will be prompted to set a new password on next login.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error resetting password: {str(e)}', 'danger')

    return redirect(url_for('admin.manage_users'))
