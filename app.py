from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect
import os
from config import config

# Extensions
db = SQLAlchemy()
csrf = CSRFProtect()

def _normalize_db_url(url: str | None) -> str | None:
    if not url:
        return None
    url = url.strip()
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    return url

def create_app(config_name: str | None = None):
    app = Flask(__name__)

    # Choose config: production when DATABASE_URL exists, otherwise development
    env_cfg = os.environ.get("FLASK_ENV")
    config_name = config_name or (env_cfg if env_cfg in config else None)
    if not config_name:
        config_name = "production" if os.environ.get("DATABASE_URL") else "development"
    app.config.from_object(config[config_name])

    # Normalize DATABASE_URL at runtime (safety for postgres://)
    db_url = os.environ.get("DATABASE_URL")
    norm = _normalize_db_url(db_url)
    if norm:
        app.config["SQLALCHEMY_DATABASE_URI"] = norm

    # Init extensions
    db.init_app(app)
    csrf.init_app(app)

    # Register blueprints
    from app.routes import main
    app.register_blueprint(main)

    # Import models after db is ready
    from app import models  # noqa: F401

    # Create tables in dev/local or first boot. In production later, switch to migrations.
    with app.app_context():
        try:
            db.create_all()
        except Exception as e:
            print(f"db.create_all() skipped/failed: {e}")

    @app.get("/health")
    def health():
        try:
            # Ping database engine
            db.session.execute(db.text("SELECT 1"))
            db_ok = "connected"
        except Exception:
            db_ok = "disconnected"
        return {"status": "healthy", "database": db_ok}

    @app.context_processor
    def inject_divisions():
        from app.models import InventoryDivision
        return dict(divisions=InventoryDivision.query.all())

    return app

# Expose app for Gunicorn
app = create_app()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    host = os.environ.get("HOST", "0.0.0.0")
    app.run(host=host, port=port, debug=False)
 