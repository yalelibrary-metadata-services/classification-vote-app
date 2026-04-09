from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class User(db.Model):
    """User model for tracking classifiers and reviewers"""
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=True)  # Nullable for migration of existing users
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_admin = db.Column(db.Boolean, default=False)

    # Relationships
    votes = db.relationship('Vote', backref='user', lazy='select', cascade='all, delete-orphan')
    reviews = db.relationship('Review', backref='user', lazy='select', cascade='all, delete-orphan')

    def __repr__(self):
        return f'<User {self.username}>'


class Record(db.Model):
    """Record model for manuscript records"""
    __tablename__ = 'records'

    id = db.Column(db.Integer, primary_key=True)
    bib_id = db.Column(db.String(50), unique=True, nullable=False, index=True)
    title = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Import metadata (nullable, for reference only)
    source_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, index=True)
    source_filename = db.Column(db.String(255), nullable=True, index=True)

    # Relationships
    notes = db.relationship('Note', backref='record', lazy='select',
                           cascade='all, delete-orphan', order_by='Note.note_index')
    source_user = db.relationship('User', foreign_keys=[source_user_id], backref='source_records')

    def __repr__(self):
        return f'<Record {self.bib_id}>'


class Note(db.Model):
    """Note model for individual notes within records"""
    __tablename__ = 'notes'

    id = db.Column(db.Integer, primary_key=True)
    record_id = db.Column(db.Integer, db.ForeignKey('records.id'), nullable=False, index=True)
    note_index = db.Column(db.Integer, nullable=False)  # Position within record
    text = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    votes = db.relationship('Vote', backref='note', lazy='select', cascade='all, delete-orphan')
    reviews = db.relationship('Review', backref='note', lazy='select', cascade='all, delete-orphan')

    # Composite unique constraint and index
    __table_args__ = (
        db.UniqueConstraint('record_id', 'note_index', name='unique_record_note_index'),
        db.Index('idx_note_record_index', 'record_id', 'note_index'),
    )

    def __repr__(self):
        return f'<Note {self.id} for Record {self.record_id}>'


class Vote(db.Model):
    """Vote model for user classifications of notes"""
    __tablename__ = 'votes'

    id = db.Column(db.Integer, primary_key=True)
    note_id = db.Column(db.Integer, db.ForeignKey('notes.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    classification = db.Column(db.String(3), nullable=False)  # o, w, ow, ao, aw, aow, ?
    needs_review = db.Column(db.Boolean, default=False)  # True if vote is incomplete (A only, no O/W)
    voted_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Composite unique constraint (one vote per user per note)
    __table_args__ = (
        db.UniqueConstraint('note_id', 'user_id', name='unique_user_note_vote'),
        db.Index('idx_vote_note_user', 'note_id', 'user_id'),
    )

    def __repr__(self):
        return f'<Vote {self.classification} by User {self.user_id} on Note {self.note_id}>'


class Review(db.Model):
    """Review model for approval status of note classifications"""
    __tablename__ = 'reviews'

    id = db.Column(db.Integer, primary_key=True)
    note_id = db.Column(db.Integer, db.ForeignKey('notes.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    approval = db.Column(db.String(1), nullable=False)  # y, n, ?
    reviewed_at = db.Column(db.DateTime, default=datetime.utcnow)


    # Composite unique constraint (one review per user per note)
    __table_args__ = (
        db.UniqueConstraint('note_id', 'user_id', name='unique_user_note_review'),
        db.Index('idx_review_note_user', 'note_id', 'user_id'),
    )

    def __repr__(self):
        return f'<Review {self.approval} by User {self.user_id} on Note {self.note_id}>'


class Setting(db.Model):
    """Setting model for configurable system settings"""
    __tablename__ = 'settings'

    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(50), unique=True, nullable=False, index=True)
    value = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<Setting {self.key}={self.value}>'
