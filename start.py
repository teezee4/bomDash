import os
from app import create_app, db
from app.models import MainBOMStorage

# Create app
app = create_app('production' if os.environ.get('RENDER') else 'development')

# Create tables on startup
with app.app_context():
    db.create_all()
    print("Database tables created!")
    
    # Check if we have any data
    part_count = MainBOMStorage.query.count()
    print(f"Current parts in database: {part_count}")

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
