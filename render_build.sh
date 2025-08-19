#!/bin/bash

# Render Build Script for BOM Inventory Dashboard
# This script runs during the build phase on Render

echo "Starting build process..."

# Install Python dependencies
echo "Installing Python dependencies..."
pip install -r requirements.txt

# Initialize database with sample data (only run once)
echo "Initializing database..."
python init_database.py

flask db upgrade


echo "Build completed successfully!"