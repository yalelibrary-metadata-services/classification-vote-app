from flask import Flask
from flask_migrate import Migrate
from models import db
from config import Config
import os

def create_app(config_class=Config):
    """Flask application factory"""
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Ensure instance folder exists
    os.makedirs(os.path.join(app.instance_path), exist_ok=True)

    # Initialize extensions
    db.init_app(app)
    migrate = Migrate(app, db)

    # Enable SQLite WAL mode for better concurrency and initialize database
    with app.app_context():
        if app.config['SQLALCHEMY_DATABASE_URI'].startswith('sqlite'):
            with db.engine.connect() as conn:
                conn.execute(db.text('PRAGMA journal_mode=WAL'))
                conn.commit()

        # Initialize database tables if they don't exist
        db.create_all()

        # Build similarity index for fast similar notes search
        from utils.similarity import rebuild_similarity_index
        print("Building similarity index...")
        stats = rebuild_similarity_index()
        print(f"✓ Similarity index built: {stats['indexed_notes']} notes, "
              f"{stats['unique_tokens']} unique tokens, "
              f"{stats['rebuild_time_seconds']}s, "
              f"{stats['cache_size_mb']} MB")

    # Register blueprints
    from auth import auth_bp
    from routes.main import main_bp
    from routes.voting import voting_bp
    from routes.filters import filters_bp
    from routes.admin import admin_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(voting_bp)
    app.register_blueprint(filters_bp)
    app.register_blueprint(admin_bp, url_prefix='/admin')

    return app


if __name__ == '__main__':
    app = create_app()
    app.run(debug=True)
