from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from models import db, User
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash

auth_bp = Blueprint('auth', __name__)

def login_required(f):
    """Decorator to require login for a route"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    """Decorator to require admin privileges for a route"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('auth.login'))

        user = User.query.filter_by(username=session['username']).first()
        if not user or not user.is_admin:
            flash('Admin access required.', 'danger')
            return redirect(url_for('main.index'))
        return f(*args, **kwargs)
    return decorated_function

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Login page and handler"""
    # If already logged in, redirect to index
    if 'username' in session:
        return redirect(url_for('main.index'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        if not username:
            flash('Username is required.', 'danger')
            return render_template('login.html')

        if not password:
            flash('Password is required.', 'danger')
            return render_template('login.html')

        if len(username) > 50:
            flash('Username must be 50 characters or less.', 'danger')
            return render_template('login.html')

        # Get or create user
        user = User.query.filter_by(username=username).first()

        # Auto-grant admin privileges to "Admin" username
        is_admin_username = username.lower() == 'admin'

        if not user:
            # New user - create account with hashed password
            password_hash = generate_password_hash(password)
            user = User(username=username, password_hash=password_hash, is_admin=is_admin_username)
            db.session.add(user)
            db.session.commit()
            if is_admin_username:
                flash(f'Welcome, {username}! Your account has been created with admin privileges.', 'success')
            else:
                flash(f'Welcome, {username}! Your account has been created.', 'success')
        else:
            # Existing user - validate password
            if user.password_hash is None:
                # Legacy user without password - set their password now
                user.password_hash = generate_password_hash(password)
                if is_admin_username and not user.is_admin:
                    user.is_admin = True
                db.session.commit()
                flash(f'Welcome back, {username}! Your password has been set.', 'success')
            elif check_password_hash(user.password_hash, password):
                # Password matches
                if is_admin_username and not user.is_admin:
                    user.is_admin = True
                    db.session.commit()
                    flash(f'Welcome back, {username}! Admin privileges have been granted.', 'success')
                else:
                    flash(f'Welcome back, {username}!', 'success')
            else:
                # Password doesn't match
                flash('Incorrect password.', 'danger')
                return render_template('login.html')

        # Set session
        session['username'] = username
        session['user_id'] = user.id
        session['is_admin'] = user.is_admin
        session.permanent = True

        return redirect(url_for('main.index'))

    return render_template('login.html')

@auth_bp.route('/logout')
def logout():
    """Logout handler"""
    username = session.get('username', 'User')
    session.clear()
    flash(f'Goodbye, {username}!', 'info')
    return redirect(url_for('auth.login'))
