#!/bin/bash

# Render Build Script for BOM Inventory Dashboard
# This script runs during the build phase on Render

echo "Starting build process..."

# Install Python dependencies
echo "Installing Python dependencies..."
pip install -r requirements.txt

# Apply database migrations and seed sample data
echo "Running database migrations..."
FLASK_APP=app:create_app flask db upgrade

echo "Seeding initial data..."
python init_database.py

echo "Build completed successfully!"
