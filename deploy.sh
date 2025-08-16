#!/bin/bash

# Deployment script for AWS Lightsail
# This script helps deploy the Codebase Time Machine application

echo "Starting deployment for Codebase Time Machine..."

# Set production environment variables
export FLASK_ENV=production
export FLASK_DEBUG=False

# Create necessary directories
mkdir -p data/cache
mkdir -p data/repos

# Remove existing virtual environment if it exists but is broken
if [ -d "venv" ] && [ ! -f "venv/bin/python" ]; then
    echo "Removing broken virtual environment..."
    rm -rf venv
fi

# Create and setup virtual environment FIRST
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
    
    # Check if creation was successful
    if [ $? -ne 0 ]; then
        echo "ERROR: Virtual environment creation failed!"
        echo "Make sure python3-venv is installed: sudo apt install python3-venv"
        exit 1
    fi
fi

# Verify virtual environment was created successfully
if [ ! -f "venv/bin/python" ]; then
    echo "ERROR: Virtual environment creation failed!"
    echo "venv/bin/python does not exist"
    echo "Make sure python3-venv is installed: sudo apt install python3-venv"
    exit 1
fi

echo "Virtual environment created successfully"
echo "Activating virtual environment..."
source venv/bin/activate

echo "Installing/updating dependencies..."
venv/bin/pip install --upgrade pip
venv/bin/pip install -r requirements.txt

# Verify dependencies were installed
if [ ! -f "venv/bin/gunicorn" ]; then
    echo "Installing gunicorn..."
    venv/bin/pip install gunicorn
fi

# Initialize database AFTER dependencies are installed
echo "Initializing database..."
venv/bin/python backend/database/init_db.py

# Start the application
echo "Starting Codebase Time Machine..."

# Try to get public IP (works on AWS)
PUBLIC_IP=$(curl -s --connect-timeout 5 http://169.254.169.254/latest/meta-data/public-ipv4 2>/dev/null || echo "your-server-ip")
echo "Application will be available at: http://$PUBLIC_IP"

# Set Python path to include backend directory
export PYTHONPATH="${PYTHONPATH}:$(pwd)/backend"

# Set working directory for database paths
export WORKING_DIR=$(pwd)

# Create the Flask app instance
export FLASK_APP=backend.app:app

# Run with gunicorn for production (stay in root directory for correct paths)
echo "Starting with Gunicorn on port 80..."

# Start with gunicorn (already installed above)
exec venv/bin/gunicorn -w 4 -b 0.0.0.0:80 --timeout 300 --access-logfile - --error-logfile - --chdir $(pwd) backend.app:app