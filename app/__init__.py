from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect
from config import config
import os

# Initialize extensions
db = SQLAlchemy()
csrf = CSRFProtect()

def create_app(config_name=None):
    # Create Flask application
    app = Flask(__name__)
    
    # Load configuration
    config_name = config_name or os.environ.get('FLASK_ENV', 'default')
    app.config.from_object(config[config_name])
    
    # Initialize extensions
    db.init_app(app)
    csrf.init_app(app)
    
    # Create instance folder if it doesn't exist
    try:
        os.makedirs(app.instance_path, exist_ok=True)
    except OSError:
        pass
    
    # Register blueprints
    from app.routes import main
    app.register_blueprint(main)
    
    return app
