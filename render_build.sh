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

# Manually add missing location column if it doesn't exist
echo "Ensuring location column exists..."
python -c "
import os
from app import create_app, db
app = create_app()
with app.app_context():
    try:
        # Check if column exists by trying to query it
        result = db.engine.execute('SELECT column_name FROM information_schema.columns WHERE table_name = \'inventory_division\' AND column_name = \'location\';')
        if result.rowcount == 0:
            # Column doesn't exist, add it
            db.engine.execute('ALTER TABLE inventory_division ADD COLUMN location VARCHAR(100);')
            print('✅ Location column added successfully')
        else:
            print('✅ Location column already exists')
    except Exception as e:
        print(f'⚠️  Column operation result: {e}')
        # Try alternative approach
        try:
            db.engine.execute('ALTER TABLE inventory_division ADD COLUMN IF NOT EXISTS location VARCHAR(100);')
            print('✅ Location column ensured via IF NOT EXISTS')
        except Exception as e2:
            print(f'⚠️  Alternative approach result: {e2}')
"

# Load BOM seed data (after schema is ready)
echo "Loading BOM seed data..."
python init_database.py

echo "Build completed successfully!"