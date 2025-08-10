#!/usr/bin/env python3
"""
Complete Setup Script for BOM Inventory Dashboard
This script sets up everything to work with your Excel import script
"""

import os
import subprocess
import sys

def run_command(command, description):
    """Run a shell command and handle errors"""
    print(f"\n🔧 {description}")
    print(f"Running: {command}")
    
    try:
        result = subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
        if result.stdout:
            print(result.stdout)
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Error: {e}")
        if e.stdout:
            print(f"STDOUT: {e.stdout}")
        if e.stderr:
            print(f"STDERR: {e.stderr}")
        return False

def create_project_structure():
    """Create the necessary directories"""
    directories = [
        'app',
        'app/templates',
        'app/static',
        'instance'
    ]
    
    for directory in directories:
        os.makedirs(directory, exist_ok=True)
        print(f"✅ Created directory: {directory}")

def setup_flask_app():
    """Set up the Flask application with correct imports"""
    print("\n📁 Setting up Flask application structure...")
    
    # Create __init__.py for the app package
    init_content = '''from flask import Flask
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
'''
    
    with open('app/__init__.py', 'w') as f:
        f.write(init_content)
    
    print("✅ Created app/__init__.py")

def create_config_file():
    """Create the configuration file"""
    config_content = '''import os
from datetime import timedelta

class Config:
    # Basic Flask configuration
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'your-secret-key-change-in-production'
    
    # Database configuration - matching your migrate script
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \\
        'sqlite:///' + os.path.join('instance', 'bominventory.db')
    
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Session configuration
    PERMANENT_SESSION_LIFETIME = timedelta(hours=2)
    
    # File upload configuration (for future Excel uploads)
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size
    
    # Flask-WTF configuration
    WTF_CSRF_TIME_LIMIT = None

class DevelopmentConfig(Config):
    DEBUG = True

class ProductionConfig(Config):
    DEBUG = False

# Configuration dictionary for easy switching
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}
'''
    
    with open('config.py', 'w') as f:
        f.write(config_content)
    
    print("✅ Created config.py")

def create_run_file():
    """Create the main run file"""
    run_content = '''#!/usr/bin/env python3
"""
BOM Inventory Dashboard - Entry Point
Compatible with your Excel import script
"""
import os
from app import create_app, db

# Create Flask application
app = create_app()

if __name__ == '__main__':
    # Create tables if they don't exist
    with app.app_context():
        # Note: We don't call db.create_all() here because your migrate script handles schema creation
        pass
    
    # Get configuration from environment variables
    debug = os.environ.get('FLASK_DEBUG', 'True').lower() in ['true', '1', 'yes']
    port = int(os.environ.get('PORT', 5000))
    host = os.environ.get('HOST', '127.0.0.1')
    
    print(f"🚀 Starting BOM Inventory Dashboard on {host}:{port}")
    print(f"Debug mode: {debug}")
    print("Access your dashboard at: http://{}:{}".format(host, port))
    print("\\n💡 Make sure to import your Excel data first:")
    print("   python migrate_excel_data.py officalBom.xlsx")
    
    app.run(debug=debug, host=host, port=port)
'''
    
    with open('run.py', 'w') as f:
        f.write(run_content)
    
    print("✅ Created run.py")

def create_requirements_file():
    """Create requirements.txt with exact versions"""
    requirements = '''Flask==3.0.0
Flask-SQLAlchemy==3.1.1
Flask-WTF==1.2.1
WTForms==3.1.1
pandas==2.1.4
openpyxl==3.1.2
SQLAlchemy==2.0.23
'''
    
    with open('requirements.txt', 'w') as f:
        f.write(requirements)
    
    print("✅ Created requirements.txt")

def main():
    """Main setup function"""
    print("🎯 BOM Inventory Dashboard Setup")
    print("=" * 50)
    
    # Check if we're in the right directory
    if not os.path.exists('migrate_excel_data.py'):
        print("❌ Error: migrate_excel_data.py not found in current directory")
        print("Please run this script from the directory containing your migrate_excel_data.py file")
        sys.exit(1)
    
    # Create project structure
    create_project_structure()
    
    # Set up Flask components
    setup_flask_app()
    create_config_file()
    create_run_file()
    create_requirements_file()
    
    print("\n" + "=" * 50)
    print("✅ SETUP COMPLETE!")
    print("=" * 50)
    
    print("\\n📋 Next Steps:")
    print("1. Install requirements:")
    print("   pip install -r requirements.txt")
    print("\\n2. Import your Excel data:")
    print("   python migrate_excel_data.py officalBom.xlsx")
    print("\\n3. Copy the provided models.py, routes.py, and forms.py to app/")
    print("\\n4. Run the application:")
    print("   python run.py")
    print("\\n5. Open browser to: http://127.0.0.1:5000")
    
    print("\\n🎉 Your BOM Inventory Dashboard will be compatible with your Excel import script!")

if __name__ == '__main__':
    main()