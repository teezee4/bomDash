# Render Build Script for BOM Inventory Dashboard
# This script runs during the build phase on Render

echo "Starting build process..."

# Install Python dependencies
echo "Installing Python dependencies..."
pip install -r requirements.txt

# Apply database migrations FIRST (before creating tables)
echo "Applying database migrations..."
flask db upgrade

# Load BOM seed data (after schema is ready)
echo "Loading BOM seed data..."
python init_database.py

echo "Build completed successfully!"