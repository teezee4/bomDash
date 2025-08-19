#!/bin/bash

# Render Build Script for BOM Inventory Dashboard
# This script runs during the build phase on Render

echo "Starting build process..."
pip install -r requirements.txt

# Initialize database first
echo "Initializing database..."
python init_database.py

# Mark the problematic migration as completed without running it
echo "Marking migration as completed..."
flask db stamp f186032c5cc1

echo "Build completed successfully!"
