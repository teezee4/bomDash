from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_wtf.csrf import CSRFProtect
from config import config
import os

# Initialize extensions
db = SQLAlchemy()
migrate = Migrate()
csrf = CSRFProtect()

def create_app(config_name=None):
    """Create and configure the Flask application"""
    app = Flask(__name__)
    
    # Load configuration
    config_name = config_name or os.environ.get('FLASK_ENV', 'production' if os.environ.get('DATABASE_URL') else 'development')
    app.config.from_object(config[config_name])
    
    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)
    
    # Create instance folder if it doesn't exist (for local development)
    if not os.environ.get('DATABASE_URL'):  # Only for local SQLite
        try:
            os.makedirs(app.instance_path, exist_ok=True)
        except OSError:
            pass
    
    # Register blueprints
    from app.routes import main
    app.register_blueprint(main)
    
    # Import models to ensure they're registered with SQLAlchemy
    from app import models
    
    # REMOVED: db.create_all() block - use Flask-Migrate instead
    
    @app.route('/health')
    def health_check():
        """Simple health check endpoint for monitoring"""
        return {'status': 'healthy', 'database': 'connected' if db.engine else 'disconnected'}
    
    return app
'''
def create_app(config_name=None):
    """Create and configure the Flask application"""
    app = Flask(__name__)
    
    # Load configuration
    config_name = config_name or os.environ.get('FLASK_ENV', 'production' if os.environ.get('DATABASE_URL') else 'development')
    app.config.from_object(config[config_name])
    
    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)
    
    # Create instance folder if it doesn't exist (for local development)
    if not os.environ.get('DATABASE_URL'):  # Only for local SQLite
        try:
            os.makedirs(app.instance_path, exist_ok=True)
        except OSError:
            pass
    
    # Register blueprints
    from app.routes import main
    app.register_blueprint(main)
    
    # Import models to ensure they're registered with SQLAlchemy
    from app import models
    
    # Create database tables (only for first-time setup)
    with app.app_context():
        try:
            # This will create tables if they don't exist
            db.create_all()
        except Exception as e:
            print(f"Database initialization error: {e}")
            # In production, tables should be created via migrations
            pass
    
    @app.route('/health')
    def health_check():
        """Simple health check endpoint for monitoring"""
        return {'status': 'healthy', 'database': 'connected' if db.engine else 'disconnected'}
    
    return app
    '''