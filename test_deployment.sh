#!/bin/bash

echo "Testing deployment locally..."

# Activate virtual environment
source venv/bin/activate

# Test if Flask can be imported
python3 -c "import flask; print('Flask imported successfully')"

# Test if the app can be created
python3 -c "from backend.app import app; print('App created successfully')"

# Test health endpoint
echo "Starting app in background for testing..."
python3 backend/app.py &
APP_PID=$!

# Wait for app to start
sleep 3

# Test health endpoint
echo "Testing health endpoint..."
curl -f http://localhost:5000/health

# Kill the test app
kill $APP_PID

echo "Local test completed!"