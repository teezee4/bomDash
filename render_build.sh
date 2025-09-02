#!/bin/bash

# Render Build Script for BOM Inventory Dashboard
# This script runs during the build phase on Render

echo "Starting build process..."

# Install Python dependencies
echo "Installing Python dependencies..."
pip install -r requirements.txt

# Apply database migrations FIRST (before creating tables)
echo "Applying database migrations..."
flask db upgrade

# Manually add missing location column if it doesn't exist (FIXED SQLAlchemy 2.0 syntax)
echo "Ensuring location column exists..."
python -c "
import os
from app import create_app, db
from sqlalchemy import text
app = create_app()
with app.app_context():
    try:
        # Check if column exists by trying to query it
        result = db.session.execute(text('SELECT column_name FROM information_schema.columns WHERE table_name = :table_name AND column_name = :column_name'), {'table_name': 'inventory_division', 'column_name': 'location'})
        if result.rowcount == 0:
            # Column doesn't exist, add it
            db.session.execute(text('ALTER TABLE inventory_division ADD COLUMN location VARCHAR(100)'))
            db.session.commit()
            print('✅ Location column added successfully')
        else:
            print('✅ Location column already exists')
    except Exception as e:
        print(f'⚠️  Column check result: {e}')
        # Try direct addition approach
        try:
            db.session.execute(text('ALTER TABLE inventory_division ADD COLUMN IF NOT EXISTS location VARCHAR(100)'))
            db.session.commit()
            print('✅ Location column ensured via IF NOT EXISTS')
        except Exception as e2:
            print(f'⚠️  Alternative approach result: {e2}')
            # Try one more approach - just add it and ignore if it exists
            try:
                db.session.execute(text('ALTER TABLE inventory_division ADD COLUMN location VARCHAR(100)'))
                db.session.commit()
                print('✅ Location column added (might have already existed)')
            except Exception as e3:
                if 'already exists' in str(e3).lower():
                    print('✅ Location column already exists (confirmed)')
                else:
                    print(f'❌ Failed to add location column: {e3}')
"

# Load BOM seed data (after schema is ready)
#echo "Loading BOM seed data..."
#python init_database.py

echo "Build completed successfully!"
