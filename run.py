#!/usr/bin/env python3
"""
BOM Inventory Dashboard - Phase 1
Entry point for the Flask application
"""
import os
from app import create_app
# Create Flask application
app = create_app()
if __name__ == '__main__':
    # Get configuration from environment variables
    debug = os.environ.get('FLASK_DEBUG', 'True').lower() in ['true', '1', 'yes']
    port = int(os.environ.get('PORT', 5000))
    host = os.environ.get('HOST', '127.0.0.1')
    print(f"Starting BOM Inventory Dashboard on {host}:{port}")
    print(f"Debug mode: {debug}")
    print("Access your dashboard at: http://{}:{}".format(host, port))
    app.run(debug=debug, host=host, port=port)